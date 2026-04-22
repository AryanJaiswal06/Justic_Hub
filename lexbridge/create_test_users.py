#!/usr/bin/env python3
from app import create_app
app = create_app()
with app.app_context():
    from models.user_model import User, LawyerProfile
    from extensions import db

    # Check if admin exists
    admin = User.query.filter_by(role='admin').first()
    if admin:
        print(f"Admin already exists: {admin.email}")
    else:
        admin = User(
            full_name="System Admin",
            email="admin@lexbridge.com",
            role="admin",
            is_active=True,
            is_verified=True,
            email_verified=True,
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print(f"Admin created: {admin.email}")

    # Create test client
    client = User.query.filter_by(email='client@test.com').first()
    if not client:
        client = User(
            full_name="Test Client",
            email="client@test.com",
            phone="1234567890",
            role="client",
            is_active=True,
            is_verified=True,
            email_verified=True,
        )
        client.set_password("client123")
        db.session.add(client)
        db.session.commit()
        print(f"Client created: {client.email}")

    # Create test lawyer
    lawyer = User.query.filter_by(email='lawyer@test.com').first()
    if not lawyer:
        lawyer = User(
            full_name="Test Lawyer",
            email="lawyer@test.com",
            phone="9876543210",
            role="lawyer",
            is_active=True,
            is_verified=False,
            email_verified=True,
        )
        lawyer.set_password("lawyer123")
        db.session.add(lawyer)
        db.session.commit()  # Commit the lawyer first
        
        # Create lawyer profile
        profile = LawyerProfile(
            user_id=lawyer.id,
            bar_council_no="ABC123",
            specializations=["Criminal Law", "Civil Law"],
            experience_years=5,
        )
        db.session.add(profile)
        db.session.commit()
        print(f"Lawyer created: {lawyer.email}")
    
    # List all users
    users = User.query.all()
    print(f"\nTotal users: {len(users)}")
    for u in users:
        lawyer_info = ""
        if u.lawyer_profile:
            lawyer_info = f" (Bar: {u.lawyer_profile.bar_council_no}, Verified: {u.lawyer_profile.verified_at is not None})"
        print(f"  {u.id}: {u.email} ({u.role}){lawyer_info}")