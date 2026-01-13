from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
import yaml
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys
from src.services.generator import generate_and_validate, generate_and_validate_with_pdf, load_prompt_config
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
    PROMPT_CFG_PATH_PDF = CONFIG_DIR / "prompt_pdf.yaml"
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
    topic: str = Field(..., description="Topic/Core Skill - the specific skill to be tested")
    topic_id: int = Field(..., description="Topic/Section ID")
    domain: str = Field(..., description="Domain name")
    domain_id: int = Field(..., description="Domain ID")
    question_type: Literal["MCQ", "FIB"] = Field(..., description="Question type: MCQ or FIB")
    marks: int = Field(..., ge=1, le=10, description="Marks for the question (1-10)")
    taxonomy: List[Literal["Remembering", "Understanding", "Applying"]] = Field(
        ..., 
        min_length=1,
        max_length=3,
        description="List of taxonomy levels to include. Ratios: R+U=50-50, R/U+A=2:1, R+U+A=2:2:1"
    )
    taxonomy_id: int = Field(..., description="Bloom's Taxonomy ID")
    rigor_level: Literal["Level 1", "Level 2", "Level 3"] = Field(..., description="Rigor level")
    number_of_questions: int = Field(default=1, ge=1, le=20, description="Number of questions to generate")
    mathml: bool = Field(default=True, description="Include MathML in response (True/False)")
    new_concept: Optional[str] = Field(default=None, description="Concepts currently being learned (covered in this chapter)")
    old_concept: Optional[str] = Field(default=None, description="Prerequisite knowledge (concepts from previous chapters)")
    additional_notes: Optional[str] = Field(default=None, description="Extra instructions or configuration for generation")
    
    # New context fields for enhanced question generation
    standard: Optional[str] = Field(default=None, description="Primary curriculum standard and its description, e.g., 'Breaking numbers into H, T, and U components'")
    cognitive_skill: Optional[str] = Field(default=None, description="Required thinking skill, e.g., 'Decompose, Represent'")
    performance_expectation: Optional[str] = Field(default=None, description="What the student must demonstrate for mastery, e.g., 'Ability to break down numbers'")
    context_setting: Optional[str] = Field(default=None, description="Setting/tool the skill is applied within (CRITICAL for item design), e.g., 'Using visual aids like place value charts, number lines'")
    level_of_mastery: Optional[str] = Field(default=None, description="Expected speed and accuracy, e.g., 'Fluently'")
    actionable_skill_description: Optional[str] = Field(default=None, description="Detailed description of targeted skill, e.g., 'Identify face and place value of 2-digit numbers'")

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
                "domain": "Number",
                "domain_id": 1,
                "question_type": "FIB",
                "marks": 1,
                "taxonomy": ["Remembering", "Understanding"],
                "taxonomy_id": 1,
                "rigor_level": "Level 1",
                "number_of_questions": 4,
                "mathml": True,
                "new_concept": "Place value up to 1000",
                "old_concept": "Counting to 100",
                "additional_notes": "Avoid word problems",
                "standard": "Breaking numbers into H, T, and U components",
                "cognitive_skill": "Decompose, Represent",
                "performance_expectation": "Ability to break down numbers into place value components",
                "context_setting": "Using visual aids like place value charts, number lines",
                "level_of_mastery": "Fluently",
                "actionable_skill_description": "Identify face and place value of 2-digit numbers"
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
    domain: str
    domain_id: int
    question_type: str
    marks: int
    taxonomy: str
    taxonomy_id: int
    rigor_level: str
    
    # Context fields echoed back
    standard: Optional[str] = None
    cognitive_skill: Optional[str] = None
    performance_expectation: Optional[str] = None
    context_setting: Optional[str] = None
    level_of_mastery: Optional[str] = None
    actionable_skill_description: Optional[str] = None
    
    # Key takeaway - core learning point
    key_takeaway: Optional[str] = None
    
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
    domain: str
    domain_id: int
    question_type: str
    marks: int
    taxonomy: str
    taxonomy_id: int
    rigor_level: str
    
    # Context fields echoed back
    standard: Optional[str] = None
    cognitive_skill: Optional[str] = None
    performance_expectation: Optional[str] = None
    context_setting: Optional[str] = None
    level_of_mastery: Optional[str] = None
    actionable_skill_description: Optional[str] = None
    
    # Key takeaway - core learning point
    key_takeaway: Optional[str] = None
    
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
            "POST /generate-questions-pdf": "Generate educational questions from PDF",
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
    
    Taxonomy Distribution (based on selected levels):
    - R+U (Remembering + Understanding): 50-50 split
    - R/U + A (single + Applying): 2:1 ratio
    - R+U+A (all three): 2:2:1 ratio
    """
    logger.info(f"Question generation request received: {request.question_type} x{request.number_of_questions}")
    logger.info(f"Taxonomy levels: {request.taxonomy}")
    logger.debug(f"Request details: curriculum={request.curriculum}, grade={request.grade}, subject={request.subject}")
    
    try:
        # Calculate taxonomy distribution based on selected levels
        total_questions = request.number_of_questions
        taxonomy_distribution = {}
        selected_taxonomies = request.taxonomy
        
        if len(selected_taxonomies) == 1:
            # Only one taxonomy selected - all questions get that taxonomy
            taxonomy_distribution = {selected_taxonomies[0]: total_questions}
        
        elif len(selected_taxonomies) == 2:
            has_applying = "Applying" in selected_taxonomies
            
            if has_applying:
                # One of R/U + Applying: 2:1 ratio
                other_taxonomy = [t for t in selected_taxonomies if t != "Applying"][0]
                applying_count = max(1, total_questions // 3)
                other_count = total_questions - applying_count
                taxonomy_distribution = {
                    other_taxonomy: other_count,
                    "Applying": applying_count
                }
            else:
                # Remembering + Understanding: 50-50 split
                remembering_count = (total_questions + 1) // 2
                understanding_count = total_questions - remembering_count
                taxonomy_distribution = {
                    "Remembering": remembering_count,
                    "Understanding": understanding_count
                }
        
        else:  # len == 3, all three selected
            # R+U+A: 2:2:1 ratio
            applying_count = max(1, total_questions // 5)
            remaining = total_questions - applying_count
            remembering_count = (remaining + 1) // 2
            understanding_count = remaining - remembering_count
            taxonomy_distribution = {
                "Remembering": remembering_count,
                "Understanding": understanding_count,
                "Applying": applying_count
            }
        
        logger.info(f"Taxonomy distribution: {taxonomy_distribution}")
        
        all_valid_results = []
        taxonomy_assignments = []  # Track which taxonomy each result should have
        
        MAX_RETRIES = 3  # Maximum retry attempts per taxonomy level
        
        # Generate questions for each taxonomy level with retry logic
        for taxonomy_level, target_count in taxonomy_distribution.items():
            if target_count <= 0:
                continue
            
            valid_results_for_level = []
            remaining_count = target_count
            retry_count = 0
            
            while remaining_count > 0 and retry_count < MAX_RETRIES:
                if retry_count > 0:
                    logger.info(f"Retry {retry_count}/{MAX_RETRIES} for {taxonomy_level}: need {remaining_count} more question(s)")
                
                # Prepare inputs for the generator service
                inputs = {
                    "syllabus": request.curriculum,
                    "standard": request.grade,
                    "subject": request.subject,
                    "topic": request.chapter,
                    "section": request.topic,
                    "marks": request.marks,
                    "taxonomy": taxonomy_level,
                    "rigor": request.rigor_level,
                    "type": request.question_type,
                    "new_concept": request.new_concept,
                    "old_concept": request.old_concept,
                    "additional_notes": request.additional_notes,
                    # New context fields
                    "standard_desc": request.standard,
                    "cognitive_skill": request.cognitive_skill,
                    "performance_expectation": request.performance_expectation,
                    "context_setting": request.context_setting,
                    "level_of_mastery": request.level_of_mastery,
                    "actionable_skill_description": request.actionable_skill_description,
                    "previous_questions": "\n".join([f"[{q.get('type')}] {q.get('question_text')}" for q in all_valid_results]) if all_valid_results else "None",
                }
                
                logger.info(f"Calling generator service for {remaining_count} {request.question_type} question(s) at {taxonomy_level} level")
                
                # Call the existing generator service
                results, raw_response = generate_and_validate(
                    str(PROMPT_CFG_PATH),
                    APP_CFG['app'],
                    inputs,
                    remaining_count
                )
                
                logger.info(f"Generator returned {len(results)} result(s) for {taxonomy_level}")
                
                # Filter valid results from this batch
                for result in results:
                    if result.get("_error") or result.get("_parsing_error") or result.get("_validation_error"):
                        error_msg = result.get('_error') or result.get('_parsing_error') or result.get('_validation_error')
                        logger.warning(f"Invalid result for {taxonomy_level}: {error_msg}")
                        continue
                    valid_results_for_level.append(result)
                
                # Update remaining count
                remaining_count = target_count - len(valid_results_for_level)
                retry_count += 1
            
            logger.info(f"Final count for {taxonomy_level}: {len(valid_results_for_level)}/{target_count} valid question(s)")
            
            # Add valid results to the overall list
            for result in valid_results_for_level:
                all_valid_results.append(result)
                taxonomy_assignments.append(taxonomy_level)
        
        logger.info(f"Total valid results from all taxonomy levels: {len(all_valid_results)}")
        
        # Check if generation failed
        if not all_valid_results:
            logger.error("Question generation failed - no valid results returned after retries")
            raise HTTPException(
                status_code=500,
                detail="Question generation failed - no valid results returned after retries"
            )
        
        # Transform results to match API response format
        response_questions = []
        include_mathml = request.mathml
        logger.info(f"MathML output: {'enabled' if include_mathml else 'disabled'}")
        
        # All results in all_valid_results are already validated, no need to check for errors
        for idx, (result, assigned_taxonomy) in enumerate(zip(all_valid_results, taxonomy_assignments), 1):
            logger.debug(f"Processing result {idx}: {result.get('type', 'unknown')} question with taxonomy {assigned_taxonomy}")
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
                "domain": request.domain,
                "domain_id": request.domain_id,
                "question_type": request.question_type,
                "marks": request.marks,
                "taxonomy": assigned_taxonomy,  # Use the assigned taxonomy from distribution
                "taxonomy_id": request.taxonomy_id,
                "rigor_level": request.rigor_level,
                # Context fields echoed back
                "standard": request.standard,
                "cognitive_skill": request.cognitive_skill,
                "performance_expectation": request.performance_expectation,
                "context_setting": request.context_setting,
                "level_of_mastery": request.level_of_mastery,
                "actionable_skill_description": request.actionable_skill_description,
                "key_takeaway": result.get("key_takeaway"),  # New field from LLM
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
    topic: str = Form(..., description="Topic/Core Skill - the specific skill to be tested"),
    topic_id: int = Form(...),
    domain: str = Form(..., description="Domain name"),
    domain_id: int = Form(...),
    question_type: str = Form(..., description="MCQ or FIB"),
    marks: int = Form(..., ge=1, le=10),
    taxonomy: str = Form(..., description="Comma-separated taxonomy levels: 'Remembering,Understanding' or 'Remembering,Understanding,Applying'"),
    taxonomy_id: int = Form(...),
    rigor_level: str = Form(...),
    number_of_questions: int = Form(default=1, ge=1, le=20),
    mathml: bool = Form(default=True),
    old_concept: Optional[str] = Form(default=None),
    additional_notes: Optional[str] = Form(default=None),
    # New context fields
    standard: Optional[str] = Form(default=None, description="Primary curriculum standard"),
    cognitive_skill: Optional[str] = Form(default=None, description="Required thinking skill"),
    performance_expectation: Optional[str] = Form(default=None, description="What the student must demonstrate"),
    context_setting: Optional[str] = Form(default=None, description="Setting/tool the skill is applied within"),
    level_of_mastery: Optional[str] = Form(default=None, description="Expected speed and accuracy"),
    actionable_skill_description: Optional[str] = Form(default=None, description="Detailed skill description")
):
    """
    Generate educational questions based on PDF content and parameters.
    
    Taxonomy Distribution (based on selected levels):
    - R+U (Remembering + Understanding): 50-50 split
    - R/U + A (single + Applying): 2:1 ratio
    - R+U+A (all three): 2:2:1 ratio
    """
    logger.info(f"PDF Question generation request received: {question_type} x{number_of_questions}")
    logger.info(f"Taxonomy: {taxonomy}")
    logger.debug(f"Request details: curriculum={curriculum}, grade={grade}, subject={subject}")
    
    try:
        # Read PDF content
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Empty PDF file uploaded")
        
        # Parse taxonomy from comma-separated string
        selected_taxonomies = [t.strip() for t in taxonomy.split(",") if t.strip()]
        
        # Calculate taxonomy distribution based on selected levels
        total_questions = number_of_questions
        taxonomy_distribution = {}
        
        if len(selected_taxonomies) == 1:
            # Only one taxonomy selected - all questions get that taxonomy
            taxonomy_distribution = {selected_taxonomies[0]: total_questions}
        
        elif len(selected_taxonomies) == 2:
            has_applying = "Applying" in selected_taxonomies
            
            if has_applying:
                # One of R/U + Applying: 2:1 ratio
                other_taxonomy = [t for t in selected_taxonomies if t != "Applying"][0]
                applying_count = max(1, total_questions // 3)
                other_count = total_questions - applying_count
                taxonomy_distribution = {
                    other_taxonomy: other_count,
                    "Applying": applying_count
                }
            else:
                # Remembering + Understanding: 50-50 split
                remembering_count = (total_questions + 1) // 2
                understanding_count = total_questions - remembering_count
                taxonomy_distribution = {
                    "Remembering": remembering_count,
                    "Understanding": understanding_count
                }
        
        else:  # len >= 3, all three selected
            # R+U+A: 2:2:1 ratio
            applying_count = max(1, total_questions // 5)
            remaining = total_questions - applying_count
            remembering_count = (remaining + 1) // 2
            understanding_count = remaining - remembering_count
            taxonomy_distribution = {
                "Remembering": remembering_count,
                "Understanding": understanding_count,
                "Applying": applying_count
            }
        
        logger.info(f"Taxonomy distribution: {taxonomy_distribution}")
        
        all_valid_results = []
        taxonomy_assignments = []
        
        MAX_RETRIES = 3  # Maximum retry attempts per taxonomy level
        
        # Generate questions for each taxonomy level with retry logic
        for taxonomy_level, target_count in taxonomy_distribution.items():
            if target_count <= 0:
                continue
            
            valid_results_for_level = []
            remaining_count = target_count
            retry_count = 0
            
            while remaining_count > 0 and retry_count < MAX_RETRIES:
                if retry_count > 0:
                    logger.info(f"Retry {retry_count}/{MAX_RETRIES} for {taxonomy_level}: need {remaining_count} more question(s)")
                
                # Prepare inputs for the generator service
                inputs = {
                    "syllabus": curriculum,
                    "standard": grade,
                    "subject": subject,
                    "topic": chapter,
                    "section": topic,
                    "marks": marks,
                    "taxonomy": taxonomy_level,
                    "rigor": rigor_level,
                    "type": question_type,
                    "new_concept": "See attached PDF content",
                    "old_concept": old_concept,
                    "additional_notes": additional_notes,
                    # New context fields
                    "standard_desc": standard,
                    "cognitive_skill": cognitive_skill,
                    "performance_expectation": performance_expectation,
                    "context_setting": context_setting,
                    "level_of_mastery": level_of_mastery,
                    "actionable_skill_description": actionable_skill_description,
                    "previous_questions": "\n".join([f"[{q.get('type')}] {q.get('question_text')}" for q in all_valid_results]) if all_valid_results else "None",
                }
                
                logger.info(f"Calling PDF generator service for {remaining_count} {question_type} question(s) at {taxonomy_level} level")
                
                # Call the PDF generator service
                results, raw_response = generate_and_validate_with_pdf(
                    str(PROMPT_CFG_PATH_PDF),
                    APP_CFG['app'],
                    inputs,
                    remaining_count,
                    pdf_bytes
                )
                
                logger.info(f"Generator returned {len(results)} result(s) for {taxonomy_level}")
                
                # Filter valid results from this batch
                for result in results:
                    if result.get("_error") or result.get("_parsing_error") or result.get("_validation_error"):
                        error_msg = result.get('_error') or result.get('_parsing_error') or result.get('_validation_error')
                        logger.warning(f"Invalid result for {taxonomy_level}: {error_msg}")
                        continue
                    valid_results_for_level.append(result)
                
                # Update remaining count
                remaining_count = target_count - len(valid_results_for_level)
                retry_count += 1
            
            logger.info(f"Final count for {taxonomy_level}: {len(valid_results_for_level)}/{target_count} valid question(s)")
            
            # Add valid results to the overall list
            for result in valid_results_for_level:
                all_valid_results.append(result)
                taxonomy_assignments.append(taxonomy_level)
        
        logger.info(f"Total valid results from all taxonomy levels: {len(all_valid_results)}")
        
        # Check if generation failed
        if not all_valid_results:
            logger.error("Question generation failed - no valid results returned after retries")
            raise HTTPException(
                status_code=500,
                detail="Question generation failed - no valid results returned after retries"
            )
        
        # Transform results to match API response format
        response_questions = []
        include_mathml = mathml
        
        # All results in all_valid_results are already validated, no need to check for errors
        for idx, (result, assigned_taxonomy) in enumerate(zip(all_valid_results, taxonomy_assignments), 1):
            logger.debug(f"Processing result {idx}: {result.get('type', 'unknown')} question with taxonomy {assigned_taxonomy}")
            
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
                "domain": domain,
                "domain_id": domain_id,
                "question_type": question_type,
                "marks": marks,
                "taxonomy": assigned_taxonomy,  # Use the assigned taxonomy from distribution
                "taxonomy_id": taxonomy_id,
                "rigor_level": rigor_level,
                # Context fields echoed back
                "standard": standard,
                "cognitive_skill": cognitive_skill,
                "performance_expectation": performance_expectation,
                "context_setting": context_setting,
                "level_of_mastery": level_of_mastery,
                "actionable_skill_description": actionable_skill_description,
                "key_takeaway": result.get("key_takeaway"),  # New field from LLM
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
