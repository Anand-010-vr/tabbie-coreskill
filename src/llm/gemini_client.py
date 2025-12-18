import os
import json
import time
from typing import Dict, Any
# google-genai SDK
from google import genai
from google.genai import types

# retry params
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.2

def call_gemini(prompt: str, cfg: Dict[str, Any], n: int) -> str:
    """
    Use google-genai SDK to call Gemini. Returns the model text output (string).
    If cfg['app']['mock_mode'] is True, returns mock NDJSON for testing.
    """
    if cfg.get("app", {}).get("mock_mode", True):
        return _mock_output(prompt, cfg, n)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    client = genai.Client(api_key=api_key)

    model_name = cfg.get("prompt", {}).get("model_name", "gemini-2.5-flash")
    temperature = cfg.get("prompt", {}).get("temperature", 0.2)
    # Default to 8192 tokens to handle multiple questions with full MathML
    max_output_tokens = cfg.get("prompt", {}).get("max_tokens", 8192)

    attempt = 0
    last_exc = None
    while attempt < _MAX_RETRIES:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                max_output_tokens=max_output_tokens
            )
        )
            # response may provide a callable .text() or .text attribute
            if hasattr(response, "text") and callable(response.text):
                return response.text()
            if hasattr(response, "text"):
                return response.text
            # fallback serialization
            try:
                return json.dumps(response.__dict__, default=str)
            except Exception:
                return str(response)
        except Exception as e:
            last_exc = e
            attempt += 1
            if attempt >= _MAX_RETRIES:
                raise RuntimeError(f"Gemini API failed after {attempt} attempts: {e}")
            time.sleep(_BACKOFF_BASE ** attempt)

    raise RuntimeError(f"Gemini call failed, last exception: {last_exc}")


def _mock_output(prompt: str, cfg: Dict[str, Any], n: int) -> str:
    lines = []
    pv = cfg.get("prompt", {}).get("prompt_version", "v1.1")
    model = cfg.get("prompt", {}).get("model_name", "mock-model")
    is_fib = "|#|TEXT:1|#|" in prompt or '"type": "FIB"' in prompt or '"Type": "FIB"' in prompt
    for i in range(n):
        if is_fib:
            q = {
                "curriculum":"UK National Curriculum",
                "subject":"Math",
                "grade":"3",
                "chapter":"Mock Chapter",
                "topic":"Mock FIB topic",
                "type":"FIB",
                "marks":1,
                "taxonomy":"Remembering",
                "rigor":"Level 1",
                "question_mathml":"<p><math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mn>5</mn><mo>&#160;</mo><mo>+</mo><mo>&#160;</mo><mn>8</mn><mo>&#160;</mo><mo>=</mo><mo>&#160;</mo><mi>|#|TEXT:1|#|</mi></math></p>",
                "solution_mathml":"<p><math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mi>Step</mi><mo>&#160;</mo><mn>1</mn><mo>:</mo><mo>&#160;</mo><mn>5</mn><mo>&#160;</mo><mo>+</mo><mo>&#160;</mo><mn>8</mn><mo>&#160;</mo><mo>=</mo><mo>&#160;</mo><mn>13</mn></math></p>",
                "question_text":"5 + 8 = ?",
                "solution_text":"Step 1: 5 + 8 = 13.",
                "accepted_answers":"13",
                "status":"AI-Created",
                "ai_meta":{"prompt_version":pv,"model":model}
            }
        else:
            q = {
                "curriculum":"UK National Curriculum",
                "subject":"Math",
                "grade":"4",
                "chapter":"Mock Chapter",
                "topic":"Mock MCQ topic",
                "type":"MCQ",
                "marks":1,
                "taxonomy":"Remembering",
                "rigor":"Level 1",
                "question_mathml":"<p><math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mi>What</mi><mo>&#160;</mo><mi>is</mi><mo>&#160;</mo><mn>7</mn><mo>&#160;</mo><mo>+</mo><mo>&#160;</mo><mn>6</mn><mo>?</mo></math></p>",
                "solution_mathml":"<p><math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mi>Step</mi><mo>&#160;</mo><mn>1</mn><mo>:</mo><mo>&#160;</mo><mn>7</mn><mo>&#160;</mo><mo>+</mo><mo>&#160;</mo><mn>6</mn><mo>&#160;</mo><mo>=</mo><mo>&#160;</mo><mn>13</mn></math></p>",
                "question_text":"What is 7 + 6?",
                "solution_text":"Step 1: 7 + 6 = 13.",
                "options":[
                    "<p><math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mn>13</mn></math></p>",
                    "<p><math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mn>12</mn></math></p>",
                    "<p><math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mn>14</mn></math></p>",
                    "<p><math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mn>11</mn></math></p>"
                ],
                "options_text_1":"13",
                "options_text_2":"12",
                "options_text_3":"14",
                "options_text_4":"11",
                "correct_option":1,
                "status":"AI-Created",
                "ai_meta":{"prompt_version":pv,"model":model}
            }
        lines.append(json.dumps(q))
    return "\n".join(lines)


def call_gemini_with_pdf(prompt: str, pdf_bytes: bytes, cfg: Dict[str, Any], n: int) -> str:
    """
    Call Gemini with a PDF file and a text prompt.
    """
    if cfg.get("app", {}).get("mock_mode", True):
        # reuse mock output for now, ignoring PDF content
        return _mock_output(prompt, cfg, n)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    # Initialize client
    client = genai.Client(api_key=api_key)

    # Get configuration with defaults
    model_name = cfg.get("prompt", {}).get("model_name", "gemini-2.5-pro")
    
    # Create PDF part
    try:
        pdf_part = types.Part.from_bytes(
            data=pdf_bytes,
            mime_type='application/pdf'
        )
    except Exception as e:
        raise ValueError(f"Failed to create PDF part: {e}")

    attempt = 0
    last_exc = None
    while attempt < _MAX_RETRIES:
        try:
            # Generate content
            # Using specific config from user snippet if model is 2.5-pro, otherwise standard
            if "gemini-2.5-pro" in model_name:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[pdf_part, prompt],
                    config=types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(thinking_budget=6500)
                    )
                )
            else:
                # Fallback for other models that might not support thinking config
                # or if we want to use standard config from cfg
                temperature = cfg.get("prompt", {}).get("temperature", 0.8)
                max_tokens = cfg.get("prompt", {}).get("max_tokens", 8192)
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=[pdf_part, prompt],
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens
                    )
                )

            if hasattr(response, "text") and callable(response.text):
                return response.text()
            if hasattr(response, "text"):
                return response.text
            return str(response)

        except Exception as e:
            last_exc = e
            attempt += 1
            if attempt >= _MAX_RETRIES:
                break
            time.sleep(_BACKOFF_BASE ** attempt)

    raise RuntimeError(f"Gemini PDF call failed after {attempt} attempts: {last_exc}")
