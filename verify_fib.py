import requests
import json
import sys

url = "http://localhost:8000/generate-questions"

fib_payload = {
    "curriculum": "UK National Curriculum",
    "curriculum_id": 1,
    "grade": "4",
    "grade_id": 123,
    "subject": "Maths",
    "subject_id": 1,
    "chapter": "Number – number and place value",
    "chapter_id": 456,
    "topic": "count from 0 in multiples of 4, 8, 50 and 100",
    "topic_id": 3281,
    "question_type": "FIB",
    "marks": 1,
    "taxonomy": "Remembering",
    "rigor_level": "Level 1",
    "number_of_questions": 1,
    "mathml": True
}

output_file = "verification_output.txt"

def log(msg):
    print(msg)
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# Clear file
open(output_file, "w", encoding="utf-8").close()

try:
    log("Sending request...")
    response = requests.post(url, json=fib_payload)
    log(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        log(f"Number of questions: {len(result)}")
        
        if len(result) > 0:
            q = result[0]
            log(f"Question Text: {q.get('question_text', 'N/A')}")
            log(f"Question MathML: {q.get('question_mathml', 'N/A')}")
            
            # Check for markers
            text_ok = "|#|TEXT:1|#|" in q.get('question_text', '')
            mathml_ok = "|#|TEXT:1|#|" in q.get('question_mathml', '')
            
            log(f"Marker in Text: {text_ok}")
            log(f"Marker in MathML: {mathml_ok}")
            
            if text_ok and mathml_ok:
                log("SUCCESS: format verified.")
            else:
                log("FAILURE: Incorrect format.")
    else:
        log(f"Error: {response.text}")

except Exception as e:
    log(f"Exception: {str(e)}")
