from fastapi import FastAPI, UploadFile, Form
import os
import shutil
from typing import List
from email.message import EmailMessage
import requests
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()

# Required documents
required_docs = ["aadhar", "pan", "release_letter"]

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -----------------------------
#   COMPOSIO CONFIG
# -----------------------------
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
BASE_URL = "https://backend.composio.dev/api/v3"
GMAIL_CONNECTED_ACCOUNT_ID = os.getenv("GMAIL_CONNECTED_ACCOUNT_ID")


def send_email_via_composio_single(to_email: str, subject: str, html_body: str):
    """
    Sends ONE email at a time using Composio Gmail.
    """
    payload = {
        "connected_account_id": GMAIL_CONNECTED_ACCOUNT_ID,
        "arguments": {
            "recipient_email": to_email,
            "subject": subject,
            "body": html_body,
            "is_html": True
        }
    }

    endpoint = f"{BASE_URL}/tools/execute/GMAIL_SEND_EMAIL"

    res = requests.post(
        endpoint,
        json=payload,
        headers={"x-api-key": COMPOSIO_API_KEY},
        timeout=60
    )

    return res.status_code, res.json()


# -----------------------------
#   ROUTES
# -----------------------------
@app.post("/init_user/")
async def init_user(email: str = Form(...)):
    folder = os.path.join(UPLOAD_DIR, email)
    os.makedirs(folder, exist_ok=True)

    uploaded_docs = [
        doc.split(".pdf")[0]
        for doc in os.listdir(folder)
        if doc.endswith(".pdf") and doc.split(".pdf")[0] in required_docs
    ]

    missing_docs = [doc for doc in required_docs if doc not in uploaded_docs]

    return {
        "status": "initialized",
        "required_docs": required_docs,
        "next_doc": missing_docs[0] if missing_docs else None,
        "uploaded_docs": uploaded_docs,
        "missing_docs": missing_docs,
    }


@app.post("/upload_doc/")
async def upload_doc(
    email: str = Form(...),
    doc_type: str = Form(...),
    file: UploadFile = None
):
    folder = os.path.join(UPLOAD_DIR, email)

    if not os.path.exists(folder):
        return {"status": "error", "message": "User not initialized"}

    if not file:
        return {"status": "error", "message": "No file uploaded"}

    doc_map = {doc.lower(): doc for doc in required_docs}
    normalized_doc = doc_map.get(doc_type.strip().lower())

    if not normalized_doc:
        return {
            "status": "error",
            "message": f"Unknown document '{doc_type}'. Must be one of {required_docs}",
        }

    # Save file
    filepath = os.path.join(folder, f"{normalized_doc}.pdf")
    with open(filepath, "wb") as f:
        f.write(await file.read())

    uploaded_docs = [
        doc.split(".pdf")[0]
        for doc in os.listdir(folder)
        if doc.endswith(".pdf") and doc.split(".pdf")[0] in required_docs
    ]

    missing_docs = [doc for doc in required_docs if doc not in uploaded_docs]

    doc_status = {
        doc: ("completed" if doc in uploaded_docs else "incompleted")
        for doc in required_docs
    }

    if not missing_docs:
        # All documents received → email HR
        await send_email_with_attachments(email, folder)

        shutil.rmtree(folder)

        return {
            "status": "complete",
            "message": "All documents received. Email sent via Composio.",
            "doc_status": doc_status,
        }

    next_doc = missing_docs[0]

    return {
        "status": "incomplete",
        "message": f"{normalized_doc} uploaded successfully.",
        "missing_docs": missing_docs,
        "next_doc": next_doc,
        "doc_status": doc_status,
    }


async def send_email_with_attachments(user_email: str, folder: str):
    """
    Sends ONE email to HR with ALL attachments (but email sending is one-by-one).
    """
    hr_list = ["shreya.p@nighthack.in", "hr@example.com"]

    subject = f"New Employee Onboarding - {user_email}"
    html_body = f"All required documents for {user_email} have been collected."

    for hr_email in hr_list:  # ONE BY ONE
        status, data = send_email_via_composio_single(
            hr_email,
            subject,
            html_body
        )
        print("Email sent:", hr_email, status, data)
