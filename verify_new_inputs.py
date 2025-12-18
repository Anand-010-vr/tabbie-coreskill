import requests
import json

url = "http://localhost:8000/generate-questions"

payload = {
    "curriculum": "UK National Curriculum",
    "curriculum_id": 1,
    "grade": "4",
    "grade_id": 123,
    "subject": "Maths",
    "subject_id": 1,
    "chapter": "Number – addition and subtraction",
    "chapter_id": 456,
    "topic": "Add two 4-digit numbers",
    "topic_id": 789,
    "question_type": "MCQ",
    "marks": 1,
    "taxonomy": "Applying",
    "rigor_level": "Level 2",
    "number_of_questions": 1,
    "mathml": True,
    "new_concept": "Columnar addition with carrying",
    "old_concept": "Adding 3-digit numbers",
    "additional_notes": "Please include a word problem involving money."
}

print("Sending request with new fields...")
try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success! Response received.")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
