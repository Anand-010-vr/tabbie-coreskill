from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
import yaml
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys
from src.services.generator import generate_and_validate, load_prompt_config
from src.services.render_utils import mathml_to_text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

# Initialize FastAPI app
app = FastAPI(
    title="Core Skills Question Generator API",
    description="API for generating educational questions with MathML support",
    version="1.0.0"
)
logger.info("FastAPI application initialized")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins - for production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
logger.info("CORS middleware enabled")

# Load configuration
BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
try:
    APP_CFG = yaml.safe_load(open(CONFIG_DIR / "app.yaml", "r", encoding="utf-8"))
    PROMPT_CFG_PATH = CONFIG_DIR / "prompt.yaml"
    logger.info(f"Configuration loaded from {CONFIG_DIR}")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise

# ===========================
# Request Models
# ===========================

class QuestionGenerationRequest(BaseModel):
    curriculum: str = Field(..., description="Curriculum name")
    curriculum_id: int = Field(..., description="Curriculum ID")
    grade: str = Field(..., description="Grade/Standard name")
    grade_id: int = Field(..., description="Grade/Standard ID")
    subject: str = Field(..., description="Subject name")
    subject_id: int = Field(..., description="Subject ID")
    chapter: str = Field(..., description="Chapter name")
    chapter_id: int = Field(..., description="Chapter ID")
    topic: str = Field(..., description="Topic/Section name")
    topic_id: int = Field(..., description="Topic/Section ID")
    question_type: Literal["MCQ", "FIB"] = Field(..., description="Question type: MCQ or FIB")
    marks: int = Field(..., ge=1, le=10, description="Marks for the question (1-10)")
    taxonomy: Literal["Remembering", "Understanding", "Applying", "Analyzing", "Evaluating", "Creating"] = Field(
        ..., description="Bloom's Taxonomy level"
    )
    rigor_level: Literal["Level 1", "Level 2", "Level 3"] = Field(..., description="Rigor level")
    number_of_questions: int = Field(default=1, ge=1, le=10, description="Number of questions to generate")
    mathml: bool = Field(default=True, description="Include MathML in response (True/False)")
    new_concept: Optional[str] = Field(default=None, description="Concepts currently being learned (covered in this chapter)")
    old_concept: Optional[str] = Field(default=None, description="Prerequisite knowledge (concepts from previous chapters)")
    additional_notes: Optional[str] = Field(default=None, description="Extra instructions or configuration for generation")

    class Config:
        json_schema_extra = {
            "example": {
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
                "mathml": True,
                "new_concept": "Place value up to 1000",
                "old_concept": "Counting to 100",
                "additional_notes": "Avoid word problems"
            }
        }

# ===========================
# Response Models
# ===========================

class AIMeta(BaseModel):
    prompt_version: str
    model: str
    generated_at: str

class MCQQuestionResponse(BaseModel):
    # Input fields echoed back
    curriculum: str
    curriculum_id: int
    grade: str
    grade_id: int
    subject: str
    subject_id: int
    chapter: str
    chapter_id: int
    topic: str
    topic_id: int
    question_type: str
    marks: int
    taxonomy: str
    rigor_level: str
    
    # Generated content
    question_text: str
    solution_text: str
    options: List[str]  # Array of 4 text options
    correct_option: int  # 1-4
    status: str
    ai_meta: AIMeta
    
    # Optional MathML fields
    question_mathml: Optional[str] = None
    solution_mathml: Optional[str] = None
    options_mathml: Optional[List[str]] = None  # Array of 4 MathML options

class FIBQuestionResponse(BaseModel):
    # Input fields echoed back
    curriculum: str
    curriculum_id: int
    grade: str
    grade_id: int
    subject: str
    subject_id: int
    chapter: str
    chapter_id: int
    topic: str
    topic_id: int
    question_type: str
    marks: int
    taxonomy: str
    rigor_level: str
    
    # Generated content
    question_text: str
    solution_text: str
    accepted_answers: str
    status: str
    ai_meta: AIMeta
    
    # Optional MathML fields
    question_mathml: Optional[str] = None
    solution_mathml: Optional[str] = None
    accepted_answers_mathml: Optional[str] = None

# ===========================
# Endpoints
# ===========================

@app.get("/")
async def root():
    """Root endpoint with API information"""
    logger.info("Root endpoint accessed")
    return {
        "name": "Core Skills Question Generator API",
        "version": "1.0.0",
        "endpoints": {
            "POST /generate-questions": "Generate educational questions",
            "GET /health": "Health check endpoint"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.info("Health check endpoint accessed")
    return {"status": "healthy"}

@app.post("/generate-questions")
async def generate_questions(request: QuestionGenerationRequest):
    """
    Generate educational questions based on curriculum parameters.
    
    Returns an array of question objects, which can be either MCQ or FIB type.
    MathML fields are included only if mathml=True in the request.
    """
    logger.info(f"Question generation request received: {request.question_type} x{request.number_of_questions}")
    logger.debug(f"Request details: curriculum={request.curriculum}, grade={request.grade}, subject={request.subject}")
    
    try:
        # Prepare inputs for the generator service
        inputs = {
            "syllabus": request.curriculum,
            "standard": request.grade,
            "subject": request.subject,
            "topic": request.chapter,
            "section": request.topic,
            "marks": request.marks,
            "taxonomy": request.taxonomy,
            "rigor": request.rigor_level,
            "rigor": request.rigor_level,
            "type": request.question_type,
            "new_concept": request.new_concept,
            "old_concept": request.old_concept,
            "additional_notes": request.additional_notes,
        }
        
        logger.info(f"Calling generator service for {request.number_of_questions} {request.question_type} question(s)")
        
        # Call the existing generator service
        results, raw_response = generate_and_validate(
            str(PROMPT_CFG_PATH),
            APP_CFG['app'],
            inputs,
            request.number_of_questions
        )
        
        logger.info(f"Generator returned {len(results)} result(s)")
        
        # Check if generation failed
        if not results:
            logger.error("Question generation failed - no results returned")
            raise HTTPException(
                status_code=500,
                detail="Question generation failed - no results returned"
            )
        
        # Transform results to match API response format
        response_questions = []
        include_mathml = request.mathml
        logger.info(f"MathML output: {'enabled' if include_mathml else 'disabled'}")
        
        for idx, result in enumerate(results, 1):
            # Skip error entries
            if result.get("_error") or result.get("_parsing_error"):
                logger.warning(f"Skipping result {idx} due to error: {result.get('_error') or result.get('_parsing_error')}")
                continue
            
            # Skip validation errors
            if result.get("_validation_error"):
                logger.warning(f"Skipping result {idx} due to validation error: {result.get('_validation_error')}")
                continue
            
            logger.debug(f"Processing result {idx}: {result.get('type', 'unknown')} question")
            # Base fields that are always included
            base_fields = {
                "curriculum": request.curriculum,
                "curriculum_id": request.curriculum_id,
                "grade": request.grade,
                "grade_id": request.grade_id,
                "subject": request.subject,
                "subject_id": request.subject_id,
                "chapter": request.chapter,
                "chapter_id": request.chapter_id,
                "topic": request.topic,
                "topic_id": request.topic_id,
                "question_type": request.question_type,
                "marks": request.marks,
                "taxonomy": request.taxonomy,
                "rigor_level": request.rigor_level,
                "status": result.get("status", "Unknown"),
                "ai_meta": result.get("ai_meta", {
                    "prompt_version": "unknown",
                    "model": "unknown",
                    "generated_at": ""
                })
            }
            
            if request.question_type == "MCQ":
                # Extract text versions of options
                options_text = []
                for i in range(1, 5):
                    opt_text = result.get(f"options_text_{i}")
                    if not opt_text:
                        # Fallback: convert from MathML if available
                        options_arr = result.get("options", [])
                        if len(options_arr) >= i:
                            opt_text = mathml_to_text(options_arr[i-1])
                        else:
                            opt_text = ""
                    options_text.append(opt_text)
                
                mcq_data = {
                    **base_fields,
                    "question_text": result.get("question_text") or mathml_to_text(result.get("question_mathml", "")),
                    "solution_text": result.get("solution_text") or mathml_to_text(result.get("solution_mathml", "")),
                    "options": options_text,
                    "correct_option": result.get("correct_option", 1)
                }
                
                # Add MathML fields if requested
                if include_mathml:
                    mcq_data["question_mathml"] = result.get("question_mathml", "")
                    mcq_data["solution_mathml"] = result.get("solution_mathml", "")
                    mcq_data["options_mathml"] = result.get("options", [])
                
                response_questions.append(mcq_data)
                
            elif request.question_type == "FIB":
                fib_data = {
                    **base_fields,
                    "question_text": result.get("question_text") or mathml_to_text(result.get("question_mathml", "")),
                    "solution_text": result.get("solution_text") or mathml_to_text(result.get("solution_mathml", "")),
                    "accepted_answers": result.get("accepted_answers", "")
                }
                
                # Add MathML fields if requested
                if include_mathml:
                    fib_data["question_mathml"] = result.get("question_mathml", "")
                    fib_data["solution_mathml"] = result.get("solution_mathml", "")
                    fib_data["accepted_answers_mathml"] = result.get("accepted_answers", "")
                
                response_questions.append(fib_data)
        
        # Check if we have any valid questions
        if not response_questions:
            logger.error("No valid questions produced after filtering errors")
            raise HTTPException(
                status_code=500,
                detail="Question generation succeeded but no valid questions were produced. Check validation errors."
            )
        
        logger.info(f"Successfully generated {len(response_questions)} valid question(s)")
        return response_questions
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Catch any other errors and return as 500
        logger.exception(f"Unexpected error in question generation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# ===========================
# Error Handlers
# ===========================

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
