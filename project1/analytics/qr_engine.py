"""
Dynamic QR Attendance Engine
Academic Attendance Pattern & Risk Analytics System
Generates short-lived, cryptographically secure dynamic QR tokens, renders QR codes
for classroom projection/mobile scanning, and enforces strict server-side validation.
"""

import qrcode
import io
import time
import uuid
import hashlib
import datetime
from typing import Dict, Any, Optional, Tuple
from database.database import (
    create_qr_session, close_qr_session, get_active_qr_session,
    submit_qr_attendance, get_qr_session_roster, DB_PATH
)


def generate_qr_image_bytes(token_payload: str) -> bytes:
    """Generates high-contrast PNG image bytes for a given QR token string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(token_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def open_new_qr_session(
    session_id: str,
    institution_id: str,
    subject_id: str,
    room_id: Optional[str],
    opened_by: str,
    validity_seconds: int = 120,
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Initializes a dynamic QR attendance session with a cryptographically hashed token.
    Returns session metadata and PNG image bytes for display.
    """
    raw_token = f"QR_{session_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    qr_session_id = create_qr_session(
        session_id=session_id,
        institution_id=institution_id,
        subject_id=subject_id,
        room_id=room_id,
        token_hash=token_hash,
        opened_by=opened_by,
        validity_seconds=validity_seconds,
        db_path=db_path
    )

    qr_image_bytes = generate_qr_image_bytes(token_hash)

    return {
        "qr_session_id": qr_session_id,
        "token_hash": token_hash,
        "qr_image_bytes": qr_image_bytes,
        "validity_seconds": validity_seconds,
        "opened_at": datetime.datetime.now().isoformat()
    }


def validate_and_record_student_qr(
    qr_session_id: str,
    student_identifier: str,
    token_submitted: str,
    db_path: str = DB_PATH
) -> Tuple[bool, str]:
    """
    Validates a student's QR check-in submission against the server database.
    Checks token authenticity, expiration, student tenant enrollment, and prevents duplicate check-in.
    """
    return submit_qr_attendance(
        qr_session_id=qr_session_id,
        student_identifier=student_identifier,
        token_submitted=token_submitted,
        db_path=db_path
    )
