from fastapi import FastAPI, UploadFile, Form
import os
from typing import Dict
import smtplib
from email.message import EmailMessage
import shutil

app = FastAPI()

# Only these 3 docs are required now
required_docs = ["aadhar", "pan", "release_letter"]

# In-memory tracking (replace with Redis/DB if needed)
collected_info: Dict[str, Dict[str, bool]] = {}

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/init_user/")
async def init_user(email: str = Form(...)):
    folder = os.path.join(UPLOAD_DIR, email)
    os.makedirs(folder, exist_ok=True)
    collected_info[email] = {doc: False for doc in required_docs}
    return {"status": "initialized", "required": required_docs}

@app.post("/upload_doc/")
async def upload_doc(email: str = Form(...), doc_type: str = Form(...), file: UploadFile = None):
    if email not in collected_info:
        return {"status": "error", "message": "User not initialized"}

    # Normalize doc_type (case-insensitive)
    doc_map = {doc: doc for doc in required_docs}
    normalized_doc = doc_map.get(doc_type.strip().lower())

    if not normalized_doc:
        return {"status": "error", "message": f"Unknown document type '{doc_type}'. Please provide one of {required_docs}"}

    folder = os.path.join(UPLOAD_DIR, email)
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"{normalized_doc}.pdf")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Mark document as collected
    collected_info[email][normalized_doc] = True

    # Check missing docs
    missing = [doc for doc, done in collected_info[email].items() if not done]

    if not missing:
        # All documents collected → send email and delete folder
        await send_email(email, folder)
        shutil.rmtree(folder)
        del collected_info[email]
        return {"status": "complete", "message": "All documents received. Email sent."}

    return {"status": "incomplete", "missing": missing, "next_doc": missing[0]}

async def send_email(user_email, folder):
    hr_email = "shreya.p@nighthack.in"
    msg = EmailMessage()
    msg["From"] = "noreply@example.com"
    msg["To"] = hr_email
    msg["Cc"] = "shreya.p@nighthack.in"
    msg["Subject"] = f"New Employee Onboarding - {user_email}"
    msg.set_content(f"All required documents for {user_email} have been collected and are attached.")

    # Attach PDFs
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        with open(filepath, "rb") as fp:
            msg.add_attachment(fp.read(), maintype="application", subtype="pdf", filename=filename)

    # Mailtrap SMTP
    with smtplib.SMTP("sandbox.smtp.mailtrap.io", 2525) as s:
        s.login("b6c2a4b4798d4f", "fad68538a2eee8")
        s.send_message(msg)
