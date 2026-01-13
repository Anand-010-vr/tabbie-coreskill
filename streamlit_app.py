import streamlit as st
import yaml
import json
import os
from pathlib import Path
from dotenv import load_dotenv
import logging
import sys
from typing import List, Dict, Any, Optional

# Add current directory to path if needed for relative imports
sys.path.append(str(Path(__file__).parent))

from src.services.generator import generate_and_validate, generate_and_validate_with_pdf, load_prompt_config
from src.services.render_utils import mathml_to_text, render_mathml_html

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Core Skills Question Generator",
    page_icon="📚",
    layout="wide"
)

# Load configuration
BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"

@st.cache_data
def load_config():
    try:
        app_cfg = yaml.safe_load(open(CONFIG_DIR / "app.yaml", "r", encoding="utf-8"))
        return app_cfg
    except Exception as e:
        st.error(f"Failed to load configuration: {e}")
        return None

APP_CFG = load_config()
PROMPT_CFG_PATH = CONFIG_DIR / "prompt.yaml"
PROMPT_CFG_PATH_PDF = CONFIG_DIR / "prompt_pdf.yaml"

# Question classification definitions
QUESTION_CLASSIFICATIONS = {
    "Number-Based Remembering": {
        "key": "number_remembering",
        "taxonomy": "Remembering",
        "description": "Pure numerical recall or direct calculation"
    },
    "Number-Based Understanding": {
        "key": "number_understanding",
        "taxonomy": "Understanding",
        "description": "Numerical comprehension requiring interpretation"
    },
    "Image-Based Remembering": {
        "key": "image_remembering",
        "taxonomy": "Remembering",
        "description": "Questions referencing visual elements with direct recall"
    },
    "Real-Life Image Based": {
        "key": "real_life_image",
        "taxonomy": "Understanding",
        "description": "Real-world visual scenarios"
    },
    "Word Problems (Understanding)": {
        "key": "word_understanding",
        "taxonomy": "Understanding",
        "description": "Text-based problems requiring comprehension"
    },
    "Word Problems (Applying)": {
        "key": "word_applying",
        "taxonomy": "Applying",
        "description": "Text-based problems requiring application"
    },
    "Word Problems + Images (Understanding)": {
        "key": "word_image_understanding",
        "taxonomy": "Understanding",
        "description": "Combined text and visual elements for understanding"
    },
    "Word Problems + Images (Applying)": {
        "key": "word_image_applying",
        "taxonomy": "Applying",
        "description": "Combined text and visual elements for application"
    }
}

def get_classification_distribution(classification_counts: Dict[str, int]) -> Dict[str, int]:
    """Return only classifications with count > 0."""
    return {k: v for k, v in classification_counts.items() if v > 0}

def display_question_card(result: Dict[str, Any], idx: int, include_mathml: bool):
    classification = result.get('classification', 'N/A')
    taxonomy = result.get('taxonomy', 'N/A')
    q_type = result.get("type", "MCQ")
    st.markdown(f"### Question {idx}: {classification} ({q_type} - {taxonomy})")
    
    if result.get("creation_logic") or result.get("validation_reasoning"):
        with st.expander("🔍 AI Reasoning & Validation", expanded=False):
            if result.get("creation_logic"):
                st.info(f"**Creation Logic:** {result.get('creation_logic')}")
            if result.get("validation_reasoning"):
                status = result.get("validation_status", "CHECKED")
                color = "green" if status == "APPROVED" else "orange"
                st.markdown(f":{color}[**Validation ({status}):**] {result.get('validation_reasoning')}")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info("**Question Text**")
        q_text = result.get("question_text") or mathml_to_text(result.get("question_mathml", ""))
        st.write(q_text)
        
        if include_mathml and result.get("question_mathml"):
            st.markdown("**Raw Question MathML:**")
            st.code(result.get("question_mathml"), language="xml")

        st.success("**Solution**")
        s_text = result.get("solution_text") or mathml_to_text(result.get("solution_mathml", ""))
        st.write(s_text)
        
        if include_mathml and result.get("solution_mathml"):
            st.markdown("**Raw Solution MathML:**")
            st.code(result.get("solution_mathml"), language="xml")

    with col2:
        if q_type == "MCQ" or "options" in result:
            st.warning("**Options**")
            
            # Show readable options
            options_text = []
            for i in range(1, 5):
                opt_key = f"options_text_{i}"
                if opt_key in result:
                    options_text.append(result[opt_key])
            
            # Fallback to MathML list if text fields missing (shouldn't happen with new schema)
            if not options_text and "options" in result:
                 options_text = result["options"]

            correct_idx = result.get("correct_option", 1)
            
            for i, opt in enumerate(options_text, 1):
                is_correct = " (Correct ✅)" if i == correct_idx else ""
                
                # Distractor Analysis
                dist_key = f"distractor_analysis_{i}"
                dist_analysis = result.get(dist_key, "")
                dist_display = f"\n*Analysis: {dist_analysis}*" if dist_analysis else ""
                
                st.write(f"**{i}.** {opt}{is_correct}{dist_display}")
            
            # Only show MathML options if enabled
            if include_mathml and "options" in result:
                st.markdown("**Raw Options MathML:**")
                # Ensure options is a list before joining
                opts = result.get("options", [])
                if isinstance(opts, list):
                    st.code("\n".join(opts), language="xml")
                else:
                    st.code(str(opts), language="xml")
        else:
            st.warning("**Accepted Answers**")
            st.write(result.get("accepted_answers", "N/A"))
            
            if include_mathml and result.get("accepted_answers_mathml"):
                st.markdown("**Raw Accepted Answers MathML:**")
                st.code(result.get("accepted_answers_mathml"), language="xml")
        
        if result.get("key_takeaway"):
            st.markdown("---")
            st.markdown(f"**Key Takeaway:** {result.get('key_takeaway')}")

# --- UI Layout ---

st.title("📚 Core Skills Question Generator")
st.markdown("Generate high-quality educational questions using AI.")

with st.sidebar:
    st.header("Configuration")
    
    # API Key Provision
    st.subheader("Authentication")
    if "api_key" not in st.session_state:
        # Default to environment variable if set (e.g. via Streamlit Secrets), but don't persist back to it
        st.session_state.api_key = os.environ.get("GEMINI_API_KEY", "")
        
    api_key_input = st.text_input(
        "Gemini API Key", 
        value=st.session_state.api_key, 
        type="password", 
        help="Enter your Gemini API key here. It will be used ONLY for your current session and will not be shared with other users."
    )
    
    # Update session state with manual input
    st.session_state.api_key = api_key_input
    
    st.divider()
    
    # Core Metadata
    curriculum = st.text_input("Curriculum", "UK National Curriculum")
    grade = st.selectbox("Grade", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"], index=3)
    subject = st.text_input("Subject", "Maths")
    domain = st.text_input("Domain", "Number")
    chapter = st.text_input("Chapter(Learning Outcome)", "Number – number and place value")
    topic = st.text_input("Topic/Core Skill", "count from 0 in multiples of 4, 8, 50 and 100")
    
    st.divider()

    # Advanced Context
    standard_desc = st.text_area("Standard")
    cognitive_skill = st.text_input("Cognitive Skill")
    performance_expectation = st.text_area("Performance Expectation")
    context_setting = st.text_input("Context Setting")
    level_of_mastery = st.text_input("Level of Mastery")
    
    st.divider()

    # Question Parameters
    marks = st.number_input("Marks (per question)", 1, 10, 1)
    rigor = st.selectbox("Rigor Level", ["Level 1", "Level 2", "Level 3"])
    include_mathml = st.checkbox("Enable MathML Output (Raw Display)", value=True)
    
    st.divider()
    
    # Question Classifications - users select how many of each type
    st.subheader("Question Classifications")
    st.caption("Enter the number of questions for each classification (75% MCQ / 25% FIB auto-applied)")
    
    classification_counts = {}
    for class_name, class_info in QUESTION_CLASSIFICATIONS.items():
        classification_counts[class_name] = st.number_input(
            f"{class_name}",
            min_value=0, max_value=20, value=0,
            help=class_info["description"],
            key=class_info["key"]
        )
    
    st.divider()

    # Generation Mode and Conditional Inputs
    mode = st.radio("Generation Mode", ["Standard", "PDF-based"])
    
    uploaded_file = None
    new_concept = ""
    
    if mode == "Standard":
        new_concept = st.text_area("New Concept (Current Topic)")
    else:
        uploaded_file = st.file_uploader("Upload PDF Reference", type="pdf")
    
    old_concept = st.text_area("Old Concept (Prerequisite Knowledge)")
    additional_notes = st.text_area("Additional Notes")

    generate_btn = st.button("Generate Questions", type="primary", use_container_width=True)

# Main Area
if "all_results" not in st.session_state:
    st.session_state.all_results = []
if "strategy_logic" not in st.session_state:
    st.session_state.strategy_logic = {}
if "final_prompt" not in st.session_state:
    st.session_state.final_prompt = ""

if generate_btn:
    # Gets triggered only on button click
    
    # Get classifications with count > 0
    active_classifications = get_classification_distribution(classification_counts)
    total_questions = sum(active_classifications.values())
    
    if total_questions == 0:
        st.error("Please select at least one question classification with a count greater than 0.")
    elif mode == "PDF-based" and not uploaded_file:
        st.error("Please upload a PDF file.")
    else:
        with st.spinner("Generating questions..."):
            # Create a session-safe app config copy
            call_app_cfg = APP_CFG['app'].copy()
            if st.session_state.get("api_key"):
                call_app_cfg['gemini_api_key'] = st.session_state.api_key

            # Clear previous results
            st.session_state.all_results = []
            st.session_state.strategy_logic = {}
            st.session_state.final_prompt = ""
            
            # Base inputs (without classification-specific fields)
            base_inputs = {
                "syllabus": curriculum,
                "standard": grade,
                "subject": subject,
                "topic": chapter,
                "section": topic,  # This is the Topic/Core Skill - PRIMARY CONTEXT
                "marks": int(marks),
                "rigor": rigor,
                "new_concept": new_concept if mode == "Standard" else None,
                "old_concept": old_concept,
                "cognitive_skill": cognitive_skill,
                "additional_notes": additional_notes,
                "standard_desc": standard_desc,
                "performance_expectation": performance_expectation,
                "context_setting": context_setting,
                "level_of_mastery": level_of_mastery,
            }

            try:
                placeholder = st.empty()
                progress_bar = st.progress(0)
                total_classifications = len(active_classifications)
                
                # Read PDF once if in PDF mode
                pdf_bytes = None
                if mode == "PDF-based" and uploaded_file:
                    pdf_bytes = uploaded_file.read()
                
                # Context accumulator for cross-call variation
                previous_questions_summary = []
                
                # Store the last prompt used for display
                last_prompt_used = ""

                for i, (classification_name, count) in enumerate(active_classifications.items()):
                    if count <= 0: 
                        continue
                    
                    class_info = QUESTION_CLASSIFICATIONS[classification_name]
                    placeholder.text(f"Generating {count} questions for {classification_name}...")
                    
                    # Build inputs for this classification
                    classification_inputs = base_inputs.copy()
                    classification_inputs["classification"] = classification_name
                    classification_inputs["taxonomy"] = class_info["taxonomy"]
                    
                    # Inject previously generated questions context
                    if previous_questions_summary:
                        classification_inputs["previous_questions"] = "\n".join(previous_questions_summary)
                    
                    # Collection for this classification
                    classification_results = []
                    attempts = 0
                    max_attempts = 5  # Safety break
                    
                    while len(classification_results) < count and attempts < max_attempts:
                        needed = count - len(classification_results)
                        attempts += 1
                        
                        if attempts > 1:
                            placeholder.text(f"Retry {attempts-1}: Generating {needed} more questions for {classification_name}...")
                        
                        if mode == "Standard":
                            results, strategy, raw, prompt_text = generate_and_validate(
                                str(PROMPT_CFG_PATH),
                                call_app_cfg,
                                classification_inputs,
                                needed
                            )
                        else:
                            classification_inputs["new_concept"] = "See attached PDF content"
                            results, strategy, raw, prompt_text = generate_and_validate_with_pdf(
                                str(PROMPT_CFG_PATH_PDF),
                                call_app_cfg,
                                classification_inputs,
                                needed,
                                pdf_bytes
                            )
                        
                        # Capture prompt and strategy
                        last_prompt_used = prompt_text
                        if strategy and not st.session_state.strategy_logic:
                            # Only capture the first strategy object found (or merge if needed, but first is usually best)
                            st.session_state.strategy_logic = strategy
                        
                        # Filter valid results and add to collection
                        for r in results:
                            if not any(k in r for k in ["_error", "_parsing_error", "_validation_error"]):
                                r["classification"] = classification_name
                                r["taxonomy"] = class_info["taxonomy"]
                                classification_results.append(r)
                                
                                # Add this question to the summary for future context
                                # Format: [Type] Question Text
                                q_summary = f"[{r.get('type', 'N/A')}] {r.get('question_text', '')}" 
                                previous_questions_summary.append(q_summary)
                                
                        # Update context for next iteration within the loop
                        classification_inputs["previous_questions"] = "\n".join(previous_questions_summary) if previous_questions_summary else "None"
                    
                    # Add collected valid results to main list
                    st.session_state.all_results.extend(classification_results)
                    
                    if len(classification_results) < count:
                        st.warning(f"Could only generate {len(classification_results)}/{count} valid questions for {classification_name} after {attempts} attempts.")
                    
                    progress_bar.progress((i + 1) / total_classifications)
                
                placeholder.empty()
                progress_bar.empty()
                
                st.session_state.final_prompt = last_prompt_used

            except Exception as e:
                st.exception(e)
                logger.exception(f"Error in Streamlit app: {e}")

# Display Logic (Outside the button check so it persists)
if st.session_state.all_results:
    st.success(f"Generated {len(st.session_state.all_results)} questions successfully!")
    
    # Stratgey Logic Display
    if st.session_state.strategy_logic:
        st.markdown("### 🧠 Generation Logic")
        st.markdown("How the model applied Bloom's Taxonomy for this specific core skill:")
        
        sl = st.session_state.strategy_logic
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("**Remembering Strategy**")
            st.write(sl.get("remembering_logic", "N/A"))
        with c2:
            st.warning("**Understanding Strategy**")
            st.write(sl.get("understanding_logic", "N/A"))
        with c3:
            st.error("**Applying Strategy**")
            st.write(sl.get("applying_logic", "N/A"))
        st.divider()

    # Download button
    json_str = json.dumps(st.session_state.all_results, indent=2)
    st.download_button(
        label="Download Results (JSON)",
        data=json_str,
        file_name="generated_questions.json",
        mime="application/json"
    )

    st.divider()
    
    # Display results
    for idx, res in enumerate(st.session_state.all_results, 1):
        display_question_card(res, idx, include_mathml)
        st.divider()
        
    # Final Prompt Display
    if st.session_state.final_prompt:
        with st.expander("🔌 View Final Prompt (Debug)", expanded=False):
            st.code(st.session_state.final_prompt, language="markdown")
elif generate_btn and not st.session_state.all_results: 
     # Only show failure if button was clicked and no results were found (and exception didn't stop execution)
     # This assumes the try/except block handles critical failures, this handles logical empty results
     st.error("Failed to generate any valid questions. Please check the logs or try different parameters.")


else:
    st.info("Configure the parameters in the sidebar and click 'Generate Questions' to start.")
    
    # Placeholder for how it looks
    st.image("https://streamlit.io/images/brand/streamlit-mark-color.png", width=100)
    st.markdown("""
    ### How to use:
    1. **Choose Mode**: 'Standard' for general curriculum-based generation, or 'PDF-based' to upload a reference document.
    2. **Set Parameters**: Fill in Curriculum, Grade, Subject, etc.
    3. **Select Taxonomy**: Choose the Bloom's Taxonomy levels you want to target.
    4. **Generate**: Click the big blue button!
    """)
