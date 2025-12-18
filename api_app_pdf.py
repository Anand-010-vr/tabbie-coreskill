from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
import yaml
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys
from src.services.generator import generate_and_validate_with_pdf
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
    title="Core Skills Question Generator API (PDF Support)",
    description="API for generating educational questions from PDF content",
    version="1.0.0"
)
logger.info("FastAPI application initialized")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS middleware enabled")

# Load configuration
BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
try:
    APP_CFG = yaml.safe_load(open(CONFIG_DIR / "app.yaml", "r", encoding="utf-8"))
    PROMPT_CFG_PATH = CONFIG_DIR / "prompt_pdf.yaml"
    logger.info(f"Configuration loaded from {CONFIG_DIR}")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise

# ===========================
# Response Models
# ===========================

class AIMeta(BaseModel):
    prompt_version: str
    model: str
    generated_at: str

class MCQQuestionResponse(BaseModel):
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
    
    question_text: str
    solution_text: str
    options: List[str]
    correct_option: int
    status: str
    ai_meta: AIMeta
    
    question_mathml: Optional[str] = None
    solution_mathml: Optional[str] = None
    options_mathml: Optional[List[str]] = None

class FIBQuestionResponse(BaseModel):
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
    
    question_text: str
    solution_text: str
    accepted_answers: str
    status: str
    ai_meta: AIMeta
    
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
        "name": "Core Skills Question Generator API (PDF)",
        "version": "1.0.0",
        "endpoints": {
            "POST /generate-questions-pdf": "Generate educational questions from PDF",
            "GET /health": "Health check endpoint"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.info("Health check endpoint accessed")
    return {"status": "healthy"}

@app.post("/generate-questions-pdf")
async def generate_questions_pdf(
    file: UploadFile = File(...),
    curriculum: str = Form(...),
    curriculum_id: int = Form(...),
    grade: str = Form(...),
    grade_id: int = Form(...),
    subject: str = Form(...),
    subject_id: int = Form(...),
    chapter: str = Form(...),
    chapter_id: int = Form(...),
    topic: str = Form(...),
    topic_id: int = Form(...),
    question_type: str = Form(..., description="MCQ or FIB"),
    marks: int = Form(..., ge=1, le=10),
    taxonomy: str = Form(...),
    rigor_level: str = Form(...),
    number_of_questions: int = Form(default=1, ge=1, le=10),
    mathml: bool = Form(default=True),
    old_concept: Optional[str] = Form(default=None),
    additional_notes: Optional[str] = Form(default=None)
):
    """
    Generate educational questions based on PDF content and parameters.
    """
    logger.info(f"PDF Question generation request received: {question_type} x{number_of_questions}")
    logger.debug(f"Request details: curriculum={curriculum}, grade={grade}, subject={subject}")
    
    try:
        # Read PDF content
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Empty PDF file uploaded")
            
        # Prepare inputs for the generator service
        inputs = {
            "syllabus": curriculum,
            "standard": grade,
            "subject": subject,
            "topic": chapter,
            "section": topic,
            "marks": marks,
            "taxonomy": taxonomy,
            "rigor": rigor_level,
            "type": question_type,
            "new_concept": "See attached PDF content",
            "old_concept": old_concept,
            "additional_notes": additional_notes,
        }
        
        logger.info(f"Calling PDF generator service for {number_of_questions} {question_type} question(s)")
        
        # Call the new PDF generator service
        results, raw_response = generate_and_validate_with_pdf(
            str(PROMPT_CFG_PATH),
            APP_CFG['app'],
            inputs,
            number_of_questions,
            pdf_bytes
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
        include_mathml = mathml
        
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
            
            base_fields = {
                "curriculum": curriculum,
                "curriculum_id": curriculum_id,
                "grade": grade,
                "grade_id": grade_id,
                "subject": subject,
                "subject_id": subject_id,
                "chapter": chapter,
                "chapter_id": chapter_id,
                "topic": topic,
                "topic_id": topic_id,
                "question_type": question_type,
                "marks": marks,
                "taxonomy": taxonomy,
                "rigor_level": rigor_level,
                "status": result.get("status", "Unknown"),
                "ai_meta": result.get("ai_meta", {
                    "prompt_version": "unknown",
                    "model": "unknown",
                    "generated_at": ""
                })
            }
            
            if question_type == "MCQ":
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
                
                if include_mathml:
                    mcq_data["question_mathml"] = result.get("question_mathml", "")
                    mcq_data["solution_mathml"] = result.get("solution_mathml", "")
                    mcq_data["options_mathml"] = result.get("options", [])
                
                response_questions.append(mcq_data)
                
            elif question_type == "FIB":
                fib_data = {
                    **base_fields,
                    "question_text": result.get("question_text") or mathml_to_text(result.get("question_mathml", "")),
                    "solution_text": result.get("solution_text") or mathml_to_text(result.get("solution_mathml", "")),
                    "accepted_answers": result.get("accepted_answers", "")
                }
                
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
        raise
    except Exception as e:
        logger.exception(f"Unexpected error in question generation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
