# FastAPI Question Generator - Testing Guide

## Installation

First, install the new dependencies:

```bash
pip install -r requirements.txt
```

## Running the API

Start the FastAPI server:

```bash
uvicorn api_app:app --reload --port 8000
```

The API will be available at: `http://localhost:8000`

## API Documentation

Once the server is running, you can access:
- **Interactive API docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative API docs (ReDoc)**: http://localhost:8000/redoc

## Testing the API

### Using the Browser

1. Go to http://localhost:8000/docs
2. Click on the POST `/generate-questions` endpoint
3. Click "Try it out"
4. Modify the example JSON as needed
5. Click "Execute"

### Using cURL

#### Test 1: Generate FIB Question with MathML

```bash
curl -X POST "http://localhost:8000/generate-questions" ^
  -H "Content-Type: application/json" ^
  -d "{\"curriculum\": \"UK National Curriculum\", \"curriculum_id\": 1, \"grade\": \"4\", \"grade_id\": 123, \"subject\": \"Maths\", \"subject_id\": 1, \"chapter\": \"Number – number and place value\", \"chapter_id\": 456, \"topic\": \"count from 0 in multiples of 4, 8, 50 and 100; find 10 or 100 more or less than a given number\", \"topic_id\": 3281, \"question_type\": \"FIB\", \"marks\": 1, \"taxonomy\": \"Remembering\", \"rigor_level\": \"Level 1\", \"number_of_questions\": 2, \"mathml\": \"y\"}"
```

#### Test 2: Generate MCQ Question without MathML

```bash
curl -X POST "http://localhost:8000/generate-questions" ^
  -H "Content-Type: application/json" ^
  -d "{\"curriculum\": \"UK National Curriculum\", \"curriculum_id\": 1, \"grade\": \"4\", \"grade_id\": 123, \"subject\": \"Maths\", \"subject_id\": 1, \"chapter\": \"Number – number and place value\", \"chapter_id\": 456, \"topic\": \"count from 0 in multiples of 4, 8, 50 and 100\", \"topic_id\": 789, \"question_type\": \"MCQ\", \"marks\": 1, \"taxonomy\": \"Understanding\", \"rigor_level\": \"Level 2\", \"number_of_questions\": 1, \"mathml\": \"n\"}"
```

### Using Python

```python
import requests
import json

url = "http://localhost:8000/generate-questions"

# Test FIB with MathML
payload = {
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
    "question_type": "FIB",
    "marks": 1,
    "taxonomy": "Remembering",
    "rigor_level": "Level 1",
    "number_of_questions": 2,
    "mathml": "y"
}

response = requests.post(url, json=payload)
print(json.dumps(response.json(), indent=2))
```

## Request Format

### Required Fields

```json
{
  "curriculum": "string",
  "curriculum_id": 0,
  "grade": "string",
  "grade_id": 0,
  "subject": "string",
  "subject_id": 0,
  "chapter": "string",
  "chapter_id": 0,
  "topic": "string",
  "topic_id": 0,
  "question_type": "MCQ or FIB",
  "marks": 1-10,
  "taxonomy": "Remembering|Understanding|Applying|Analyzing|Evaluating|Creating",
  "rigor_level": "Level 1|Level 2|Level 3",
  "number_of_questions": 1-10,
  "mathml": "y or n"
}
```

## Response Format

### FIB Response (with MathML)

```json
[
  {
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
    "question_type": "FIB",
    "marks": 1,
    "taxonomy": "Remembering",
    "rigor_level": "Level 1",
    "question_text": "100 less than 6720 is ?",
    "solution_text": "Step 1: To find 100 less than 6720...",
    "accepted_answers": "6620",
    "status": "AI-Created",
    "ai_meta": {
      "prompt_version": "v1.5",
      "model": "gemini-2.5-flash",
      "generated_at": "2025-12-03T08:53:11.148582"
    },
    "question_mathml": "<p><math>...</math></p>",
    "solution_mathml": "<p><math>...</math></p>",
    "accepted_answers_mathml": "6620"
  }
]
```

### MCQ Response (without MathML)

```json
[
  {
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
    "question_text": "What is 100 more than 5000?",
    "solution_text": "Add 100 to 5000...",
    "options": [
      "5100",
      "5010",
      "6000",
      "4900"
    ],
    "correct_option": 1,
    "status": "AI-Created",
    "ai_meta": {
      "prompt_version": "v1.5",
      "model": "gemini-2.5-flash",
      "generated_at": "2025-12-03T08:53:11.148582"
    }
  }
]
```

## Notes

1. **MathML Toggle**: When `mathml: "n"`, the response will NOT include `question_mathml`, `solution_mathml`, `options_mathml`, or `accepted_answers_mathml` fields
2. **Multiple Questions**: Set `number_of_questions` to generate multiple questions in one request (max 10)
3. **Response is Always an Array**: Even if requesting 1 question, the response is an array
4. **Error Handling**: Invalid inputs return 400 status code, server errors return 500

## Troubleshooting

### Port Already in Use
If port 8000 is already in use, specify a different port:
```bash
uvicorn api_app:app --reload --port 8001
```

### Module Not Found Errors
Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Database Connection Errors
Make sure your `.env` file has the correct database credentials if the generator uses the database.
