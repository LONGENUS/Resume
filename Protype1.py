#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# streamlit_app.py

import streamlit as st
from pathlib import Path
import requests
import re
import docx
import PyPDF2
from jinja2 import Template
import pdfkit
import time
from bs4 import BeautifulSoup

# --- Configuration ---
MISTRAL_API_KEY = "ELO6G5Sa9by0FCWCwtrFxkmKyY1gFs7l"
WKHTMLTOPDF_PATH = r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"

# --- Helpers ---
def extract_text_from_pdf(file) -> str:
    reader = PyPDF2.PdfReader(file)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def extract_text_from_docx(file) -> str:
    doc = docx.Document(file)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

def call_mistral_api(prompt: str, model: str = "mistral-medium") -> str:
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a professional resume reviewer and job alignment expert."},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
    return response.json()["choices"][0]["message"]["content"]

def generate_analysis_prompt(resume_text: str, job_description: str) -> str:
    return f"""
You are an expert resume analyst. Analyze the resume and job description below.

Provide a structured response with the following sections:
1. **Missing Technical/Domain-Specific Keywords**
2. **Actionable Suggestions**
3. **ATS Match Score**

---
📄 Resume:
{resume_text}

📌 Job Description:
{job_description}
"""

def extract_missing_keywords(text: str):
    match = re.search(r"Missing.*?Keywords.*?:?\s*(.*?)(?:\n\s*\d\.\s*Actionable|\Z)", text, re.DOTALL)
    if match:
        lines = match.group(1).splitlines()
        return [line.strip("-• ") for line in lines if line.strip().startswith(("-", "•"))]
    return []

def build_resume_prompt(resume_text, keywords, confirmed):
    lines = "\n".join([f"- **{k}**: {v}" for k, v in confirmed.items()])
    enriched_resume = resume_text + ("\n\nAdditional Experience:\n" + lines if lines else "")
    return f"""
You are a resume enhancement expert.

Original Resume:
---
{enriched_resume}
---

Task:
1. Include the following missing keywords in **bold**: {', '.join(keywords)}
2. Organize into clear sections: Summary, Skills, Experience
3. Use bullet points. Maintain a professional tone.
"""

def render_html(resume_text):
    html_template = Template("""
    <html><head><style>
    body { font-family: Arial; margin: 40px; }
    .resume { border: 1px solid #ccc; padding: 20px; border-radius: 10px; max-width: 800px; }
    pre { white-space: pre-wrap; }
    </style></head><body>
    <div class='resume'><pre>{{ resume }}</pre></div></body></html>
    """)
    return html_template.render(resume=resume_text)

def clean_html(input_html):
    soup = BeautifulSoup(input_html, "html.parser")
    text = soup.find("pre").get_text()
    soup.find("pre").string = text.replace("*", "")
    return str(soup)

def convert_to_pdf(html_content, output_path):
    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
    with open("temp.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    pdfkit.from_file("temp.html", output_path, configuration=config)

# --- Streamlit UI ---
st.set_page_config(page_title="AI Resume Analyzer", layout="centered")
st.title("📄 AI Resume Analyzer & Enhancer")

input_method = st.radio("Choose resume input method:", ["Upload PDF/DOCX", "Manual Entry"])
resume_text = ""

if input_method == "Upload PDF/DOCX":
    uploaded_file = st.file_uploader("Upload Resume (PDF or DOCX)", type=["pdf", "docx"])
    if uploaded_file:
        if uploaded_file.name.endswith(".pdf"):
            resume_text = extract_text_from_pdf(uploaded_file)
        else:
            resume_text = extract_text_from_docx(uploaded_file)
else:
    summary = st.text_area("Professional Summary")
    skills = st.text_input("Skills (comma separated)")
    experience = st.text_area("Work Experience")
    resume_text = f"Professional Summary:\n{summary}\n\nSkills:\n{skills}\n\nExperience:\n{experience}"

job_description = st.text_area("Paste Job Description")

if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "missing_keywords" not in st.session_state:
    st.session_state.missing_keywords = []
if "confirmed" not in st.session_state:
    st.session_state.confirmed = {}
if "ready_to_enhance" not in st.session_state:
    st.session_state.ready_to_enhance = False

if st.button("🔍 Analyze Resume") and resume_text and job_description:
    with st.spinner("Analyzing with Mistral..."):
        prompt = generate_analysis_prompt(resume_text, job_description)
        analysis = call_mistral_api(prompt)
        st.session_state.analysis = analysis
        st.session_state.missing_keywords = extract_missing_keywords(analysis)
        st.session_state.confirmed = {}
        st.session_state.ready_to_enhance = False

if st.session_state.analysis:
    st.subheader("🧠 Resume Analysis")
    st.markdown(st.session_state.analysis)

    if st.session_state.missing_keywords:
        st.subheader("📌 Confirm Experience for Missing Keywords")
        for kw in st.session_state.missing_keywords:
            with st.expander(f"Do you have experience with '{kw}'?"):
                choice = st.radio("Experience?", ["Yes", "No"], key=f"radio_{kw}")
                if choice == "Yes":
                    desc = st.text_area("Describe your experience:", key=f"desc_{kw}")
                    if desc.strip():
                        st.session_state.confirmed[kw] = desc.strip()

    if st.button("✅ Confirm & Enhance Resume"):
        st.session_state.ready_to_enhance = True

if st.session_state.ready_to_enhance:
    st.subheader("✨ Enhancing Resume...")
    prompt = build_resume_prompt(resume_text, st.session_state.missing_keywords, st.session_state.confirmed)
    progress = st.progress(0, text="Calling Mistral...")
    for i in range(1, 6):
        time.sleep(0.2)
        progress.progress(i * 20)
    enhanced = call_mistral_api(prompt)
    progress.progress(100, text="Done!")

    st.subheader("✅ Enhanced Resume")
    st.text_area("Preview", enhanced, height=400)

    html = render_html(enhanced)
    cleaned = clean_html(html)
    Path("enhanced_resume_cleaned.html").write_text(cleaned, encoding="utf-8")

    convert_to_pdf(cleaned, "enhanced_resume.pdf")
    with open("enhanced_resume.pdf", "rb") as f:
        st.download_button("📥 Download Enhanced Resume (PDF)", f, file_name="enhanced_resume.pdf")

