import yaml
import datetime
import json
import os
import re
from typing import Dict, Any, List, Tuple
from src.llm.gemini_client import call_gemini, call_gemini_with_pdf
from src.services.validator import (
    is_valid_mathml,
    count_blank_markers,
    validate_fib_accepted_answers,
    validate_mcq_options,
)

LOGS_DIR = os.path.join("logs")
os.makedirs(LOGS_DIR, exist_ok=True)
PROMPT_LOG = os.path.join(LOGS_DIR, "prompts.log")


def _append_prompt_log(prompt: str, raw: Any):
    try:
        with open(PROMPT_LOG, "a", encoding="utf-8") as f:
            f.write("=== PROMPT ===\n")
            f.write(prompt + "\n")
            f.write("=== RAW RESPONSE ===\n")
            f.write((raw if isinstance(raw, str) else repr(raw)) + "\n\n")
    except Exception:
        # don't fail generation because of logging issues
        pass


def load_prompt_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_prompt(prompt_cfg: Dict[str, Any], inputs: Dict[str, Any], n: int) -> str:
    system = prompt_cfg["prompt"]["instructions"]["system"]
    user_task = prompt_cfg["prompt"]["instructions"]["user_task"].replace("{N}", str(n))
    input_block = json.dumps(inputs, ensure_ascii=False, indent=2)
    few_shots = ""
    for ex in prompt_cfg["prompt"].get("few_shot_examples", []):
        few_shots += f"\n\n# Example: {ex['name']}\n{ex['json']}\n"
    schema_block = json.dumps(prompt_cfg["prompt"].get("schema", {}), ensure_ascii=False, indent=2)
    prompt = f"{system}\n\n{user_task}\n\n## Inputs\n{input_block}\n\n## FewShots{few_shots}\n\n## Schema\n{schema_block}"
    return prompt


# --- Robust JSON extractor to handle fences and multi-line output ---
def extract_json_objects(raw_text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Extract JSON objects from arbitrary raw text with enhanced error handling.
    Returns (list_of_parsed_dicts, list_of_unparsed_chunks_with_errors).
    """
    if not isinstance(raw_text, str):
        return [], [f"Raw response not a string: {repr(raw_text)[:200]}..."]

    # Clean the input text
    cleaned = raw_text.strip()
    
    # Try to parse the entire response as a single JSON object first
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return [parsed], []
    except json.JSONDecodeError:
        pass

    # If that fails, try to extract JSON objects from the text
    objs: List[Dict[str, Any]] = []
    errors: List[str] = []
    
    # Look for JSON objects using regex
    json_pattern = r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}'
    matches = re.finditer(json_pattern, cleaned, re.DOTALL)
    
    for match in matches:
        try:
            json_str = match.group(0)
            # Try to fix common JSON issues
            json_str = json_str.replace("\n", " ").replace("\r", " ").strip()
            # Remove any non-printable characters
            json_str = ''.join(char for char in json_str if char.isprintable() or char.isspace())
            
            # Try to parse the JSON
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                objs.append(parsed)
        except json.JSONDecodeError as e:
            errors.append(f"Failed to parse JSON: {str(e)}\nText: {json_str[:200]}...")
    
    # If we didn't find any JSON objects, try to extract with more permissive parsing
    if not objs:
        try:
            # Try to find JSON between markers
            json_markers = ['```json', '```', 'JSON:', 'Response:']
            for marker in json_markers:
                if marker in cleaned:
                    parts = cleaned.split(marker, 1)
                    if len(parts) > 1:
                        json_part = parts[1].split('```', 1)[0]  # Get content until next ``` if exists
                        try:
                            parsed = json.loads(json_part)
                            if isinstance(parsed, dict):
                                objs.append(parsed)
                                break
                        except json.JSONDecodeError:
                            continue
            
            # If still no objects, try to find the most JSON-looking part
            if not objs:
                # Look for the longest string that looks like a JSON object
                potential_jsons = re.findall(r'\{.*\}', cleaned, re.DOTALL)
                if potential_jsons:
                    # Sort by length descending and try to parse
                    potential_jsons.sort(key=len, reverse=True)
                    for json_str in potential_jsons:
                        try:
                            parsed = json.loads(json_str)
                            if isinstance(parsed, dict):
                                objs.append(parsed)
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            errors.append(f"Error during fallback JSON extraction: {str(e)}")
    
    # If we still have no objects, log the first 500 chars of the response for debugging
    if not objs and not errors:
        errors.append(f"No valid JSON objects found in response. First 500 chars: {cleaned[:500]}...")
    
    return objs, errors


def generate_and_validate(prompt_cfg_path: str, app_cfg: Dict[str, Any], inputs: Dict[str, Any], n: int) -> Tuple[List[Dict[str, Any]], str]:
    """Generate questions using the LLM and validate the responses."""
    try:
        prompt_cfg = load_prompt_config(prompt_cfg_path)
        prompt = build_prompt(prompt_cfg, inputs, n)

        # Call the LLM with error handling
        try:
            raw = call_gemini(prompt, {**prompt_cfg, **{"app": app_cfg}}, n)
        except Exception as e:
            error_msg = f"LLM call failed: {str(e)}"
            _append_prompt_log(prompt, f"Exception: {error_msg}")
            return [{"_error": error_msg}], ""

        # Validate the response is a string
        if not isinstance(raw, str):
            error_msg = f"LLM returned non-string response (type={type(raw)}). Check logs for details."
            _append_prompt_log(prompt, f"Non-string response: {str(raw)[:500]}...")
            return [{"_error": error_msg}], ""

        # Save prompt and response for debugging
        _append_prompt_log(prompt, raw)

        # Extract JSON objects from the response
        parsed_objs, parse_errors = extract_json_objects(raw)
        
        # If we have parse errors but no objects, try to recover
        if parse_errors and not parsed_objs and len(parse_errors) == 1:
            # Try to extract the most promising JSON-like part
            error_text = parse_errors[0]
            if len(error_text) > 50:  # Only try to recover if we have enough text
                try:
                    # Look for the first { and last } in the error text
                    start = error_text.find('{')
                    end = error_text.rfind('}')
                    if start != -1 and end != -1 and end > start:
                        json_str = error_text[start:end+1]
                        parsed = json.loads(json_str)
                        if isinstance(parsed, dict):
                            parsed_objs = [parsed]
                            parse_errors = []
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        # Handle any other exceptions
        error_msg = f"Unexpected error during question generation: {str(e)}"
        _append_prompt_log("", f"Unexpected error: {error_msg}")
        return [{"_error": error_msg}], ""

    results: List[Dict[str, Any]] = []

    # Validate each parsed object
    results: List[Dict[str, Any]] = []
    
    for obj in parsed_objs:
        if not isinstance(obj, dict):
            results.append({"_validation_error": f"Expected a dictionary, got {type(obj).__name__}"})
            continue
            
        # Fill in default values from inputs if they're missing
        for k in ["syllabus", "standard", "subject", "topic", "section", "marks", "taxonomy", "rigor"]:
            if k not in obj:
                # Get the key from inputs, using the full path if needed
                input_key = k
                if k == "syllabus":
                    input_key = "syllabus"
                elif k == "standard":
                    input_key = "standard"
                obj[k] = inputs.get(input_key, "")
        
        # Set default values for required fields
        obj.setdefault("type", "MCQ")  # Default to MCQ if not specified
        obj.setdefault("question_mathml", "")
        obj.setdefault("solution_mathml", "")
        
        # Initialize validation
        ok = True
        reasons = []
        
        # Get question type and validate accordingly
        qtype = str(obj.get("type", "")).upper()
        
        # Common validations for all question types
        if not obj.get("question_mathml"):
            ok = False
            reasons.append("Missing question_mathml")
        elif not is_valid_mathml(obj["question_mathml"]):
            ok = False
            reasons.append("Invalid question MathML")
            
        if not obj.get("solution_mathml"):
            ok = False
            reasons.append("Missing solution_mathml")
        elif not is_valid_mathml(obj["solution_mathml"]):
            ok = False
            reasons.append("Invalid solution MathML")
        
        # Type-specific validations
        if qtype == "FIB":
            blank_count = count_blank_markers(obj["question_mathml"])
            if blank_count != 1:
                ok = False
                reasons.append(f"FIB must have exactly 1 blank (found {blank_count})")
                
            a_ok, a_reason = validate_fib_accepted_answers(obj.get("accepted_answers", "") or "")
            if not a_ok:
                ok = False
                reasons.append(f"Invalid accepted_answers: {a_reason}")
                
        elif qtype == "MCQ":
            options = obj.get("options", [])
            m_ok, m_reason = validate_mcq_options(options)
            if not m_ok:
                ok = False
                reasons.append(f"Invalid options: {m_reason}")
                
            correct = obj.get("correct_option")
            if not isinstance(correct, int) or correct < 1 or correct > len(options):
                ok = False
                reasons.append(f"Invalid correct_option: must be between 1 and {len(options)}")
        else:
            ok = False
            reasons.append(f"Unknown question type: {qtype}")
            
        # Combine all reasons if there are multiple issues
        reason = "; ".join(reasons) if reasons else ""

        # Add metadata and validation results
        if ok:
            obj["status"] = "AI-Created"
            obj["ai_meta"] = {
                "prompt_version": prompt_cfg.get("prompt", {}).get("prompt_version", "v1.2"),
                "model": prompt_cfg.get("prompt", {}).get("model_name", "unknown"),
                "generated_at": datetime.datetime.utcnow().isoformat(),
            }
        else:
            obj["status"] = "Error"
            obj["_validation_error"] = reason
            
            # Add more context for debugging
            obj["_debug"] = {
                "input_keys": list(inputs.keys()),
                "question_type": qtype,
                "validation_errors": reasons
            }
        
        results.append(obj)
    
    # Handle parse errors
    for i, error in enumerate(parse_errors, 1):
        results.append({
            "_parsing_error": f"Error {i}: {error[:500]}",
            "status": "Error",
            "_debug": {
                "error_type": "JSON parsing",
                "input_keys": list(inputs.keys())
            }
        })
    
    # If we have no valid results but have parsed objects, include them for debugging
    if not any(r.get("status") == "AI-Created" for r in results) and parsed_objs:
        for i, obj in enumerate(parsed_objs):
            if isinstance(obj, dict) and "_validation_error" not in obj:
                results.append({
                    "_partial_result": f"Partially parsed object {i+1}",
                    "status": "Partial",
                    "data": {k: v for k, v in obj.items() if not k.startswith('_')}
                })

    return results, raw


def save_results_to_file(results: List[Dict[str, Any]], outputs_dir: str) -> str:
    os.makedirs(outputs_dir, exist_ok=True)
    ts = __import__("datetime").datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(outputs_dir, f"questions_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return path


def generate_and_validate_with_pdf(prompt_cfg_path: str, app_cfg: Dict[str, Any], inputs: Dict[str, Any], n: int, pdf_bytes: bytes) -> Tuple[List[Dict[str, Any]], str]:
    """Generate questions using the LLM with PDF context and validate the responses."""
    try:
        prompt_cfg = load_prompt_config(prompt_cfg_path)
        prompt = build_prompt(prompt_cfg, inputs, n)

        # Call the LLM with error handling - usage call_gemini_with_pdf
        try:
            raw = call_gemini_with_pdf(prompt, pdf_bytes, {**prompt_cfg, **{"app": app_cfg}}, n)
        except Exception as e:
            error_msg = f"LLM call (PDF) failed: {str(e)}"
            _append_prompt_log(prompt, f"Exception: {error_msg}")
            return [{"_error": error_msg}], ""

        # Validate the response is a string
        if not isinstance(raw, str):
            error_msg = f"LLM returned non-string response (type={type(raw)}). Check logs for details."
            _append_prompt_log(prompt, f"Non-string response: {str(raw)[:500]}...")
            return [{"_error": error_msg}], ""

        # Save prompt and response for debugging
        _append_prompt_log(prompt + "\n[PDF CONTENT WAS ATTACHED]", raw)

        # Extract JSON objects from the response
        parsed_objs, parse_errors = extract_json_objects(raw)
        
        # If we have parse errors but no objects, try to recover
        if parse_errors and not parsed_objs and len(parse_errors) == 1:
            # Try to extract the most promising JSON-like part
            error_text = parse_errors[0]
            if len(error_text) > 50:  # Only try to recover if we have enough text
                try:
                    # Look for the first { and last } in the error text
                    start = error_text.find('{')
                    end = error_text.rfind('}')
                    if start != -1 and end != -1 and end > start:
                        json_str = error_text[start:end+1]
                        parsed = json.loads(json_str)
                        if isinstance(parsed, dict):
                            parsed_objs = [parsed]
                            parse_errors = []
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        # Handle any other exceptions
        error_msg = f"Unexpected error during question generation: {str(e)}"
        _append_prompt_log("", f"Unexpected error: {error_msg}")
        return [{"_error": error_msg}], ""

    # Reuse validation logic - essentially similar to generate_and_validate
    # We can refactor validation Logic out, but for robustness let's just copy the validation part for now
    # or reuse the logic by calling a helper?
    # For now, I will just duplicate the validation logic below to ensure it works exactly the same
    
    results: List[Dict[str, Any]] = []
    
    for obj in parsed_objs:
        if not isinstance(obj, dict):
            results.append({"_validation_error": f"Expected a dictionary, got {type(obj).__name__}"})
            continue
            
        # Fill in default values from inputs if they're missing
        for k in ["syllabus", "standard", "subject", "topic", "section", "marks", "taxonomy", "rigor"]:
            if k not in obj:
                # Get the key from inputs, using the full path if needed
                input_key = k
                if k == "syllabus":
                    input_key = "syllabus"
                elif k == "standard":
                    input_key = "standard"
                obj[k] = inputs.get(input_key, "")
        
        # Set default values for required fields
        obj.setdefault("type", "MCQ")  # Default to MCQ if not specified
        obj.setdefault("question_mathml", "")
        obj.setdefault("solution_mathml", "")
        
        # Initialize validation
        ok = True
        reasons = []
        
        # Get question type and validate accordingly
        qtype = str(obj.get("type", "")).upper()
        
        # Common validations for all question types
        if not obj.get("question_mathml"):
            ok = False
            reasons.append("Missing question_mathml")
        elif not is_valid_mathml(obj["question_mathml"]):
            ok = False
            reasons.append("Invalid question MathML")
            
        if not obj.get("solution_mathml"):
            ok = False
            reasons.append("Missing solution_mathml")
        elif not is_valid_mathml(obj["solution_mathml"]):
            ok = False
            reasons.append("Invalid solution MathML")
        
        # Type-specific validations
        if qtype == "FIB":
            blank_count = count_blank_markers(obj["question_mathml"])
            if blank_count != 1:
                ok = False
                reasons.append(f"FIB must have exactly 1 blank (found {blank_count})")
                
            a_ok, a_reason = validate_fib_accepted_answers(obj.get("accepted_answers", "") or "")
            if not a_ok:
                ok = False
                reasons.append(f"Invalid accepted_answers: {a_reason}")
                
        elif qtype == "MCQ":
            options = obj.get("options", [])
            m_ok, m_reason = validate_mcq_options(options)
            if not m_ok:
                ok = False
                reasons.append(f"Invalid options: {m_reason}")
                
            correct = obj.get("correct_option")
            if not isinstance(correct, int) or correct < 1 or correct > len(options):
                ok = False
                reasons.append(f"Invalid correct_option: must be between 1 and {len(options)}")
        else:
            ok = False
            reasons.append(f"Unknown question type: {qtype}")
            
        # Combine all reasons if there are multiple issues
        reason = "; ".join(reasons) if reasons else ""

        # Add metadata and validation results
        if ok:
            obj["status"] = "AI-Created"
            obj["ai_meta"] = {
                "prompt_version": prompt_cfg.get("prompt", {}).get("prompt_version", "v1.2"),
                "model": prompt_cfg.get("prompt", {}).get("model_name", "unknown"),
                "generated_at": datetime.datetime.utcnow().isoformat(),
            }
        else:
            obj["status"] = "Error"
            obj["_validation_error"] = reason
            
            # Add more context for debugging
            obj["_debug"] = {
                "input_keys": list(inputs.keys()),
                "question_type": qtype,
                "validation_errors": reasons
            }
        
        results.append(obj)
    
    # Handle parse errors
    for i, error in enumerate(parse_errors, 1):
        results.append({
            "_parsing_error": f"Error {i}: {error[:500]}",
            "status": "Error",
            "_debug": {
                "error_type": "JSON parsing",
                "input_keys": list(inputs.keys())
            }
        })
    
    # If we have no valid results but have parsed objects, include them for debugging
    if not any(r.get("status") == "AI-Created" for r in results) and parsed_objs:
        for i, obj in enumerate(parsed_objs):
            if isinstance(obj, dict) and "_validation_error" not in obj:
                results.append({
                    "_partial_result": f"Partially parsed object {i+1}",
                    "status": "Partial",
                    "data": {k: v for k, v in obj.items() if not k.startswith('_')}
                })

    return results, raw
