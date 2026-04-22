# routes/lawyer_routes.py — /api/lawyer/*
import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from extensions import db, limiter
from models.user_model import User, LawyerProfile
from models.case_model import Case, CaseUpdate
from models.document_model import Document
from services.notification_service import notify_case_update, send_case_accepted_email

lawyer_bp = Blueprint("lawyer", __name__, url_prefix="/api/lawyer")


def _require_lawyer():
    user = User.query.get(int(get_jwt_identity()))
    if not user or user.role not in ("lawyer", "admin"):
        return None, (jsonify(error="Forbidden."), 403)
    return user, None


# ── Profile ───────────────────────────────────────────────────────────────────

@lawyer_bp.get("/profile")
@jwt_required()
def get_profile():
    user, err = _require_lawyer()
    if err: return err
    return jsonify(user=user.to_dict()), 200


@lawyer_bp.put("/profile")
@jwt_required()
def update_profile():
    user, err = _require_lawyer()
    if err: return err

    data = request.get_json(silent=True) or {}

    # Update base user fields
    for field in ("full_name", "phone"):
        if field in data:
            setattr(user, field, (data[field] or "").strip())

    # Update lawyer profile
    lp = user.lawyer_profile
    if not lp:
        return jsonify(error="Lawyer profile not found."), 404

    lp_fields = (
        "bar_council_no", "bio", "availability_status",
        "specializations", "court_levels", "languages",
    )
    for field in lp_fields:
        if field in data:
            setattr(lp, field, data[field])

    if "consultation_fee" in data:
        lp.consultation_fee = float(data["consultation_fee"]) if data["consultation_fee"] else None
    if "per_hearing_fee" in data:
        lp.per_hearing_fee = float(data["per_hearing_fee"]) if data["per_hearing_fee"] else None
    if "experience_years" in data:
        lp.experience_years = int(data["experience_years"] or 0)

    db.session.commit()
    return jsonify(user=user.to_dict()), 200


# ── My cases ──────────────────────────────────────────────────────────────────

@lawyer_bp.get("/cases")
@jwt_required()
def my_cases():
    user, err = _require_lawyer()
    if err: return err
    status = request.args.get("status")
    q      = Case.query.filter_by(lawyer_id=user.id)
    if status:
        q = q.filter_by(status=status)
    cases = q.order_by(Case.updated_at.desc()).all()
    return jsonify(cases=[c.to_dict() for c in cases]), 200


@lawyer_bp.get("/cases/<int:case_id>")
@jwt_required()
def get_case(case_id: int):
    user, err = _require_lawyer()
    if err: return err
    case = Case.query.filter_by(id=case_id, lawyer_id=user.id).first_or_404()
    return jsonify(case=case.to_dict(include_updates=True)), 200


@lawyer_bp.post("/cases/<int:case_id>/update")
@jwt_required()
def add_case_update(case_id: int):
    user, err = _require_lawyer()
    if err: return err

    case = Case.query.filter_by(id=case_id, lawyer_id=user.id).first_or_404()
    data = request.get_json(silent=True) or {}

    content     = (data.get("content")     or "").strip()
    update_type = (data.get("update_type") or "note")
    new_status  = data.get("status")
    next_hearing= data.get("next_hearing")

    if not content:
        return jsonify(error="content is required."), 400

    update = CaseUpdate(
        case_id=case_id, author_id=user.id,
        update_type=update_type, content=content,
    )
    db.session.add(update)

    if new_status and new_status in ("pending", "active", "in_progress", "closed", "dismissed"):
        case.status = new_status
        if new_status == "closed":
            case.closed_at = datetime.utcnow()

    if next_hearing:
        case.next_hearing = datetime.fromisoformat(next_hearing).date()
        case.stage        = data.get("stage", case.stage)

    db.session.commit()

    # Notify client
    notify_case_update(case.client_id, user.id, case.title, content)

    return jsonify(update=update.to_dict(), case=case.to_dict()), 200


# ── Pending requests (unassigned cases) ───────────────────────────────────────

@lawyer_bp.get("/requests")
@jwt_required()
def pending_requests():
    user, err = _require_lawyer()
    if err: return err

    # Return pending cases with no assigned lawyer
    cases = (
        Case.query
        .filter_by(status="pending", lawyer_id=None)
        .order_by(Case.opened_at.desc())
        .limit(50).all()
    )
    return jsonify(cases=[c.to_dict() for c in cases]), 200


@lawyer_bp.post("/requests/<int:case_id>/accept")
@jwt_required()
@limiter.limit("20 per day")
def accept_case(case_id: int):
    user, err = _require_lawyer()
    if err: return err

    case = Case.query.filter_by(id=case_id, status="pending", lawyer_id=None).first_or_404()
    case.lawyer_id = user.id
    case.status    = "active"

    update = CaseUpdate(
        case_id=case_id, author_id=user.id,
        update_type="lawyer_assigned",
        content=f"Case accepted by {user.full_name}.",
    )
    db.session.add(update)

    # Update lawyer stats
    if user.lawyer_profile:
        user.lawyer_profile.total_cases += 1

    db.session.commit()

    # Email client
    client = User.query.get(case.client_id)
    if client:
        try:
            send_case_accepted_email(client.email, client.full_name, case.title, user.full_name)
        except Exception:
            pass

    return jsonify(case=case.to_dict()), 200


@lawyer_bp.post("/requests/<int:case_id>/reject")
@jwt_required()
def reject_case(case_id: int):
    user, err = _require_lawyer()
    if err: return err
    # Just leave the case unassigned — no state change needed
    case = Case.query.get_or_404(case_id)
    return jsonify(message=f"Case {case.case_number} rejected.", case_id=case_id), 200


# ── Close a case (lawyer marks work as finished) ─────────────────────────────

@lawyer_bp.post("/cases/<int:case_id>/close")
@jwt_required()
def close_case(case_id: int):
    """Lawyer marks their own active case as closed. Client can then rate."""
    user, err = _require_lawyer()
    if err: return err

    case = Case.query.filter_by(id=case_id, lawyer_id=user.id).first_or_404()
    if case.status == "closed":
        return jsonify(error="Case is already closed."), 409

    case.status    = "closed"
    case.closed_at = datetime.utcnow()

    db.session.add(CaseUpdate(
        case_id=case.id, author_id=user.id,
        update_type="status_change",
        content=f"Case marked as closed by {user.full_name}.",
    ))
    db.session.commit()

    # Notify the client so they can rate
    try:
        from services.notification_service import create_notification
        create_notification(
            case.client_id,
            "Your case has been closed",
            body=f"{user.full_name} closed case '{case.title}'. You may now rate your lawyer.",
            notif_type="case_closed",
        )
    except Exception:
        pass

    return jsonify(case=case.to_dict()), 200


# ── Profile-level documents (bar card, ID, etc.) ─────────────────────────────

_ALLOWED_DOC_EXT = {"pdf", "jpg", "jpeg", "png", "doc", "docx"}


def _ext_ok(filename: str) -> bool:
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in _ALLOWED_DOC_EXT


@lawyer_bp.get("/documents")
@jwt_required()
def list_my_documents():
    """Lawyer lists their own profile-level uploads (case_id IS NULL)."""
    user, err = _require_lawyer()
    if err: return err
    docs = (
        Document.query
        .filter(Document.uploaded_by == user.id, Document.case_id.is_(None))
        .order_by(Document.uploaded_at.desc())
        .limit(100).all()
    )
    return jsonify(documents=[d.to_dict() for d in docs]), 200


@lawyer_bp.post("/documents")
@jwt_required()
@limiter.limit("30 per day")
def upload_profile_document():
    """Upload a profile-level credential (bar card, ID proof, etc.)."""
    user, err = _require_lawyer()
    if err: return err

    if "file" not in request.files:
        return jsonify(error="file field is required."), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify(error="No file selected."), 400
    if not _ext_ok(f.filename):
        return jsonify(error="Unsupported file type."), 400

    doc_type = (request.form.get("doc_type") or "identity").lower()
    if doc_type not in ("evidence", "contract", "petition", "judgment", "identity", "other"):
        doc_type = "other"

    original = secure_filename(f.filename)
    stored   = f"{uuid.uuid4().hex}_{original}"
    folder   = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    path     = os.path.join(folder, stored)
    f.save(path)

    doc = Document(
        case_id=None,
        uploaded_by=user.id,
        file_name=stored,
        original_name=original,
        mime_type=f.mimetype or "application/octet-stream",
        file_size_bytes=os.path.getsize(path),
        storage_path=path,
        doc_type=doc_type,
        status="pending",
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify(document=doc.to_dict()), 201


@lawyer_bp.delete("/documents/<int:doc_id>")
@jwt_required()
def delete_my_document(doc_id: int):
    user, err = _require_lawyer()
    if err: return err
    doc = Document.query.filter_by(id=doc_id, uploaded_by=user.id).first_or_404()
    try:
        if doc.storage_path and os.path.exists(doc.storage_path):
            os.remove(doc.storage_path)
    except Exception:
        pass
    db.session.delete(doc)
    db.session.commit()
    return jsonify(message="Document removed."), 200


@lawyer_bp.get("/documents/<int:doc_id>/download")
@jwt_required()
def download_document(doc_id: int):
    """Serves the file. Lawyers see their own; admins/clients-with-active-case see it too."""
    uid = int(get_jwt_identity())
    me  = User.query.get(uid)
    doc = Document.query.get_or_404(doc_id)

    allowed = (doc.uploaded_by == uid) or (me and me.role == "admin")
    # If it's a profile doc, any authenticated lawyer/client may view (public credential)
    if doc.case_id is None:
        allowed = True
    if not allowed:
        return jsonify(error="Forbidden."), 403

    folder, fname = os.path.split(doc.storage_path)
    return send_from_directory(folder, fname, as_attachment=False,
                               download_name=doc.original_name)
