import asyncio
from unittest.mock import MagicMock, patch
import api_app
from api_app import generate_questions, QuestionGenerationRequest

# Mock APP_CFG and PROMPT_CFG_PATH
api_app.APP_CFG = {'app': {}}
api_app.PROMPT_CFG_PATH = "dummy_path"
api_app.logger = MagicMock()

async def verify_batching():
    print("Verifying proactive batching logic...")
    
    # We want 16 questions. BATCH_SIZE is 5 inside api_app.
    # We expect 4 calls: 5, 5, 5, 1.
    
    # Mock generator
    # It needs to return a list of dummy results equal to 'n' requested
    def side_effect(prompt_path, app_cfg, inputs, n):
        # inputs has 'taxonomy_distribution'.
        # We simulate returning valid questions matching that distribution
        results = []
        dist = inputs.get("taxonomy_distribution", {})
        count = 0
        for tax, needed in dist.items():
            for _ in range(needed):
                results.append({"taxonomy": tax, "type": "MCQ", "question_text": f"Q{count}"})
                count += 1
        return results, "raw"

    with patch('api_app.generate_and_validate', side_effect=side_effect) as mock_gen:
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
            taxonomy=["Remembering", "Understanding"], 
            taxonomy_id=1,
            rigor_level="Level 1",
            number_of_questions=16, # Requesting 16
            mathml=False
        )
        
        # taxonomy list len=2 -> R/U split. 16 -> 8 Remembering, 8 Understanding.
        
        print("Calling generate_questions with N=16...")
        response = await generate_questions(req)
        
        print(f"Total Response count: {len(response)}")
        
        # Verify call count
        print(f"Generator call count: {mock_gen.call_count}")
        
        expected_calls = 4 # 5, 5, 5, 1
        if mock_gen.call_count == expected_calls:
             print("SUCCESS: batching split request into correct number of calls.")
        else:
             print(f"FAILURE: Expected {expected_calls} calls, got {mock_gen.call_count}")

            
        # Optional: verify args of each call
        # Call 1: n=5
        # Call 2: n=5
        # Call 3: n=5
        # Call 4: n=1
        
        calls = mock_gen.call_args_list
        ns = [c[0][3] for c in calls] # 4th arg is n
        print(f"Batch sizes requested: {ns}")
        
        if ns == [5, 5, 5, 1]:
            print("SUCCESS: Batch sizes are correct.")
        else:
            print(f"FAILURE: Batch sizes incorrect. Expected [5, 5, 5, 1]")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(verify_batching())
    loop.close()
