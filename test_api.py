import requests
import json

# API endpoint
url = "http://localhost:8000/generate-questions"

print("=" * 80)
print("TEST 1: FIB Question with MathML enabled (Boolean True)")
print("=" * 80)

# Test 1: FIB with MathML enabled (using boolean)
fib_payload = {
    "curriculum": "UK National Curriculum",
    "curriculum_id": 1,
    "grade": "4",
    "grade_id": 123,
    "subject": "Maths",
    "subject_id": 1,
    "chapter": "Number – number and place value",
    "chapter_id": 456,
    "topic": "count from 0 in multiples of 4, 8, 50 and 100; find 10 or 100 more or less than a given number",
    "topic_id": 3281,
    "question_type": "FIB",
    "marks": 1,
    "taxonomy": "Remembering",
    "rigor_level": "Level 1",
    "number_of_questions": 2,
    "mathml": True  # Changed to boolean
}

try:
    response = requests.post(url, json=fib_payload)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"\nNumber of questions generated: {len(result)}")
        print("\nFirst question:")
        # Print first question with pretty formatting
        first_q = result[0]
        print(f"  Question Text: {first_q.get('question_text', 'N/A')}")
        print(f"  Accepted Answers: {first_q.get('accepted_answers', 'N/A')}")
        print(f"  Status: {first_q.get('status', 'N/A')}")
        print(f"  Has MathML: {('question_mathml' in first_q)}")
        
        # Check if using new {TEXT1} format
        if 'question_mathml' in first_q:
            has_new_format = '{TEXT1}' in first_q.get('question_mathml', '')
            has_old_format = '|#|TEXT:1|#|' in first_q.get('question_mathml', '')
            print(f"  Uses {TEXT1} format: {has_new_format}")
            print(f"  Uses |#|TEXT:1|#| format: {has_old_format}")
        
        print("\nFull Response (first 1500 chars):")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:1500] + "...")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Request failed: {str(e)}")

print("\n" + "=" * 80)
print("TEST 2: MCQ Question without MathML (Boolean False)")
print("=" * 80)

# Test 2: MCQ without MathML (using boolean)
mcq_payload = {
    "curriculum": "UK National Curriculum",
    "curriculum_id": 1,
    "grade": "4",
    "grade_id": 123,
    "subject": "Maths",
    "subject_id": 1,
    "chapter": "Number – number and place value",
    "chapter_id": 456,
    "topic": "count from 0 in multiples of 4, 8, 50 and 100",
    "topic_id": 789,
    "question_type": "MCQ",
    "marks": 1,
    "taxonomy": "Understanding",
    "rigor_level": "Level 2",
    "number_of_questions": 1,
    "mathml": False  # Changed to boolean
}

try:
    response = requests.post(url, json=mcq_payload)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"\nNumber of questions generated: {len(result)}")
        print("\nFirst question:")
        first_q = result[0]
        print(f"  Question Text: {first_q.get('question_text', 'N/A')}")
        print(f"  Options: {first_q.get('options', [])}")
        print(f"  Correct Option: {first_q.get('correct_option', 'N/A')}")
        print(f"  Status: {first_q.get('status', 'N/A')}")
        print(f"  Has MathML: {('question_mathml' in first_q)}")
        print("\nFull Response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Request failed: {str(e)}")

print("\n" + "=" * 80)
print("TESTS COMPLETED")
print("=" * 80)
