import sys
import os
from pathlib import Path

# Add current directory to path so imports work
current_dir = Path.cwd()
sys.path.append(str(current_dir))

try:
    from api_app import QuestionGenerationRequest, MCQQuestionResponse
    from api_app_pdf import MCQQuestionResponse as PDFMCQResponse
    print("Imports successful")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)

def test_models():
    print("Testing models...")
    try:
        # Test Request Model
        req = QuestionGenerationRequest(
            curriculum="Test", curriculum_id=1,
            grade="Test", grade_id=1,
            subject="Test", subject_id=1,
            chapter="Test", chapter_id=1,
            topic="Test", topic_id=1,
            question_type="MCQ", marks=1,
            taxonomy="Remembering", taxonomy_id=100, # New field
            rigor_level="Level 1"
        )
        assert req.taxonomy_id == 100
        print("QuestionGenerationRequest model verified: taxonomy_id found")
    except Exception as e:
        print(f"QuestionGenerationRequest validation failed: {e}")
        return

    try:
        # Test Response Model
        resp = MCQQuestionResponse(
            curriculum="Test", curriculum_id=1,
            grade="Test", grade_id=1,
            subject="Test", subject_id=1,
            chapter="Test", chapter_id=1,
            topic="Test", topic_id=1,
            question_type="MCQ", marks=1,
            taxonomy="Remembering", taxonomy_id=100, # New field
            rigor_level="Level 1",
            question_text="Q", solution_text="S",
            options=["A","B","C","D"], correct_option=1,
            status="Success",
            ai_meta={"prompt_version":"1", "model":"gpt", "generated_at":"now"}
        )
        assert resp.taxonomy_id == 100
        print("MCQQuestionResponse model verified: taxonomy_id found")
    except Exception as e:
        print(f"MCQQuestionResponse validation failed: {e}")
        return

    try:
        # Test PDF Response Model
        pdf_resp = PDFMCQResponse(
            curriculum="Test", curriculum_id=1,
            grade="Test", grade_id=1,
            subject="Test", subject_id=1,
            chapter="Test", chapter_id=1,
            topic="Test", topic_id=1,
            question_type="MCQ", marks=1,
            taxonomy="Remembering", taxonomy_id=200, # New field
            rigor_level="Level 1",
            question_text="Q", solution_text="S",
            options=["A","B","C","D"], correct_option=1,
            status="Success",
            ai_meta={"prompt_version":"1", "model":"gpt", "generated_at":"now"}
        )
        assert pdf_resp.taxonomy_id == 200
        print("PDFMCQResponse model verified: taxonomy_id found")
    except Exception as e:
        print(f"PDFMCQResponse validation failed: {e}")
        return
        
    print("All models verified successfully!")

if __name__ == "__main__":
    test_models()
