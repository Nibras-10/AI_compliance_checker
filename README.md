# AI Compliance Checker

Analyze contracts and policies for missing clauses and compliance risks. This Streamlit app extracts text from uploaded documents and asks an LLM to produce a structured JSON list of issues, then computes a simple compliance score and generates a PDF report.



## Features

- Upload PDF, DOCX, or TXT
- Local text extraction (PyPDF2, python-docx)
- Clear analysis prompt tailored by industry (General, Banking, Healthcare, IT, Legal)
- Model output expected as JSON list of issues with keys:
  - `section`, `risk`, `explanation`, `risk_level` (High/Medium/Low)
- Robust JSON recovery when the model returns extra text or trailing commas
- Compliance score with weighted penalties and counts by risk level
- Color-coded issue list in the UI
- One-click PDF report download
- Developer toggle to show sanitized debug output (model “thoughts”/reasoning is stripped and hidden by default)

## Quickstart (Windows PowerShell)

```powershell
# 1) Create and activate a virtual environment (optional but recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -r requirements.txt

# 3) Set your Hugging Face token for this session
$env:HF_TOKEN = "hf_xxx_your_token_here"

# 4) Run the app
streamlit run app.py
```

Open the local URL printed by Streamlit (typically http://localhost:8501).

### Streamlit Cloud

- Go to Settings → Secrets and add:
  - `HF_TOKEN = "hf_xxx_your_token_here"`

## Configuration

- Environment variable: `HF_TOKEN`
  - Required to access the Hugging Face Router or Inference APIs.
- Sidebar options:
  - Industry selector
  - Developer toggle to show sanitized raw output

## How it works

- `app.py` handles the UI, file parsing, prompt building, model call, JSON parsing, scoring, and PDF generation.
- The model call uses the Hugging Face Router chat completions endpoint and the MiniMax model `MiniMaxAI/MiniMax-M2:novita` by default.
- The app asks the model to return ONLY JSON. A resilient parser then extracts/repairs the JSON if the response includes extra prose, code fences, smart quotes, or trailing commas.
- A score is computed (High=25, Medium=10, Low=3, plus a small volume penalty) and a PDF report is created.



## Troubleshooting

- "Hugging Face HF_TOKEN not found": set `$env:HF_TOKEN` in PowerShell or add it to Streamlit Secrets in the cloud.
- "Could not parse JSON from model output": The parser is robust but not perfect. Try clicking Analyze again or reducing document size. You can enable the developer toggle to inspect a sanitized preview of the output.
- Cold starts can take 10–90 seconds depending on the model and infrastructure.
- Large files: Keep under ~20 pages for the best results; only the first chunk is sent to the model.

## Project structure

```
app.py            # Streamlit app and model integration
requirements.txt  # Python dependencies
```

## Dependencies

- streamlit
- requests
- PyPDF2
- python-docx
- reportlab

Install them with:

```powershell
pip install -r requirements.txt
```

## Security & privacy

- Your HF token is used only to call the selected Hugging Face endpoint.
- Do not commit tokens to version control. Prefer Streamlit Secrets or environment variables.
- The app strips and hides any model “thoughts”/reasoning from the user interface by default.

## License

Add your preferred license here (MIT/Apache-2.0/etc.).
