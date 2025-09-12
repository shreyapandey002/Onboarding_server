from fastapi import FastAPI, UploadFile, Form
import os
from typing import Dict
import shutil

app = FastAPI()

# Required docs
required_docs = ["aadhar", "pan", "release_letter"]

# In-memory tracking
collected_info: Dict[str, Dict[str, bool]] = {}

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/init_user/")
async def init_user(email: str = Form(...)):
    folder = os.path.join(UPLOAD_DIR, email)
    os.makedirs(folder, exist_ok=True)
    collected_info[email] = {doc: False for doc in required_docs}
    return {"status": "initialized", "required_docs": required_docs}


@app.post("/upload_doc/")
async def upload_doc(
    email: str = Form(...), doc_type: str = Form(...), file: UploadFile = None
):
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

    # Mark document as collected
    collected_info[email][normalized_doc] = True

    # Check missing docs
    missing = [doc for doc, done in collected_info[email].items() if not done]

    if not missing:
        # Instead of sending email, signal orchestrator
        return {
            "status": "ready_for_email",
            "email": email,
            "attachments": [
                os.path.join(folder, f"{doc}.pdf") for doc in required_docs
            ],
        }

    return {"status": "incomplete", "missing_docs": missing, "next_doc": missing[0]}
