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

def calculate_taxonomy_distribution(total_questions: int, selected_taxonomies: List[str]):
    taxonomy_distribution = {}
    
    if not selected_taxonomies:
        return {}

    if len(selected_taxonomies) == 1:
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
    
    return taxonomy_distribution

def display_question_card(result: Dict[str, Any], idx: int, include_mathml: bool):
    st.markdown(f"### Question {idx} ({result.get('taxonomy', 'N/A')})")
    
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
        if result.get("type", "MCQ") == "MCQ" or "options" in result:
            st.warning("**Options**")
            options = result.get("options", [])
            correct_idx = result.get("correct_option", 1)
            
            for i, opt in enumerate(options, 1):
                is_correct = " (Correct ✅)" if i == correct_idx else ""
                st.write(f"**{i}.** {opt}{is_correct}")
            
            if include_mathml and result.get("options_mathml"):
                st.markdown("**Raw Options MathML:**")
                st.code("\n".join(result.get("options_mathml", [])), language="xml")
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
    api_key_input = st.text_input("Gemini API Key", value=os.environ.get("GEMINI_API_KEY", ""), type="password", help="Enter your Gemini API key here. It will be used for the current session.")
    
    if api_key_input:
        os.environ["GEMINI_API_KEY"] = api_key_input
    
    st.divider()
    
    mode = st.radio("Generation Mode", ["Standard", "PDF-based"])
    
    if mode == "Standard":
        # Standard input fields
        curriculum = st.text_input("Curriculum", "UK National Curriculum")
        grade = st.selectbox("Grade", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"], index=3)
        subject = st.text_input("Subject", "Maths")
        chapter = st.text_input("Chapter", "Number – number and place value")
        topic = st.text_input("Topic/Core Skill", "count from 0 in multiples of 4, 8, 50 and 100")
        domain = st.text_input("Domain", "Number")
    else:
        # PDF upload
        uploaded_file = st.file_uploader("Upload PDF Reference", type="pdf")
        curriculum = st.text_input("Curriculum", "UK National Curriculum")
        grade = st.selectbox("Grade", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"], index=3)
        subject = st.text_input("Subject", "Maths")
        chapter = st.text_input("Chapter", "Custom Chapter")
        topic = st.text_input("Topic", "Custom Topic")
        domain = st.text_input("Domain", "Custom Domain")

    st.divider()
    
    q_type = st.selectbox("Question Type", ["MCQ", "FIB"])
    num_questions = st.slider("Number of Questions", 1, 10, 1)
    marks = st.number_input("Marks", 1, 10, 1)
    
    taxonomy_options = ["Remembering", "Understanding", "Applying"]
    selected_taxonomies = st.multiselect("Taxonomy Levels", taxonomy_options, default=["Remembering", "Understanding"])
    
    rigor = st.selectbox("Rigor Level", ["Level 1", "Level 2", "Level 3"])
    include_mathml = st.checkbox("Enable MathML Output (Raw Display)", value=True)
    
    st.divider()
    
    # Context fields (showing directly now)
    st.subheader("Advanced Context")
    standard_desc = st.text_area("Standard Description")
    cognitive_skill = st.text_input("Cognitive Skill")
    performance_expectation = st.text_area("Performance Expectation")
    context_setting = st.text_input("Context Setting")
    level_of_mastery = st.text_input("Level of Mastery")
    actionable_skill = st.text_area("Actionable Skill Description")
    additional_notes = st.text_area("Additional Notes")

    generate_btn = st.button("Generate Questions", type="primary", use_container_width=True)

# Main Area
if generate_btn:
    if not selected_taxonomies:
        st.error("Please select at least one taxonomy level.")
    elif mode == "PDF-based" and not uploaded_file:
        st.error("Please upload a PDF file.")
    else:
        with st.spinner("Generating questions..."):
            dist = calculate_taxonomy_distribution(num_questions, selected_taxonomies)
            all_results = []
            
            inputs = {
                "syllabus": curriculum,
                "standard": grade,
                "subject": subject,
                "topic": chapter,
                "section": topic,
                "marks": int(marks),
                "rigor": rigor,
                "type": q_type,
                "additional_notes": additional_notes,
                "standard_desc": standard_desc,
                "cognitive_skill": cognitive_skill,
                "performance_expectation": performance_expectation,
                "context_setting": context_setting,
                "level_of_mastery": level_of_mastery,
                "actionable_skill_description": actionable_skill,
            }

            try:
                placeholder = st.empty()
                progress_bar = st.progress(0)
                total_taxonomies = len(dist)
                
                for i, (tax_level, count) in enumerate(dist.items()):
                    if count <= 0: continue
                    
                    placeholder.text(f"Generating {count} questions for {tax_level}...")
                    
                    level_inputs = inputs.copy()
                    level_inputs["taxonomy"] = tax_level
                    
                    if mode == "Standard":
                        results, raw = generate_and_validate(
                            str(PROMPT_CFG_PATH),
                            APP_CFG['app'],
                            level_inputs,
                            count
                        )
                    else:
                        pdf_bytes = uploaded_file.read()
                        level_inputs["new_concept"] = "See attached PDF content"
                        results, raw = generate_and_validate_with_pdf(
                            str(PROMPT_CFG_PATH_PDF),
                            APP_CFG['app'],
                            level_inputs,
                            count,
                            pdf_bytes
                        )
                    
                    # Filter and add tax level info
                    for r in results:
                        if not any(k in r for k in ["_error", "_parsing_error", "_validation_error"]):
                            r["taxonomy"] = tax_level
                            all_results.append(r)
                    
                    progress_bar.progress((i + 1) / total_taxonomies)
                
                placeholder.empty()
                progress_bar.empty()

                if not all_results:
                    st.error("Failed to generate any valid questions. Please check the logs or try different parameters.")
                else:
                    st.success(f"Generated {len(all_results)} questions successfully!")
                    
                    # Download button
                    json_str = json.dumps(all_results, indent=2)
                    st.download_button(
                        label="Download Results (JSON)",
                        data=json_str,
                        file_name="generated_questions.json",
                        mime="application/json"
                    )

                    st.divider()
                    
                    # Display results
                    for idx, res in enumerate(all_results, 1):
                        display_question_card(res, idx, include_mathml)
                        st.divider()

            except Exception as e:
                st.exception(e)
                logger.exception(f"Error in Streamlit app: {e}")

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
