# routes/auth_routes.py — /api/auth/*
import os, secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
)
from extensions import db, limiter
from models.user_model import User, LawyerProfile, AuthToken
from services.notification_service import send_verification_email, send_password_reset_email

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_tokens(user: User) -> dict:
    identity = str(user.id)
    return {
        "access_token":  create_access_token(identity=identity),
        "refresh_token": create_refresh_token(identity=identity),
        "role":          user.role,
        "user":          user.to_dict(),
    }

def _bad(msg: str, code: int = 400):
    return jsonify(error=msg), code


# ── Register ──────────────────────────────────────────────────────────────────

@auth_bp.post("/register")
@limiter.limit("10 per hour")
def register():
    data = request.get_json(silent=True) or {}

    full_name = (data.get("full_name") or "").strip()
    email     = (data.get("email")     or "").strip().lower()
    password  = (data.get("password")  or "")
    role      = (data.get("role")      or "client").lower()

    if not full_name or not email or not password:
        return _bad("full_name, email, and password are required.")
    if role not in ("client", "lawyer"):
        return _bad("role must be 'client' or 'lawyer'.")
    if len(password) < 8:
        return _bad("Password must be at least 8 characters.")
    if User.query.filter_by(email=email).first():
        return _bad("An account with this email already exists.", 409)

    user = User(
        full_name=full_name,
        email=email,
        phone=data.get("phone", ""),
        role=role,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()   # get user.id before commit

    # Lawyer profile
    if role == "lawyer":
        bar_no = (data.get("bar_council_no") or "").strip()
        if not bar_no:
            return _bad("bar_council_no is required for lawyers.")
        lp = LawyerProfile(
            user_id=user.id,
            bar_council_no=bar_no,
            specializations=[data["specialization"]] if data.get("specialization") else None,
            experience_years=int(data.get("experience_years") or 0),
        )
        db.session.add(lp)

    # Email verification token
    token = secrets.token_urlsafe(32)
    auth_tok = AuthToken(
        user_id=user.id,
        token=token,
        token_type="email_verify",
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.session.add(auth_tok)
    db.session.commit()

    # Send verification email (non-blocking failure)
    try:
        send_verification_email(email, full_name, token)
    except Exception:
        pass

    return jsonify(**_make_tokens(user)), 201


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.post("/login")
@limiter.limit("20 per hour")
def login():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email")    or "").strip().lower()
    password = (data.get("password") or "")

    if not email or not password:
        return _bad("email and password are required.")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return _bad("Invalid email or password.", 401)
    if not user.is_active:
        return _bad("This account has been suspended.", 403)

    user.last_login = datetime.utcnow()
    db.session.commit()
    return jsonify(**_make_tokens(user)), 200


# ── Refresh ───────────────────────────────────────────────────────────────────

@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = int(get_jwt_identity())
    user    = User.query.get_or_404(user_id)
    return jsonify(access_token=create_access_token(identity=str(user_id)), role=user.role), 200


# ── Verify email ──────────────────────────────────────────────────────────────

@auth_bp.get("/verify-email/<token>")
def verify_email(token: str):
    tok = AuthToken.query.filter_by(token=token, token_type="email_verify").first()
    if not tok or tok.is_expired or tok.is_used:
        return _bad("Invalid or expired verification link.", 400)

    tok.user.email_verified = True
    tok.used_at = datetime.utcnow()
    db.session.commit()
    return jsonify(message="Email verified successfully."), 200


# ── Forgot password ───────────────────────────────────────────────────────────

@auth_bp.post("/forgot-password")
@limiter.limit("5 per hour")
def forgot_password():
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return _bad("email is required.")

    user = User.query.filter_by(email=email).first()
    # Always return 200 to avoid user enumeration
    if user and user.is_active:
        token = secrets.token_urlsafe(32)
        tok   = AuthToken(
            user_id=user.id,
            token=token,
            token_type="password_reset",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.session.add(tok)
        db.session.commit()
        try:
            send_password_reset_email(email, user.full_name, token)
        except Exception:
            pass

    return jsonify(message="If that email exists, a reset link has been sent."), 200


# ── Reset password ────────────────────────────────────────────────────────────

@auth_bp.post("/reset-password")
@limiter.limit("10 per hour")
def reset_password():
    data     = request.get_json(silent=True) or {}
    token    = (data.get("token")    or "").strip()
    password = (data.get("password") or "")

    if not token or not password:
        return _bad("token and password are required.")
    if len(password) < 8:
        return _bad("Password must be at least 8 characters.")

    tok = AuthToken.query.filter_by(token=token, token_type="password_reset").first()
    if not tok or tok.is_expired or tok.is_used:
        return _bad("Invalid or expired reset token.", 400)

    tok.user.set_password(password)
    tok.used_at = datetime.utcnow()
    db.session.commit()
    return jsonify(message="Password reset successfully."), 200


# ── Current user ──────────────────────────────────────────────────────────────

@auth_bp.get("/me")
@jwt_required()
def me():
    user = User.query.get_or_404(int(get_jwt_identity()))
    return jsonify(user=user.to_dict()), 200
