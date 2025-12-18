# Core Skills QGen (no DB)

Minimal Streamlit app to generate UK National Curriculum core-skill questions using Google Gemini (via google-genai).

Quick start:
1. Create venv and install:
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt

2. Put year markdown files in `config/topics/`, e.g. `config/topics/year3.md`.

3. (Optional) Run loader to build consolidated topics JSON:
   python src/services/topic_loader.py

4. Set GEMINI_API_KEY in your environment:
   export GEMINI_API_KEY="YOUR_KEY"    # PowerShell: setx GEMINI_API_KEY "YOUR_KEY"

5. Turn off mock mode in `config/app.yaml` when ready.

6. Run:
   streamlit run app.py

Notes:
- The app expects the model to return newline-delimited JSON objects. Keep temperature low.
- No DB in this scaffold; generated outputs are saved to `outputs/`.
