#!/usr/bin/env python3
"""
manage.py — LexBridge CLI management tool

Usage:
    python manage.py create_admin
    python manage.py create_admin --email admin@lexbridge.in --password MyStr0ngP@ss
    python manage.py list_users
    python manage.py reset_db        # drops & recreates all tables (dev only)
"""
import sys
import getpass
import argparse
from dotenv import load_dotenv

load_dotenv()


def get_app():
    from app import create_app
    return create_app()


# ── create_admin ──────────────────────────────────────────────────────────────

def cmd_create_admin(args):
    app = get_app()
    with app.app_context():
        from extensions import db
        from models.user_model import User

        email = args.email or input("Admin email: ").strip().lower()
        name  = args.name  or input("Full name  : ").strip()

        if args.password:
            password = args.password
        else:
            password = getpass.getpass("Password   : ")
            confirm  = getpass.getpass("Confirm    : ")
            if password != confirm:
                print("❌  Passwords do not match.")
                sys.exit(1)

        if len(password) < 8:
            print("❌  Password must be at least 8 characters.")
            sys.exit(1)

        existing = User.query.filter_by(email=email).first()
        if existing:
            if existing.role == "admin":
                print(f"⚠️   Admin '{email}' already exists.")
            else:
                existing.role = "admin"
                existing.is_active = True
                existing.is_verified = True
                existing.email_verified = True
                existing.set_password(password)
                db.session.commit()
                print(f"✅  Existing user '{email}' promoted to admin.")
            return

        admin = User(
            full_name=name,
            email=email,
            role="admin",
            is_active=True,
            is_verified=True,
            email_verified=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"✅  Admin account created: {email} (id={admin.id})")


# ── list_users ────────────────────────────────────────────────────────────────

def cmd_list_users(args):
    app = get_app()
    with app.app_context():
        from models.user_model import User
        users = User.query.order_by(User.created_at.desc()).limit(50).all()
        print(f"\n{'ID':<6} {'Role':<8} {'Name':<25} {'Email':<35} {'Active'}")
        print("-" * 82)
        for u in users:
            print(f"{u.id:<6} {u.role:<8} {u.full_name[:24]:<25} {u.email[:34]:<35} {'✅' if u.is_active else '❌'}")
        print(f"\n{len(users)} user(s) shown.\n")


# ── reset_db ──────────────────────────────────────────────────────────────────

def cmd_reset_db(args):
    env = __import__("os").getenv("FLASK_ENV", "development")
    if env == "production":
        print("❌  reset_db is not allowed in production.")
        sys.exit(1)

    confirm = input("⚠️  This will DROP and recreate all tables. Type 'yes' to confirm: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        return

    app = get_app()
    with app.app_context():
        from extensions import db
        db.drop_all()
        db.create_all()
        print("✅  Database reset complete.")


def cmd_clear_users(args):
    app = get_app()
    with app.app_context():
        from sqlalchemy import or_
        from extensions import db
        from models.user_model import User
        from models.case_model import Case, Rating, CaseRequest, Conversation, Message, CaseUpdate
        from models.document_model import Document, Notification, Payment, Dispute

        users = User.query.filter(User.role != 'admin').all()
        if not users:
            print("✅  No client or lawyer accounts found.")
            return

        user_ids = [u.id for u in users]
        print(f"Deleting {len(user_ids)} non-admin user(s) and related data...")

        Payment.query.filter(or_(Payment.client_id.in_(user_ids), Payment.lawyer_id.in_(user_ids))).delete(synchronize_session=False)
        CaseRequest.query.filter(or_(CaseRequest.client_id.in_(user_ids), CaseRequest.lawyer_id.in_(user_ids))).delete(synchronize_session=False)
        Rating.query.filter(or_(Rating.reviewer_id.in_(user_ids), Rating.lawyer_id.in_(user_ids))).delete(synchronize_session=False)
        CaseUpdate.query.filter(CaseUpdate.author_id.in_(user_ids)).delete(synchronize_session=False)
        Message.query.filter(Message.sender_id.in_(user_ids)).delete(synchronize_session=False)
        Conversation.query.filter(or_(Conversation.participant_a.in_(user_ids), Conversation.participant_b.in_(user_ids))).delete(synchronize_session=False)
        Document.query.filter(Document.uploaded_by.in_(user_ids)).delete(synchronize_session=False)
        Notification.query.filter(Notification.user_id.in_(user_ids)).delete(synchronize_session=False)
        Dispute.query.filter(or_(Dispute.filed_by.in_(user_ids), Dispute.against.in_(user_ids), Dispute.resolved_by.in_(user_ids))).delete(synchronize_session=False)
        Case.query.filter(or_(Case.client_id.in_(user_ids), Case.lawyer_id.in_(user_ids))).delete(synchronize_session=False)
        User.query.filter(User.role != 'admin').delete(synchronize_session=False)

        db.session.commit()
        print("✅  Deleted all client and lawyer accounts and related records.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LexBridge management CLI")
    sub    = parser.add_subparsers(dest="command")

    # create_admin
    p_admin = sub.add_parser("create_admin", help="Create an admin user")
    p_admin.add_argument("--email",    default="", help="Admin email address")
    p_admin.add_argument("--name",     default="Platform Admin", help="Full name")
    p_admin.add_argument("--password", default="", help="Password (prompted if omitted)")

    # clear_users
    sub.add_parser("clear_users", help="Delete all client and lawyer accounts and their related data")

    # list_users
    sub.add_parser("list_users", help="List registered users")

    # reset_db
    sub.add_parser("reset_db", help="Drop and recreate all tables (dev only)")

    args = parser.parse_args()

    dispatch = {
        "create_admin": cmd_create_admin,
        "clear_users":  cmd_clear_users,
        "list_users":   cmd_list_users,
        "reset_db":     cmd_reset_db,
    }

    if args.command not in dispatch:
        parser.print_help()
        sys.exit(1)

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
