# routes/match_routes.py — Lawyer/Client matching & request workflow
#
# Endpoints under /api/match/*
#
# Directory & browsing
#   GET  /api/match/lawyers            — list all verified lawyers (for clients)
#   GET  /api/match/lawyers/<user_id>  — get a single lawyer's public profile
#   GET  /api/match/open-cases         — list unassigned pending cases (for lawyers)
#
# Requests (two-way)
#   POST /api/match/requests                       — create request (client→lawyer or lawyer→case)
#   GET  /api/match/requests                       — list the current user's requests (both directions)
#   POST /api/match/requests/<req_id>/respond      — accept/reject an incoming request
#   POST /api/match/requests/<req_id>/withdraw     — withdraw one of your own pending requests

from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_

from extensions import db, limiter
from models.user_model     import User, LawyerProfile
from models.case_model     import Case, CaseUpdate, Rating
from models.document_model import Document
from models.request_model  import CaseRequest
from services.notification_service import (
    create_notification, send_case_accepted_email,
)

match_bp = Blueprint("match", __name__, url_prefix="/api/match")


# ─── helpers ──────────────────────────────────────────────────────────────────

def _current_user() -> User | None:
    try:
        return User.query.get(int(get_jwt_identity()))
    except (ValueError, TypeError):
        return None


def _bad(msg: str, code: int = 400):
    return jsonify(error=msg), code


# ─── Directory: list lawyers ─────────────────────────────────────────────────

@match_bp.get("/lawyers")
@jwt_required()
def list_lawyers():
    """Clients (and lawyers/admins) can browse all registered, active lawyers."""
    user = _current_user()
    if not user:
        return _bad("Invalid session.", 401)

    spec   = (request.args.get("specialization") or "").strip().lower()
    search = (request.args.get("q") or "").strip().lower()
    only_verified = request.args.get("verified", "false").lower() == "true"

    # Budget filter — accepts either consultation or per-hearing fee
    def _fnum(key):
        v = request.args.get(key)
        try:    return float(v) if v not in (None, "") else None
        except: return None
    min_fee = _fnum("min_fee")
    max_fee = _fnum("max_fee")

    q = (
        User.query
        .filter(User.role == "lawyer", User.is_active.is_(True))
        .join(LawyerProfile, LawyerProfile.user_id == User.id)
    )
    if only_verified:
        q = q.filter(LawyerProfile.verified_at.isnot(None))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(User.full_name.ilike(like), User.email.ilike(like)))
    if min_fee is not None:
        q = q.filter(or_(
            LawyerProfile.per_hearing_fee  >= min_fee,
            LawyerProfile.consultation_fee >= min_fee,
        ))
    if max_fee is not None:
        # treat missing fee as "unknown" → include it; only filter rows with both set above max
        q = q.filter(or_(
            LawyerProfile.per_hearing_fee.is_(None),
            LawyerProfile.per_hearing_fee  <= max_fee,
        ))

    lawyers = q.order_by(User.full_name.asc()).limit(200).all()

    result = []
    for law in lawyers:
        d = law.to_dict()
        lp = law.lawyer_profile
        if lp:
            # Specialization filter — skip server-side if profile has no tags
            if spec:
                specs = [s.lower() for s in (lp.specializations or [])]
                if not any(spec in s for s in specs):
                    continue
            d["lawyer_profile"] = lp.to_dict()
        result.append(d)

    return jsonify(lawyers=result), 200


@match_bp.get("/lawyers/<int:user_id>")
@jwt_required()
def get_lawyer(user_id: int):
    law = User.query.filter_by(id=user_id, role="lawyer").first_or_404()
    return jsonify(lawyer=law.to_dict()), 200


# ─── Directory: list open cases (for lawyers) ────────────────────────────────

@match_bp.get("/open-cases")
@jwt_required()
def list_open_cases():
    """Lawyers can browse all unassigned, pending cases they can express interest in."""
    user = _current_user()
    if not user:
        return _bad("Invalid session.", 401)
    if user.role not in ("lawyer", "admin"):
        return _bad("Only lawyers can browse open cases.", 403)

    case_type = (request.args.get("case_type") or "").strip().lower()
    priority  = (request.args.get("priority")  or "").strip().lower()

    q = Case.query.filter(Case.lawyer_id.is_(None), Case.status == "pending")
    if case_type:
        q = q.filter(db.func.lower(Case.case_type) == case_type)
    if priority:
        q = q.filter_by(priority=priority)

    cases = q.order_by(Case.opened_at.desc()).limit(100).all()

    # Mark ones the current lawyer already showed interest in
    my_interest_ids = {
        r.case_id for r in CaseRequest.query.filter_by(
            lawyer_id=user.id, initiated_by="lawyer",
        ).filter(CaseRequest.status.in_(["pending", "accepted"])).all()
    }

    out = []
    for c in cases:
        d = c.to_dict()
        d["already_requested"] = c.id in my_interest_ids
        out.append(d)
    return jsonify(cases=out), 200


# ─── Create a request ────────────────────────────────────────────────────────

@match_bp.post("/requests")
@jwt_required()
@limiter.limit("60 per day")
def create_request():
    """
    Body:
      { "case_id": <int>, "lawyer_id": <int optional>, "message": "..." }

    If the caller is a CLIENT, `lawyer_id` is required → client asks lawyer.
    If the caller is a LAWYER, `case_id` is required → lawyer expresses interest.
    """
    user = _current_user()
    if not user:
        return _bad("Invalid session.", 401)

    data       = request.get_json(silent=True) or {}
    case_id    = data.get("case_id")
    lawyer_id  = data.get("lawyer_id")
    message    = (data.get("message") or "").strip() or None

    if not case_id:
        return _bad("case_id is required.")

    case = Case.query.get(case_id)
    if not case:
        return _bad("Case not found.", 404)
    if case.status not in ("pending",) or case.lawyer_id is not None:
        return _bad("This case is already assigned or closed.", 409)

    # Decide the direction
    if user.role == "client":
        # Client initiates: must be their own case, must specify a lawyer
        if case.client_id != user.id:
            return _bad("You can only request lawyers for your own cases.", 403)
        if not lawyer_id:
            return _bad("lawyer_id is required.")
        lawyer = User.query.filter_by(id=lawyer_id, role="lawyer", is_active=True).first()
        if not lawyer:
            return _bad("Lawyer not found.", 404)
        initiated_by = "client"
        client_id    = user.id

    elif user.role == "lawyer":
        # Lawyer initiates: any pending unassigned case
        initiated_by = "lawyer"
        lawyer_id    = user.id
        client_id    = case.client_id
    else:
        return _bad("Admins cannot create requests.", 403)

    # Reject duplicate pending request in the same direction
    existing = CaseRequest.query.filter_by(
        case_id=case.id, client_id=client_id, lawyer_id=lawyer_id,
        initiated_by=initiated_by, status="pending",
    ).first()
    if existing:
        return _bad("A pending request already exists.", 409)

    req = CaseRequest(
        case_id=case.id, client_id=client_id, lawyer_id=lawyer_id,
        initiated_by=initiated_by, message=message, status="pending",
    )
    db.session.add(req)
    db.session.commit()

    # In-app notification to the receiver
    receiver_id = lawyer_id if initiated_by == "client" else client_id
    title = (
        f"New case request from {user.full_name}" if initiated_by == "client"
        else f"Lawyer {user.full_name} is interested in your case"
    )
    body = f"Case: {case.title}" + (f"\n\n{message}" if message else "")
    try:
        create_notification(
            receiver_id, title, body=body,
            notif_type="case_request", link=f"/requests/{req.id}",
        )
    except Exception:
        pass

    return jsonify(request=req.to_dict()), 201


# ─── List my requests ────────────────────────────────────────────────────────

@match_bp.get("/requests")
@jwt_required()
def list_my_requests():
    """
    Returns an object with:
      incoming: requests where I am the receiver and can act
      outgoing: requests I created and am awaiting a response on
    """
    user = _current_user()
    if not user:
        return _bad("Invalid session.", 401)

    status = request.args.get("status")  # optional filter

    if user.role == "client":
        incoming_q = CaseRequest.query.filter_by(client_id=user.id, initiated_by="lawyer")
        outgoing_q = CaseRequest.query.filter_by(client_id=user.id, initiated_by="client")
    elif user.role == "lawyer":
        incoming_q = CaseRequest.query.filter_by(lawyer_id=user.id, initiated_by="client")
        outgoing_q = CaseRequest.query.filter_by(lawyer_id=user.id, initiated_by="lawyer")
    else:
        # admin sees all
        incoming_q = CaseRequest.query
        outgoing_q = CaseRequest.query.filter(db.false())

    if status:
        incoming_q = incoming_q.filter_by(status=status)
        outgoing_q = outgoing_q.filter_by(status=status)

    incoming = incoming_q.order_by(CaseRequest.created_at.desc()).limit(100).all()
    outgoing = outgoing_q.order_by(CaseRequest.created_at.desc()).limit(100).all()

    return jsonify(
        incoming=[r.to_dict() for r in incoming],
        outgoing=[r.to_dict() for r in outgoing],
    ), 200


# ─── Respond to a request (accept/reject) ────────────────────────────────────

@match_bp.post("/requests/<int:req_id>/respond")
@jwt_required()
def respond_to_request(req_id: int):
    """
    Body: { "action": "accept" | "reject" }

    Only the *receiver* of the request can respond:
      • client-initiated  → lawyer responds
      • lawyer-initiated → client responds
    Accepting assigns the lawyer to the case.
    """
    user = _current_user()
    if not user:
        return _bad("Invalid session.", 401)

    data   = request.get_json(silent=True) or {}
    action = (data.get("action") or "").lower()
    if action not in ("accept", "reject"):
        return _bad("action must be 'accept' or 'reject'.")

    req = CaseRequest.query.get_or_404(req_id)
    if req.status != "pending":
        return _bad(f"Request is already {req.status}.", 409)

    # Only the proper receiver can respond
    is_receiver = (
        (req.initiated_by == "client" and user.id == req.lawyer_id) or
        (req.initiated_by == "lawyer" and user.id == req.client_id)
    )
    if not is_receiver and user.role != "admin":
        return _bad("You are not authorised to respond to this request.", 403)

    case = Case.query.get(req.case_id)
    if not case:
        return _bad("Case no longer exists.", 404)

    if action == "reject":
        req.status = "rejected"
        req.responded_at = datetime.utcnow()
        db.session.commit()

        # Notify the initiator
        initiator_id = req.client_id if req.initiated_by == "client" else req.lawyer_id
        try:
            create_notification(
                initiator_id,
                "Your case request was declined",
                body=f"Case: {case.title}",
                notif_type="case_request_rejected",
            )
        except Exception:
            pass
        return jsonify(request=req.to_dict()), 200

    # ── accept ──
    if case.lawyer_id and case.lawyer_id != req.lawyer_id:
        return _bad("This case has already been assigned to another lawyer.", 409)

    req.status       = "accepted"
    req.responded_at = datetime.utcnow()

    case.lawyer_id = req.lawyer_id
    case.status    = "active"

    # Audit log entry
    db.session.add(CaseUpdate(
        case_id=case.id, author_id=user.id,
        update_type="lawyer_assigned",
        content=f"Lawyer assigned via {req.initiated_by}-initiated request.",
    ))

    # Bump lawyer's case counter
    lawyer = User.query.get(req.lawyer_id)
    if lawyer and lawyer.lawyer_profile:
        lawyer.lawyer_profile.total_cases = (lawyer.lawyer_profile.total_cases or 0) + 1

    # Reject every other pending request for this case
    (
        CaseRequest.query
        .filter(CaseRequest.case_id == case.id,
                CaseRequest.id != req.id,
                CaseRequest.status == "pending")
        .update({"status": "rejected", "responded_at": datetime.utcnow()},
                synchronize_session=False)
    )
    db.session.commit()

    # Notify initiator + email the client
    initiator_id = req.client_id if req.initiated_by == "client" else req.lawyer_id
    try:
        create_notification(
            initiator_id,
            "Your case request was accepted!",
            body=f"Case: {case.title}",
            notif_type="case_request_accepted",
        )
    except Exception:
        pass

    client = User.query.get(req.client_id)
    lawyer = User.query.get(req.lawyer_id)
    if client and lawyer:
        try:
            send_case_accepted_email(client.email, client.full_name, case.title, lawyer.full_name)
        except Exception:
            pass

    return jsonify(request=req.to_dict(), case=case.to_dict()), 200


# ─── Withdraw a request ──────────────────────────────────────────────────────

@match_bp.post("/requests/<int:req_id>/withdraw")
@jwt_required()
def withdraw_request(req_id: int):
    user = _current_user()
    if not user:
        return _bad("Invalid session.", 401)

    req = CaseRequest.query.get_or_404(req_id)
    if req.status != "pending":
        return _bad(f"Request is already {req.status}.", 409)

    is_initiator = (
        (req.initiated_by == "client" and user.id == req.client_id) or
        (req.initiated_by == "lawyer" and user.id == req.lawyer_id)
    )
    if not is_initiator:
        return _bad("Only the initiator can withdraw a request.", 403)

    req.status = "withdrawn"
    req.responded_at = datetime.utcnow()
    db.session.commit()
    return jsonify(request=req.to_dict()), 200


# ─── Detailed lawyer profile (for client "View Profile" modal) ───────────────

@match_bp.get("/lawyers/<int:user_id>/profile")
@jwt_required()
def get_lawyer_profile(user_id: int):
    """
    Returns a lawyer's full public profile:
      • User + LawyerProfile details
      • Profile-level uploaded documents (case_id IS NULL, e.g. bar card, ID proof)
      • All ratings & reviews received
    """
    me = _current_user()
    if not me:
        return _bad("Invalid session.", 401)

    law = User.query.filter_by(id=user_id, role="lawyer", is_active=True).first()
    if not law:
        return _bad("Lawyer not found.", 404)

    # Only show profile-level docs the lawyer themselves uploaded
    docs = (
        Document.query
        .filter(Document.uploaded_by == law.id, Document.case_id.is_(None))
        .order_by(Document.uploaded_at.desc())
        .limit(50).all()
    )

    ratings = (
        Rating.query
        .filter_by(lawyer_id=law.id)
        .order_by(Rating.created_at.desc())
        .limit(50).all()
    )

    payload = law.to_dict()
    payload["documents"] = [d.to_dict() for d in docs]
    payload["ratings"]   = [r.to_dict() for r in ratings]
    return jsonify(lawyer=payload), 200


# ─── Ratings: create / list ─────────────────────────────────────────────────

@match_bp.post("/ratings")
@jwt_required()
@limiter.limit("30 per day")
def create_rating():
    """
    Body: { "case_id": <int>, "score": 1-5, "review": "..." }

    Only the case's *client* may rate, and only on a **closed** case that has
    a lawyer assigned. One rating per (case, reviewer).
    """
    user = _current_user()
    if not user:
        return _bad("Invalid session.", 401)
    if user.role != "client":
        return _bad("Only clients can rate lawyers.", 403)

    data    = request.get_json(silent=True) or {}
    case_id = data.get("case_id")
    score   = data.get("score")
    review  = (data.get("review") or "").strip() or None

    try:
        score = int(score)
    except (TypeError, ValueError):
        return _bad("score must be an integer 1-5.")
    if score < 1 or score > 5:
        return _bad("score must be between 1 and 5.")
    if not case_id:
        return _bad("case_id is required.")

    case = Case.query.get(case_id)
    if not case:
        return _bad("Case not found.", 404)
    if case.client_id != user.id:
        return _bad("You can only rate your own cases.", 403)
    if case.status != "closed":
        return _bad("You can only rate a lawyer after the case is closed.", 409)
    if not case.lawyer_id:
        return _bad("This case has no assigned lawyer.", 409)

    # Reject duplicate rating
    existing = Rating.query.filter_by(case_id=case.id, reviewer_id=user.id).first()
    if existing:
        return _bad("You have already rated this case.", 409)

    rating = Rating(
        case_id=case.id, reviewer_id=user.id,
        lawyer_id=case.lawyer_id, score=score, review=review,
    )
    db.session.add(rating)

    # ── Update rolling average on LawyerProfile ─────────────────────────────
    lp = LawyerProfile.query.filter_by(user_id=case.lawyer_id).first()
    if lp:
        old_total = lp.total_ratings or 0
        old_avg   = float(lp.avg_rating or 0)
        new_total = old_total + 1
        new_avg   = ((old_avg * old_total) + score) / new_total
        lp.avg_rating    = round(new_avg, 2)
        lp.total_ratings = new_total

    db.session.commit()

    # Notify the lawyer
    try:
        create_notification(
            case.lawyer_id,
            f"You received a {score}-star rating",
            body=f"Case: {case.title}" + (f"\n\n{review}" if review else ""),
            notif_type="rating_received",
        )
    except Exception:
        pass

    return jsonify(rating=rating.to_dict()), 201


@match_bp.get("/ratings")
@jwt_required()
def list_ratings():
    """List ratings. Query params:  lawyer_id (required)."""
    lawyer_id = request.args.get("lawyer_id", type=int)
    if not lawyer_id:
        return _bad("lawyer_id query param is required.")
    items = (
        Rating.query
        .filter_by(lawyer_id=lawyer_id)
        .order_by(Rating.created_at.desc())
        .limit(100).all()
    )
    return jsonify(ratings=[r.to_dict() for r in items]), 200
