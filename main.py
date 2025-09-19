from fastapi import FastAPI, UploadFile, Form
import os
import json
import shutil
from typing import Dict
import smtplib
from email.message import EmailMessage

app = FastAPI()

# Required documents
required_docs = ["aadhar", "pan", "release_letter"]

# JSON file for persistent tracking
COLLECTED_JSON = "collected_info.json"

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def load_collected_info() -> Dict[str, Dict[str, bool]]:
    if os.path.exists(COLLECTED_JSON):
        with open(COLLECTED_JSON, "r") as f:
            return json.load(f)
    return {}


def save_collected_info(collected_info: Dict[str, Dict[str, bool]]):
    with open(COLLECTED_JSON, "w") as f:
        json.dump(collected_info, f)


@app.post("/init_user/")
async def init_user(email: str = Form(...)):
    """
    Initialize a new onboarding session for a user.
    """
    collected_info = load_collected_info()

    folder = os.path.join(UPLOAD_DIR, email)
    os.makedirs(folder, exist_ok=True)

    if email not in collected_info:
        collected_info[email] = {doc: False for doc in required_docs}
        save_collected_info(collected_info)

    return {"status": "initialized", "required_docs": required_docs, "next_doc": required_docs[0]}


@app.post("/upload_doc/")
async def upload_doc(
    email: str = Form(...), doc_type: str = Form(...), file: UploadFile = None
):
    """
    Upload a document for a user.
    """
    collected_info = load_collected_info()

    if email not in collected_info:
        return {"status": "error", "message": "User not initialized"}

    if not file:
        return {"status": "error", "message": "No file uploaded"}

    # Normalize doc_type (case-insensitive)
    doc_map = {doc.lower(): doc for doc in required_docs}
    normalized_doc = doc_map.get(doc_type.strip().lower())

    if not normalized_doc:
        return {
            "status": "error",
            "message": f"Unknown document type '{doc_type}'. Provide one of {required_docs}",
        }

    # Save uploaded file
    folder = os.path.join(UPLOAD_DIR, email)
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"{normalized_doc}.pdf")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Mark document as collected and save to JSON
    collected_info[email][normalized_doc] = True
    save_collected_info(collected_info)

    # Determine missing documents
    missing_docs = [doc for doc, done in collected_info[email].items() if not done]

    # Build doc status map (Completed/Incompleted)
    doc_status = {
        doc: ("completed" if done else "incompleted")
        for doc, done in collected_info[email].items()
    }

    if not missing_docs:
        # All docs collected → send email
        await send_email(email, folder)

        # Cleanup
        shutil.rmtree(folder)
        del collected_info[email]
        save_collected_info(collected_info)

        return {
            "status": "complete",
            "message": "All documents received. Email sent.",
            "doc_status": doc_status,
        }

    # Return next document to prompt user for
    next_doc = missing_docs[0]
    return {
        "status": "incomplete",
        "message": f"{normalized_doc} uploaded successfully.",
        "missing_docs": missing_docs,
        "next_doc": next_doc,
        "doc_status": doc_status,
    }


async def send_email(user_email: str, folder: str):
    """
    Send an email to HR with all uploaded documents attached.
    """
    hr_email = "shreya.p@nighthack.in"
    msg = EmailMessage()
    msg["From"] = "noreply@example.com"
    msg["To"] = hr_email
    msg["Cc"] = "shreya.p@nighthack.in"
    msg["Subject"] = f"New Employee Onboarding - {user_email}"
    msg.set_content(f"All required documents for {user_email} have been collected and are attached.")

    # Attach all PDFs in the folder
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        with open(filepath, "rb") as fp:
            msg.add_attachment(fp.read(), maintype="application", subtype="pdf", filename=filename)

    # Mailtrap SMTP (blocking, suitable for small apps)
    with smtplib.SMTP("sandbox.smtp.mailtrap.io", 2525) as s:
        s.login("b6c2a4b4798d4f", "fad68538a2eee8")
        s.send_message(msg)
