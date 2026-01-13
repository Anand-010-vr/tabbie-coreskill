import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.services.generator import generate_and_validate, load_prompt_config

def test_variety_logic():
    print("Testing Variety Logic Enhancement...")
    
    prompt_cfg_path = os.path.join("config", "prompt.yaml")
    app_cfg = {
        "mock_mode": True,  # Use mock mode to avoid API costs
        "gemini_api_key": "mock-key"
    }
    
    inputs = {
        "syllabus": "UK National Curriculum",
        "standard": "4",
        "subject": "Maths",
        "topic": "Number – addition",
        "section": "add and subtract numbers with up to 4 digits",
        "marks": 1,
        "rigor": "Level 1",
        "classification": "Number-Based Remembering",
        "taxonomy": "Remembering",
        "previous_questions": "Question 1: [MCQ] What is 1+1?\nQuestion 2: [FIB] 2+2=|#|TEXT:1|#|"
    }
    
    # We'll use a small N to test
    N = 2
    
    results, strategy, raw, prompt_used = generate_and_validate(prompt_cfg_path, app_cfg, inputs, N)
    
    print("\n--- Verification Results ---")
    
    # Check if placeholders were replaced in the prompt
    print(f"Checking placeholder replacement in prompt...")
    if "{previous_questions}" not in prompt_used and "Question 1: [MCQ] What is 1+1?" in prompt_used:
        print("SUCCESS: {previous_questions} placeholder was correctly replaced.")
    else:
        print("FAILURE: {previous_questions} placeholder still present or not replaced correctly.")
        
    if "{section}" not in prompt_used and "add and subtract numbers with up to 4 digits" in prompt_used:
        print("SUCCESS: {section} placeholder was correctly replaced.")
    else:
        print("FAILURE: {section} placeholder still present or not replaced correctly.")

    # Check strategy object if mock client was updated or if we can see it in logs
    # Note: strategy object is parsed from the raw response
    # In mock mode, _mock_output doesn't return a strategy object yet.
    # I should update _mock_output to return a strategy object to fully test this.

if __name__ == "__main__":
    test_variety_logic()
