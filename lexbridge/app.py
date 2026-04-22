# app.py – LexBridge Flask Application Entry Point
import os
from datetime import timedelta
from pathlib import Path
from flask import Flask, jsonify, send_from_directory

# FIX (low): load_dotenv() must be called before any os.getenv() so .env is actually read
from dotenv import load_dotenv
if os.getenv('FLASK_ENV', 'development') != 'production':
    load_dotenv(override=True)
else:
    load_dotenv()

from flask_cors import CORS
from extensions import db, jwt, mail, limiter
from routes.auth_routes   import auth_bp
from routes.client_routes import client_bp
from routes.lawyer_routes import lawyer_bp
from routes.admin_routes  import admin_bp
from routes.match_routes  import match_bp

# Import all models so `db.create_all()` sees them
import models  # noqa: F401


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")

    env = config_name or os.getenv("FLASK_ENV", "development")

    # ── FIX (critical): No hardcoded DB credentials — require DATABASE_URL in env ──
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        if env == "testing":
            database_url = "sqlite:///:memory:"
        else:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set. "
                "Add it to your .env file, e.g.:\n"
                "DATABASE_URL=mysql+mysqlconnector://user:password@localhost/lexbridge"
            )

    # Ensure relative SQLite paths are resolved against app root, not current shell cwd.
    if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:////"):
        db_path = database_url[len("sqlite:///"):]
        if not os.path.isabs(db_path):
            db_path = Path(os.path.dirname(__file__)) / db_path
        else:
            db_path = Path(db_path)
        database_url = "sqlite:///" + db_path.resolve().as_posix()

    # ── FIX (critical): No weak default secret keys ────────────────────────────
    secret_key = os.getenv("SECRET_KEY")
    jwt_secret_key = os.getenv("JWT_SECRET_KEY")

    if env == "production":
        if not secret_key:
            raise RuntimeError("SECRET_KEY must be set in production.")
        if not jwt_secret_key:
            raise RuntimeError("JWT_SECRET_KEY must be set in production.")
    else:
        import secrets as _secrets
        secret_key     = secret_key     or _secrets.token_hex(32)
        jwt_secret_key = jwt_secret_key or _secrets.token_hex(32)

    # ── FIX (high): JWT expiry must be timedelta, not a plain int ─────────────
    app.config.update(
        SECRET_KEY                     = secret_key,
        JWT_SECRET_KEY                 = jwt_secret_key,
        JWT_ACCESS_TOKEN_EXPIRES       = timedelta(seconds=int(os.getenv("JWT_ACCESS_EXPIRES",  3600))),
        JWT_REFRESH_TOKEN_EXPIRES      = timedelta(seconds=int(os.getenv("JWT_REFRESH_EXPIRES", 604800))),

        SQLALCHEMY_DATABASE_URI        = database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS = False,
        SQLALCHEMY_ENGINE_OPTIONS      = {"pool_recycle": 280, "pool_pre_ping": True},

        UPLOAD_FOLDER       = os.getenv("UPLOAD_FOLDER", os.path.join(os.path.dirname(__file__), "uploads")),
        MAX_CONTENT_LENGTH  = 10 * 1024 * 1024,

        MAIL_SERVER         = os.getenv("MAIL_SERVER",  "smtp.gmail.com"),
        MAIL_PORT           = int(os.getenv("MAIL_PORT", 587)),
        MAIL_USE_TLS        = True,
        MAIL_USERNAME       = os.getenv("MAIL_USERNAME", ""),
        MAIL_PASSWORD       = os.getenv("MAIL_PASSWORD", ""),
        MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply@lexbridge.in"),

        BASE_URL = os.getenv("BASE_URL", "http://localhost:5000"),
    )

    if env == "testing":
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["TESTING"] = True

    # ── FIX (critical): CORS must never default to '*' in production ──────────
    cors_origins_raw = os.getenv("CORS_ORIGINS", "")
    if env == "production":
        if not cors_origins_raw:
            raise RuntimeError("CORS_ORIGINS must be set in production, e.g. https://yourdomain.com")
        cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    elif env == "testing":
        cors_origins = "*"
    else:
        cors_origins = cors_origins_raw.split(",") if cors_origins_raw else [
            "http://localhost:8080", "http://localhost:3000", "http://127.0.0.1:8080",
        ]

    CORS(app, resources={r"/api/*": {"origins": cors_origins}})

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(lawyer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(match_bp)

    # ── Serve frontend pages and assets ─────────────────────────────────────────
    @limiter.exempt
    @app.get("/")
    def index_page():
        return send_from_directory(app.root_path, "index.html")

    @limiter.exempt
    @app.get("/<path:filename>")
    def serve_frontend(filename: str):
        allowed_html = {
            "index.html", "login.html", "signup.html", "client_dashboard.html",
            "lawyer_dashboard.html", "admin_panel.html", "verify_email.html",
            "reset_password.html", "404.html"
        }
        if filename in allowed_html:
            return send_from_directory(app.root_path, filename)
        for folder in ("scripts", "styles", "uploads"):
            if filename.startswith(folder + "/"):
                return send_from_directory(app.root_path, filename)
        return jsonify(error="Resource not found."), 404

    # ── Messaging routes ──────────────────────────────────────────────────────
    from flask import request
    from flask_jwt_extended import jwt_required, get_jwt_identity
    from services.messaging_service import (
        get_or_create_conversation, send_message, get_messages, mark_messages_read
    )

    @app.post("/api/messages/send")
    @jwt_required()
    def api_send_message():
        sender_id    = int(get_jwt_identity())
        data         = request.get_json(silent=True) or {}
        recipient_id = data.get("recipient_id")
        content      = (data.get("content") or "").strip()
        case_id      = data.get("case_id")

        if not recipient_id or not content:
            return jsonify(error="recipient_id and content are required."), 400

        conv_id = get_or_create_conversation(sender_id, recipient_id, case_id)
        msg     = send_message(conv_id, sender_id, content)
        return jsonify(message=msg), 201

    @app.get("/api/messages/<int:conversation_id>")
    @jwt_required()
    def api_get_messages(conversation_id: int):
        from models.conversation_model import Conversation
        reader_id = int(get_jwt_identity())

        # FIX (high): verify the requesting user is a participant in this conversation
        conv = Conversation.query.get_or_404(conversation_id)
        if reader_id not in (conv.participant_a, conv.participant_b):
            return jsonify(error="Forbidden."), 403

        before = request.args.get("before_id", type=int)
        msgs   = get_messages(conversation_id, limit=50, before_id=before)
        mark_messages_read(conversation_id, reader_id)
        return jsonify(messages=msgs), 200

    # ── Error Handlers ────────────────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):   return jsonify(error=str(e)), 400

    @app.errorhandler(401)
    def unauthorized(e):  return jsonify(error="Unauthorized."), 401

    @app.errorhandler(403)
    def forbidden(e):     return jsonify(error="Forbidden."), 403

    @app.errorhandler(404)
    def not_found(e):     return jsonify(error="Resource not found."), 404

    @app.errorhandler(413)
    def too_large(e):     return jsonify(error="File too large. Maximum is 10 MB."), 413

    @app.errorhandler(429)
    def rate_limit(e):    return jsonify(error="Too many requests. Please slow down."), 429

    @app.errorhandler(500)
    def server_error(e):  return jsonify(error="Internal server error."), 500

    # ── JWT error handlers ────────────────────────────────────────────────────
    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return jsonify(error="Token has expired."), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify(error=f"Invalid token: {reason}"), 401

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify(error="Authorization token missing."), 401

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/api/health")
    def health():
        return jsonify(status="ok", env=env), 200

    # ── FIX (medium): run db.create_all() inside create_app so Gunicorn works ─
    with app.app_context():
        db.create_all()
        _auto_migrate()
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    return app


def _auto_migrate() -> None:
    """Tiny ad-hoc migration runner for columns added after the initial schema.

    SQLAlchemy's create_all() only adds missing *tables*, never missing
    *columns*. This helper checks the live schema and issues ALTER TABLE when
    needed. Safe to run repeatedly — it's a no-op if the column exists.
    """
    from sqlalchemy import inspect, text
    try:
        insp = inspect(db.engine)
        if "lawyer_profiles" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("lawyer_profiles")}
            if "per_hearing_fee" not in cols:
                db.session.execute(text(
                    "ALTER TABLE lawyer_profiles ADD COLUMN per_hearing_fee DECIMAL(10,2) NULL"
                ))
                db.session.commit()
    except Exception:
        db.session.rollback()  # best-effort; app still boots


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    application = create_app()
    port  = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    application.run(host="0.0.0.0", port=port, debug=debug)
