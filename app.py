# app.py
import os
import streamlit as st
import requests
import PyPDF2
from docx import Document
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import json
import re

# ------------------- CONFIG -------------------
st.set_page_config(page_title="AI Compliance Checker", page_icon="🧾", layout="wide")

# Read HF token from Streamlit secrets (recommended for Streamlit Cloud)
# In Streamlit Cloud: Settings -> Secrets -> add HF_TOKEN = "hf_xxx..."
try:
    HF_TOKEN = st.secrets["HF_TOKEN"]
except Exception:
    HF_TOKEN = os.environ.get("HF_TOKEN")

# Use Hugging Face Router (OpenAI-compatible) to access MiniMax chat model
API_URL = "https://router.huggingface.co/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}

# ------------------- HELPERS -------------------
def query_chat(messages, max_tokens=1024, temperature=0.0):
    """
    Query MiniMax via Hugging Face Router (OpenAI-compatible /v1/chat/completions).
    messages: list of {role, content}
    Returns the assistant message content (string) or best-effort text.
    """
    payload = {
        "model": "MiniMaxAI/MiniMax-M2:novita",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=120)
    try:
        data = resp.json()
    except Exception:
        return resp.text

    # OpenAI-style response handling
    if isinstance(data, dict) and "choices" in data and data["choices"]:
        choice = data["choices"][0] or {}
        # Some routers use choice["message"]["content"]
        if isinstance(choice, dict) and "message" in choice:
            msg = choice.get("message") or {}
            content = msg.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                # Join text parts if returned as a list of segments
                parts = []
                for seg in content:
                    if isinstance(seg, dict) and seg.get("type") == "text":
                        parts.append(seg.get("text", ""))
                    elif isinstance(seg, str):
                        parts.append(seg)
                if parts:
                    return "".join(parts)
        # Fallbacks sometimes provide 'text'
        if isinstance(choice, dict) and "text" in choice:
            return choice["text"]
    # Last resort: return JSON string
    return json.dumps(data) if isinstance(data, (dict, list)) else str(data)

def extract_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(uploaded_file)
        pages = []
        for p in reader.pages:
            try:
                text = p.extract_text()
                if text:
                    pages.append(text)
            except Exception:
                continue
        return "\n".join(pages)
    elif name.endswith(".docx"):
        doc = Document(uploaded_file)
        return "\n".join([para.text for para in doc.paragraphs])
    else:
        # txt or fallback
        raw = uploaded_file.read()
        try:
            return raw.decode("utf-8", errors="ignore")
        except Exception:
            return str(raw)

def find_json_in_text(s: str):
    """
    Try to find JSON array/object in the generated text and parse it.
    Returns parsed JSON or None.
    """
    # Try direct parse first
    try:
        return json.loads(s)
    except Exception:
        pass
    # Try to extract the first JSON array/object within text using regex
    patterns = [
        r"(\[.*\])",  # JSON array
        r"(\{.*\})"   # JSON object
    ]
    for pat in patterns:
        match = re.search(pat, s, re.DOTALL)
        if match:
            candidate = match.group(1)
            # Try to fix trailing commas and parse
            try:
                return json.loads(candidate)
            except Exception:
                # attempt simple cleanup
                cleaned = re.sub(r",\s*}", "}", candidate)
                cleaned = re.sub(r",\s*\]", "]", cleaned)
                try:
                    return json.loads(cleaned)
                except Exception:
                    continue
    return None

def risk_icon(level: str):
    l = (level or "").strip().lower()
    if l == "high":
        return "🔴"
    if l == "medium":
        return "🟠"
    return "🟢"

def compute_compliance_score(issues):
    """
    Simple weighted scoring:
    - High risk: 25 points penalty each
    - Medium risk: 10 points penalty each
    - Low risk: 3 points penalty each
    Score = 100 - total_penalty, clamped to [0,100]
    Also small penalty for many issues (to avoid 100 when many low risks)
    """
    high = sum(1 for i in issues if i.get("risk_level","").strip().lower()=="high")
    med = sum(1 for i in issues if i.get("risk_level","").strip().lower()=="medium")
    low = sum(1 for i in issues if i.get("risk_level","").strip().lower()=="low")
    penalty = high*25 + med*10 + low*3
    # extra penalty for sheer volume
    penalty += max(0, len(issues)-5) * 1
    score = max(0, 100 - penalty)
    return score, {"high": high, "medium": med, "low": low, "total": len(issues)}

def generate_pdf(report_data, compliance_score, filename="compliance_report.pdf"):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_x = 50
    y = height - 80

    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin_x, y, "AI Compliance Report")
    c.setFont("Helvetica", 12)
    y -= 30
    c.drawString(margin_x, y, f"Overall Compliance Score: {compliance_score}/100")
    y -= 20
    c.drawString(margin_x, y, f"Issues found: {len(report_data)}")
    y -= 30

    for issue in report_data:
        if y < 100:
            c.showPage()
            y = height - 80
        section = issue.get("section", "N/A")
        risk = issue.get("risk", "N/A")
        level = issue.get("risk_level", "N/A")
        explanation = issue.get("explanation", "N/A")

        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin_x, y, f"• {risk} ({level})")
        y -= 16
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(margin_x + 10, y, f"Section: {section}")
        y -= 14
        c.setFont("Helvetica", 10)
        # wrap explanation
        text_lines = []
        line = ""
        for word in explanation.split():
            if len(line) + len(word) + 1 > 90:
                text_lines.append(line)
                line = word
            else:
                line = (line + " " + word).strip()
        if line:
            text_lines.append(line)
        for ln in text_lines:
            c.drawString(margin_x + 10, y, ln)
            y -= 12
        y -= 10

    c.save()
    buffer.seek(0)
    return buffer

# ------------------- UI -------------------
st.title("🧾 AI Compliance Checker (IBM Granite)")
st.write("Analyze contracts and policies for missing clauses and compliance risks. Uses IBM Granite via Hugging Face Inference API.")

if not HF_TOKEN:
    st.warning("Hugging Face HF_TOKEN not found in `st.secrets` or environment. Add HF_TOKEN before using the app.")
    st.write("In Streamlit Cloud: Settings → Secrets → add `HF_TOKEN = \"hf_xxx...\"` — or set an environment variable HF_TOKEN on your machine.")
    # still allow demo with a placeholder but will not work
    # return early? Continue but model calls will fail.
    
industry = st.sidebar.selectbox("Select Industry Type:", ["General", "Banking", "Healthcare", "IT", "Legal"])
st.sidebar.markdown("---")
st.sidebar.markdown("⚙️ This demo uses the `ibm-granite/granite-13b-instruct` model via Hugging Face Inference API.")
st.sidebar.markdown("Tip: Keep documents under ~20 pages for best results. The app sends the first chunk of the document to the model.")

uploaded_file = st.file_uploader("Upload a document (.pdf, .docx, .txt)", type=["pdf", "docx", "txt"])

if uploaded_file:
    with st.spinner("Extracting text..."):
        text = extract_text(uploaded_file)
    st.subheader("Document preview (truncated)")
    st.write(text[:4000] + ("...\n\n(document truncated for analysis)" if len(text) > 4000 else ""))

    # Build prompt (truncated to first 6000 chars to control cost and latency)
    truncated_text = text[:6000]
    base_prompt = f"""
You are a senior compliance auditor specialized in {industry} domain.
Analyze the document text below for missing, weak, or risky clauses (for example: confidentiality, data protection, liability, indemnity, termination, audit rights, regulatory obligations).
For each issue you find, return a JSON array of objects with EXACT keys:
- section: short descriptor or snippet of the document (or 'Missing <clause>' if absent)
- risk: one-line description of the issue
- explanation: a short paragraph explaining why this is risky or non-compliant
- risk_level: one of ["High","Medium","Low"]

Return ONLY JSON. Example output:
[
  {{
    "section": "Confidentiality - missing",
    "risk": "Missing confidentiality clause",
    "explanation": "No clause ensures confidentiality, which risks data leakage of sensitive customer information.",
    "risk_level": "High"
  }},
  ...
]

Document (begin):
{truncated_text}
Document (end).
If no issues are found, return an empty JSON array: []
"""
    st.write("")  # spacing
    if st.button("🔍 Analyze with Granite"):
        with st.spinner("Contacting Granite model (may take ~10-90s on cold start)..."):
            try:
                # Send previous prompt as a single user message to chat endpoint
                messages = [
                    {"role": "user", "content": base_prompt}
                ]
                raw = query_chat(messages, max_tokens=1024, temperature=0.0)
            except Exception as e:
                st.error("Model query failed: " + str(e))
                raw = None

        if raw is None:
            st.error("No response from model.")
        else:
            st.subheader("Raw model output (first 2000 chars) — for debugging")
            st.text(raw[:2000])

            parsed = find_json_in_text(raw)
            if parsed is None:
                st.error("Could not parse JSON from model output. Try simplifying the document or re-running.")
                st.write("Model output (full):")
                st.code(raw)
            else:
                # Expecting a list
                issues = parsed if isinstance(parsed, list) else [parsed]
                score, counts = compute_compliance_score(issues)
                st.metric("Overall Compliance Score", f"{score}/100")
                st.write(f"Issues — High: {counts['high']} • Medium: {counts['medium']} • Low: {counts['low']} • Total: {counts['total']}")

                # Display issues color-coded
                for idx, issue in enumerate(issues, start=1):
                    level = issue.get("risk_level", "Low")
                    icon = risk_icon(level)
                    st.markdown(f"### {icon} {issue.get('risk', 'Unnamed issue')}")
                    col1, col2 = st.columns([3,1])
                    with col1:
                        st.markdown(f"**Section:** {issue.get('section', 'N/A')}")
                        st.markdown(f"**Explanation:** {issue.get('explanation', 'N/A')}")
                    with col2:
                        l = (level or "").strip().lower()
                        if l == "high":
                            st.markdown("<div style='font-weight:bold; color:#b00020;'>High</div>", unsafe_allow_html=True)
                        elif l == "medium":
                            st.markdown("<div style='font-weight:bold; color:#e65c00;'>Medium</div>", unsafe_allow_html=True)
                        else:
                            st.markdown("<div style='font-weight:bold; color:#2e7d32;'>Low</div>", unsafe_allow_html=True)
                    st.markdown("---")

                # PDF generation and download
                pdf_buffer = generate_pdf(issues, score)
                st.download_button(
                    label="📥 Download Compliance Report (PDF)",
                    data=pdf_buffer,
                    file_name="compliance_report.pdf",
                    mime="application/pdf"
                )

                # Show JSON result & offer copy
                st.subheader("Structured JSON output")
                st.json(issues)
