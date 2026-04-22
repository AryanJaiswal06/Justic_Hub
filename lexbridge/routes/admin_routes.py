# routes/admin_routes.py — /api/admin/*
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from extensions import db
from models.user_model import User, LawyerProfile
from models.case_model import Case
from models.document_model import Document, Payment, Dispute, Notification
from services.notification_service import notify_lawyer_verified, send_lawyer_verified_email

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _require_admin():
    user = User.query.get(int(get_jwt_identity()))
    if not user or user.role != "admin":
        return None, (jsonify(error="Admin access required."), 403)
    return user, None


# ── Platform stats ────────────────────────────────────────────────────────────

@admin_bp.get("/stats")
@jwt_required()
def stats():
    _, err = _require_admin()
    if err: return err

    total_users   = User.query.filter(User.role != "admin").count()
    total_lawyers = User.query.filter_by(role="lawyer").count()
    total_clients = User.query.filter_by(role="client").count()
    total_cases   = Case.query.count()
    active_cases  = Case.query.filter(Case.status.in_(["active", "in_progress"])).count()
    closed_cases  = Case.query.filter_by(status="closed").count()
    total_docs    = Document.query.count()
    pending_docs  = Document.query.filter_by(status="pending").count()
    total_revenue = db.session.query(
        func.sum(Payment.amount)
    ).filter_by(status="completed").scalar() or 0
    open_disputes = Dispute.query.filter(
        Dispute.status.in_(["open", "investigating"])
    ).count()
    pending_verif = LawyerProfile.query.filter(
        LawyerProfile.verified_at.is_(None)
    ).count()

    return jsonify(stats={
        "total_users":    total_users,
        "total_lawyers":  total_lawyers,
        "total_clients":  total_clients,
        "total_cases":    total_cases,
        "active_cases":   active_cases,
        "closed_cases":   closed_cases,
        "total_docs":     total_docs,
        "pending_docs":   pending_docs,
        "total_revenue":  float(total_revenue),
        "open_disputes":  open_disputes,
        "pending_verif":  pending_verif,
    }), 200


# ── Users ─────────────────────────────────────────────────────────────────────

@admin_bp.get("/users")
@jwt_required()
def list_users():
    _, err = _require_admin()
    if err: return err

    role   = request.args.get("role")
    page   = int(request.args.get("page", 1))
    per    = min(int(request.args.get("per_page", 50)), 100)
    search = request.args.get("q", "").strip()

    q = User.query.filter(User.role != "admin").options(joinedload(User.lawyer_profile))
    if role:
        q = q.filter_by(role=role)
    if search:
        q = q.filter(
            User.full_name.ilike(f"%{search}%") |
            User.email.ilike(f"%{search}%")
        )

    pagination = q.order_by(User.created_at.desc()).paginate(page=page, per_page=per, error_out=False)
    return jsonify(
        users=[u.to_dict() for u in pagination.items],
        total=pagination.total,
        pages=pagination.pages,
        page=page,
    ), 200


@admin_bp.put("/users/<int:user_id>/status")
@jwt_required()
def set_user_status(user_id: int):
    _, err = _require_admin()
    if err: return err

    data   = request.get_json(silent=True) or {}
    action = data.get("action", "")
    user   = User.query.get_or_404(user_id)

    if action == "suspend":
        user.is_active = False
    elif action == "reinstate":
        user.is_active = True
    else:
        return jsonify(error="action must be 'suspend' or 'reinstate'."), 400

    db.session.commit()
    return jsonify(user=user.to_dict()), 200


# ── Lawyer verifications ──────────────────────────────────────────────────────

@admin_bp.get("/verifications/pending")
@jwt_required()
def pending_verifications():
    _, err = _require_admin()
    if err: return err

    profiles = (
        LawyerProfile.query
        .filter(LawyerProfile.verified_at.is_(None))
        .join(User, LawyerProfile.user_id == User.id)
        .filter_by(is_active=True)
        .all()
    )
    return jsonify(lawyers=[p.user.to_dict() for p in profiles]), 200


@admin_bp.post("/verifications/<int:user_id>/approve")
@jwt_required()
def approve_lawyer(user_id: int):
    admin, err = _require_admin()
    if err: return err

    user = User.query.get_or_404(user_id)
    if not user.lawyer_profile:
        return jsonify(error="No lawyer profile found."), 404

    user.lawyer_profile.verified_at = datetime.utcnow()
    user.lawyer_profile.verified_by = admin.id
    user.is_verified = True
    db.session.commit()

    notify_lawyer_verified(user.id, approved=True)
    try:
        send_lawyer_verified_email(user.email, user.full_name, approved=True)
    except Exception:
        pass

    return jsonify(message="Lawyer approved.", user=user.to_dict()), 200


@admin_bp.post("/verifications/<int:user_id>/reject")
@jwt_required()
def reject_lawyer(user_id: int):
    _, err = _require_admin()
    if err: return err

    user = User.query.get_or_404(user_id)
    user.is_verified = False
    db.session.commit()

    notify_lawyer_verified(user.id, approved=False)
    try:
        send_lawyer_verified_email(user.email, user.full_name, approved=False)
    except Exception:
        pass

    return jsonify(message="Lawyer rejected.", user=user.to_dict()), 200


# ── Documents ─────────────────────────────────────────────────────────────────

@admin_bp.get("/documents")
@jwt_required()
def list_documents():
    _, err = _require_admin()
    if err: return err

    status = request.args.get("status")
    q      = Document.query
    if status:
        q = q.filter_by(status=status)
    docs = q.order_by(Document.uploaded_at.desc()).limit(200).all()
    return jsonify(documents=[d.to_dict() for d in docs]), 200


@admin_bp.post("/documents/<int:doc_id>/verify")
@jwt_required()
def verify_document(doc_id: int):
    admin, err = _require_admin()
    if err: return err

    data   = request.get_json(silent=True) or {}
    action = data.get("action", "")
    doc    = Document.query.get_or_404(doc_id)

    if action == "approve":
        doc.status      = "verified"
        doc.reviewed_by = admin.id
        doc.reviewed_at = datetime.utcnow()
    elif action == "reject":
        doc.status      = "rejected"
        doc.reviewed_by = admin.id
        doc.reviewed_at = datetime.utcnow()
    else:
        return jsonify(error="action must be 'approve' or 'reject'."), 400

    db.session.commit()
    return jsonify(document=doc.to_dict()), 200


# ── Cases ─────────────────────────────────────────────────────────────────────

@admin_bp.get("/cases")
@jwt_required()
def list_cases():
    _, err = _require_admin()
    if err: return err

    status = request.args.get("status")
    page   = int(request.args.get("page", 1))
    per    = min(int(request.args.get("per_page", 50)), 100)

    q = Case.query
    if status:
        q = q.filter_by(status=status)

    pagination = q.order_by(Case.opened_at.desc()).paginate(page=page, per_page=per, error_out=False)
    return jsonify(
        cases=[c.to_dict() for c in pagination.items],
        total=pagination.total,
        pages=pagination.pages,
        page=page,
    ), 200


@admin_bp.put("/cases/<int:case_id>/status")
@jwt_required()
def update_case_status(case_id: int):
    _, err = _require_admin()
    if err: return err

    data   = request.get_json(silent=True) or {}
    status = data.get("status", "")
    valid  = ("pending", "active", "in_progress", "closed", "dismissed")
    if status not in valid:
        return jsonify(error=f"status must be one of {valid}."), 400

    case = Case.query.get_or_404(case_id)
    case.status = status
    if status == "closed":
        case.closed_at = datetime.utcnow()
    db.session.commit()
    return jsonify(case=case.to_dict()), 200
