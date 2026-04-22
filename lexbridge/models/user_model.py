# models/user_model.py — User, LawyerProfile, AuthToken
import uuid as _uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(db.Model):
    __tablename__ = "users"

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uuid           = db.Column(db.String(36), nullable=False, unique=True, default=lambda: str(_uuid.uuid4()))
    full_name      = db.Column(db.String(120), nullable=False)
    email          = db.Column(db.String(180), nullable=False, unique=True)
    phone          = db.Column(db.String(20),  nullable=True)
    password_hash  = db.Column(db.String(255), nullable=False)
    role           = db.Column(db.Enum("client", "lawyer", "admin"), nullable=False, default="client")
    avatar_url     = db.Column(db.String(500), nullable=True)
    is_active      = db.Column(db.Boolean, nullable=False, default=True)
    is_verified    = db.Column(db.Boolean, nullable=False, default=False)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login     = db.Column(db.DateTime, nullable=True)

    # Relationships
    lawyer_profile = db.relationship("LawyerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan", foreign_keys="LawyerProfile.user_id")
    auth_tokens    = db.relationship("AuthToken",     back_populates="user", cascade="all, delete-orphan")
    notifications  = db.relationship("Notification",  back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_private: bool = False) -> dict:
        data = {
            "id":             self.id,
            "uuid":           self.uuid,
            "full_name":      self.full_name,
            "email":          self.email,
            "phone":          self.phone,
            "role":           self.role,
            "avatar_url":     self.avatar_url,
            "is_active":      self.is_active,
            "is_verified":    self.is_verified,
            "email_verified": self.email_verified,
            "created_at":     self.created_at.isoformat() if self.created_at else None,
            "last_login":     self.last_login.isoformat()  if self.last_login  else None,
        }
        if self.lawyer_profile:
            data["lawyer_profile"] = self.lawyer_profile.to_dict()
        return data

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email} [{self.role}]>"


class LawyerProfile(db.Model):
    __tablename__ = "lawyer_profiles"

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id             = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    bar_council_no      = db.Column(db.String(50),  nullable=False)
    specializations     = db.Column(db.JSON,         nullable=True)
    experience_years    = db.Column(db.SmallInteger, nullable=False, default=0)
    court_levels        = db.Column(db.JSON,         nullable=True)
    languages           = db.Column(db.JSON,         nullable=True)
    bio                 = db.Column(db.Text,          nullable=True)
    consultation_fee    = db.Column(db.Numeric(10, 2), nullable=True)
    per_hearing_fee     = db.Column(db.Numeric(10, 2), nullable=True)  # NEW: per-hearing rate for budget filtering
    availability_status = db.Column(db.Enum("available", "busy", "offline"), nullable=False, default="available")
    avg_rating          = db.Column(db.Numeric(3, 2), nullable=False, default=0.00)
    total_ratings       = db.Column(db.Integer, nullable=False, default=0)
    total_cases         = db.Column(db.Integer, nullable=False, default=0)
    verified_at         = db.Column(db.DateTime, nullable=True)
    verified_by         = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user    = db.relationship("User", back_populates="lawyer_profile", foreign_keys=[user_id])
    verifier = db.relationship("User", foreign_keys=[verified_by])

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "user_id":             self.user_id,
            "bar_council_no":      self.bar_council_no,
            "specializations":     self.specializations,
            "experience_years":    self.experience_years,
            "court_levels":        self.court_levels,
            "languages":           self.languages,
            "bio":                 self.bio,
            "consultation_fee":    float(self.consultation_fee) if self.consultation_fee else None,
            "per_hearing_fee":     float(self.per_hearing_fee)  if self.per_hearing_fee  else None,
            "availability_status": self.availability_status,
            "avg_rating":          float(self.avg_rating),
            "total_ratings":       self.total_ratings,
            "total_cases":         self.total_cases,
            "verified_at":         self.verified_at.isoformat() if self.verified_at else None,
        }


class AuthToken(db.Model):
    __tablename__ = "auth_tokens"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token      = db.Column(db.String(120), nullable=False, unique=True)
    token_type = db.Column(db.Enum("email_verify", "password_reset", "otp"), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at    = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="auth_tokens")

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None
