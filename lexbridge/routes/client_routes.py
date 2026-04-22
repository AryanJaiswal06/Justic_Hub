# routes/client_routes.py — /api/client/*
import os, uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from extensions import db, limiter
from models.user_model import User
from models.case_model import Case, CaseUpdate
from models.document_model import Document, Notification
from services.notification_service import notify_case_update

client_bp = Blueprint("client", __name__, url_prefix="/api/client")

ALLOWED_MIME = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg", "image/png",
}


def _require_client():
    user = User.query.get(int(get_jwt_identity()))
    if not user or user.role not in ("client", "admin"):
        return None, (jsonify(error="Forbidden."), 403)
    return user, None


# ── Cases ─────────────────────────────────────────────────────────────────────

@client_bp.get("/cases")
@jwt_required()
def list_cases():
    user, err = _require_client()
    if err: return err

    status = request.args.get("status")
    q      = Case.query.filter_by(client_id=user.id)
    if status:
        q = q.filter_by(status=status)
    cases = q.order_by(Case.opened_at.desc()).all()
    return jsonify(cases=[c.to_dict() for c in cases]), 200


@client_bp.post("/cases")
@jwt_required()
@limiter.limit("30 per day")
def open_case():
    user, err = _require_client()
    if err: return err

    data      = request.get_json(silent=True) or {}
    title     = (data.get("title")     or "").strip()
    case_type = (data.get("case_type") or "").strip()
    if not title or not case_type:
        return jsonify(error="title and case_type are required."), 400

    case = Case(
        case_number=Case.generate_case_number(),
        client_id=user.id,
        case_type=case_type,
        title=title,
        description=data.get("description", ""),
        priority=data.get("priority", "medium"),
        next_hearing=datetime.fromisoformat(data["next_hearing"]).date() if data.get("next_hearing") else None,
    )
    db.session.add(case)
    db.session.commit()
    return jsonify(case=case.to_dict()), 201


@client_bp.get("/cases/<int:case_id>")
@jwt_required()
def get_case(case_id: int):
    user, err = _require_client()
    if err: return err
    case = Case.query.filter_by(id=case_id, client_id=user.id).first_or_404()
    return jsonify(case=case.to_dict(include_updates=True)), 200


# ── Document upload ───────────────────────────────────────────────────────────

@client_bp.post("/cases/<int:case_id>/documents")
@jwt_required()
@limiter.limit("50 per day")
def upload_document(case_id: int):
    user, err = _require_client()
    if err: return err

    case = Case.query.filter_by(id=case_id, client_id=user.id).first_or_404()
    file = request.files.get("file")
    if not file:
        return jsonify(error="No file provided."), 400
    if file.mimetype not in ALLOWED_MIME:
        return jsonify(error="Unsupported file type."), 415

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    ext        = os.path.splitext(secure_filename(file.filename))[1]
    stored     = f"{uuid.uuid4().hex}{ext}"
    path       = os.path.join(upload_folder, stored)
    file.save(path)

    doc = Document(
        case_id=case_id,
        uploaded_by=user.id,
        file_name=stored,
        original_name=file.filename,
        mime_type=file.mimetype,
        file_size_bytes=os.path.getsize(path),
        storage_path=path,
        doc_type=request.form.get("doc_type", "other"),
    )
    db.session.add(doc)

    update = CaseUpdate(
        case_id=case_id, author_id=user.id,
        update_type="document_added",
        content=f"Document uploaded: {file.filename}",
    )
    db.session.add(update)

    db.session.commit()
    return jsonify(document=doc.to_dict()), 201


@client_bp.get("/documents")
@jwt_required()
def list_documents():
    user, err = _require_client()
    if err: return err
    docs = Document.query.filter_by(uploaded_by=user.id).order_by(Document.uploaded_at.desc()).all()
    return jsonify(documents=[d.to_dict() for d in docs]), 200


# ── Notifications ─────────────────────────────────────────────────────────────

@client_bp.get("/notifications")
@jwt_required()
def get_notifications():
    user, err = _require_client()
    if err: return err
    notifs = (
        Notification.query
        .filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc())
        .limit(50).all()
    )
    return jsonify(notifications=[n.to_dict() for n in notifs]), 200


@client_bp.post("/notifications/read-all")
@jwt_required()
def mark_all_read():
    user, err = _require_client()
    if err: return err
    Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return jsonify(message="All notifications marked as read."), 200
