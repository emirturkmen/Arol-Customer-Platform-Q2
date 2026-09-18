"""FastAPI backend of the AROL Customer Platform.

Login and sessions, the chat endpoint, and the fleet data the frontend shows
next to the conversation.
"""

import hashlib
import io
import json
import logging
import uuid
from datetime import datetime

import openai
import qrcode
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

import access
import orchestrator
from config import FRONTEND_URL, MANUALS_DIR
from db import execute, query, query_one

# One log line per turn and per tool call, next to uvicorn's access log.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="AROL Customer Platform")


class LoginRequest(BaseModel):
    email: str
    password: str


class ChatRequest(BaseModel):
    message: str
    machine: str | None = None


def user_from_token(token):
    session = query_one("SELECT * FROM Sessions WHERE token = ?", (token,))
    if not session:
        raise HTTPException(status_code=401, detail="Not logged in")
    user = query_one(
        """SELECT u.*, c.companyName, c.country, c.city, c.currency
           FROM Users u JOIN Companies c ON u.companyId = c.companyId
           WHERE u.userId = ?""",
        (session["userId"],),
    )
    user["token"] = token
    return user


def current_user(authorization: str = Header(default="")):
    """Resolve the session token sent as 'Authorization: Bearer <token>'."""
    return user_from_token(authorization.replace("Bearer ", "").strip())


@app.post("/api/login")
def login(request: LoginRequest):
    """Log in with email and password.

    The dataset has no credentials, so load_data.py stores the hash of one demo
    password for every account.
    """
    user = query_one("SELECT * FROM Users WHERE lower(email) = ?", (request.email.strip().lower(),))
    credentials = query_one("SELECT * FROM Credentials WHERE userId = ?",
                            (user["userId"],)) if user else None
    password_hash = hashlib.sha256(request.password.encode()).hexdigest()
    # Same message for an unknown address and a wrong password.
    if not credentials or credentials["passwordHash"] != password_hash:
        raise HTTPException(status_code=401, detail="Wrong email address or password")

    token = uuid.uuid4().hex
    execute(
        "INSERT INTO Sessions (token, userId, createdAt) VALUES (?, ?, ?)",
        (token, user["userId"], datetime.now().isoformat(timespec="seconds")),
    )
    return {"token": token}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return {
        "userId": user["userId"],
        "name": f"{user['firstName']} {user['lastName']}",
        "jobTitle": user["jobTitle"],
        "visibility": user["visibility"],
        "companyName": user["companyName"],
    }


@app.get("/api/machines")
def machines(user=Depends(current_user)):
    """The fleet of the user's company. Visible at every visibility level."""
    return query(
        """SELECT m.machineId, m.serialNumber, mo.modelCode, m.plantLocation, m.deliveryDate
           FROM Machines m JOIN MachineModels mo ON m.modelId = mo.modelId
           WHERE m.companyId = ? ORDER BY m.machineId""",
        (user["companyId"],),
    )


@app.get("/api/machines/{machine_ref}")
def machine(machine_ref: str, user=Depends(current_user)):
    """One machine, addressed by machineId or by serial number (QR code)."""
    row = access.get_machine(user, machine_ref)
    if not row:
        raise HTTPException(status_code=404, detail="Machine not found in your fleet")
    model = query_one("SELECT * FROM MachineModels WHERE modelId = ?", (row["modelId"],))
    return {**row, "model": model}


@app.get("/api/machines/{machine_ref}/manual")
def manual(machine_ref: str, token: str = ""):
    """The manual PDF of the machine.

    The token comes in the query string: the PDF is shown in an <iframe>, which
    cannot send an Authorization header.
    """
    user = user_from_token(token)
    row = access.get_machine(user, machine_ref)
    if not row:
        raise HTTPException(status_code=404, detail="Machine not found in your fleet")
    return FileResponse(MANUALS_DIR / f"{row['serialNumber']}_manual_EN.pdf",
                        media_type="application/pdf")


@app.get("/api/machines/{machine_ref}/qr")
def machine_qr(machine_ref: str, token: str = ""):
    """QR code to print and stick on the machine. It opens this machine page."""
    user = user_from_token(token)
    row = access.get_machine(user, machine_ref)
    if not row:
        raise HTTPException(status_code=404, detail="Machine not found in your fleet")
    image = qrcode.make(f"{FRONTEND_URL}/machines/{row['serialNumber']}")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png")


@app.get("/api/chat/history")
def history(machine: str = "", user=Depends(current_user)):
    """The last turns of this session about one machine, so the chat panel is not
    empty after a reload."""
    row = access.get_machine(user, machine) if machine else None
    rows = query(
        """SELECT role, content, agent, sources FROM Messages
           WHERE token = ? AND machineId IS ? ORDER BY messageId DESC LIMIT 6""",
        (user["token"], row["machineId"] if row else None),
    )
    for message in rows:
        message["sources"] = json.loads(message["sources"]) if message["sources"] else []
    return list(reversed(rows))


@app.post("/api/chat")
def chat(request: ChatRequest, user=Depends(current_user)):
    """One conversation turn, handled by the orchestrator."""
    machine_row = access.get_machine(user, request.machine) if request.machine else None
    try:
        return orchestrator.handle_message(user, user["token"], request.message, machine_row)
    except openai.OpenAIError as error:
        # Missing or wrong API key, no internet, quota exhausted.
        raise HTTPException(status_code=503, detail=f"The language model is not reachable: {error}")

