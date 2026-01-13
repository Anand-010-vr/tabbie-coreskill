import asyncio
from unittest.mock import MagicMock, patch
from api_app import generate_questions, QuestionGenerationRequest

# Mock APP_CFG and PROMPT_CFG_PATH
import api_app
api_app.APP_CFG = {'app': {}}
api_app.PROMPT_CFG_PATH = "dummy_path"

# Mock logger
api_app.logger = MagicMock()

async def verify_single_call():
    print("Verifying single call logic...")
    
    # Mock generator returning mixed taxonomy results
    mock_results = [
        {"taxonomy": "Remembering", "question_text": "Q1", "type": "MCQ"},
        {"taxonomy": "Remembering", "question_text": "Q2", "type": "MCQ"},
        {"taxonomy": "Understanding", "question_text": "Q3", "type": "MCQ"},
    ]
    
    # Setup mock
    with patch('api_app.generate_and_validate') as mock_gen:
        mock_gen.return_value = (mock_results, "raw_response")
        
        # Create request
        req = QuestionGenerationRequest(
            curriculum="test",
            curriculum_id=1,
            grade="test",
            grade_id=1,
            subject="test",
            subject_id=1,
            chapter="test",
            chapter_id=1,
            topic="test",
            topic_id=1,
            domain="test",
            domain_id=1,
            question_type="MCQ",
            marks=1,
            taxonomy=["Remembering", "Understanding"], # 2:1 ratio for 3 questions?
            taxonomy_id=1,
            rigor_level="Level 1",
            number_of_questions=3,
            mathml=False
        )
        
        # In api_app logic:
        # len=2 -> has_applying=False -> R/U split.
        # 3 questions -> R=(3+1)//2 = 2. U=3-2=1.
        # Distribution: {"Remembering": 2, "Understanding": 1}
        
        print("Calling generate_questions...")
        response = await generate_questions(req)
        
        print(f"Response count: {len(response)}")
        
        # Verify generate_and_validate was called ONCE
        print(f"Call count: {mock_gen.call_count}")
        if mock_gen.call_count == 1:
            print("SUCCESS: generate_and_validate called exactly once.")
        else:
            print(f"FAILURE: generate_and_validate called {mock_gen.call_count} times.")
            
        # Verify inputs contained distribution
        call_args = mock_gen.call_args
        inputs_arg = call_args[0][2] # 3rd arg is inputs
        print(f"Inputs keys: {inputs_arg.keys()}")
        if "taxonomy_distribution" in inputs_arg:
            print(f"SUCCESS: taxonomy_distribution passed: {inputs_arg['taxonomy_distribution']}")
            expected_dist = {"Remembering": 2, "Understanding": 1}
            if inputs_arg['taxonomy_distribution'] == expected_dist:
                 print("SUCCESS: Distribution matches expected logic.")
            else:
                 print(f"FAILURE: Expected {expected_dist} but got {inputs_arg['taxonomy_distribution']}")
        else:
            print("FAILURE: taxonomy_distribution NOT found in inputs.")

        # Verify output taxonomy assignment
        r_tax = [r.get("taxonomy") for r in response] # response is list of dicts now? No, list of MCQQuestionResponse models? or dicts?
        # api_app returns list of dicts (converted from models by fastapi? No, just list of dicts constructed)
        # Wait, the code returns list of dicts (mcq_data).
        
        print(f"Result taxonomies: {[r['taxonomy'] for r in response]}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(verify_single_call())
    loop.close()
