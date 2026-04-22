# models/document_model.py — Document, Notification, Payment, Dispute
from datetime import datetime
from extensions import db


class Document(db.Model):
    __tablename__ = "documents"

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    case_id         = db.Column(db.Integer, db.ForeignKey("cases.id",  ondelete="SET NULL"), nullable=True)
    uploaded_by     = db.Column(db.Integer, db.ForeignKey("users.id",  ondelete="CASCADE"),  nullable=False)
    file_name       = db.Column(db.String(255), nullable=False)   # stored filename (uuid-based)
    original_name   = db.Column(db.String(255), nullable=False)   # original user filename
    mime_type       = db.Column(db.String(100), nullable=False)
    file_size_bytes = db.Column(db.Integer, nullable=False)
    storage_path    = db.Column(db.String(500), nullable=False)
    doc_type        = db.Column(db.Enum("evidence", "contract", "petition", "judgment", "identity", "other"), nullable=False, default="other")
    status          = db.Column(db.Enum("pending", "under_review", "verified", "rejected"), nullable=False, default="pending")
    reviewed_by     = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at     = db.Column(db.DateTime, nullable=True)
    uploaded_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    uploader = db.relationship("User", foreign_keys=[uploaded_by])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "case_id":         self.case_id,
            "uploaded_by":     self.uploaded_by,
            "uploader_name":   self.uploader.full_name if self.uploader else None,
            "file_name":       self.file_name,
            "original_name":   self.original_name,
            "mime_type":       self.mime_type,
            "file_size_bytes": self.file_size_bytes,
            "doc_type":        self.doc_type,
            "status":          self.status,
            "reviewed_at":     self.reviewed_at.isoformat() if self.reviewed_at else None,
            "uploaded_at":     self.uploaded_at.isoformat(),
        }


class Notification(db.Model):
    __tablename__ = "notifications"

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type       = db.Column(db.String(60),  nullable=False)
    title      = db.Column(db.String(200), nullable=False)
    body       = db.Column(db.Text,         nullable=True)
    link       = db.Column(db.String(300),  nullable=True)
    is_read    = db.Column(db.Boolean,      nullable=False, default=False)
    created_at = db.Column(db.DateTime,     nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="notifications")

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "user_id":    self.user_id,
            "type":       self.type,
            "title":      self.title,
            "body":       self.body,
            "link":       self.link,
            "is_read":    self.is_read,
            "created_at": self.created_at.isoformat(),
        }


class Payment(db.Model):
    __tablename__ = "payments"

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    case_id        = db.Column(db.Integer, db.ForeignKey("cases.id",  ondelete="RESTRICT"), nullable=False)
    client_id      = db.Column(db.Integer, db.ForeignKey("users.id",  ondelete="RESTRICT"), nullable=False)
    lawyer_id      = db.Column(db.Integer, db.ForeignKey("users.id",  ondelete="RESTRICT"), nullable=False)
    amount         = db.Column(db.Numeric(12, 2), nullable=False)
    currency       = db.Column(db.String(3),  nullable=False, default="INR")
    gateway_txn_id = db.Column(db.String(120), nullable=True, unique=True)
    payment_type   = db.Column(db.Enum("consultation", "retainer", "milestone", "final"), nullable=False)
    status         = db.Column(db.Enum("pending", "completed", "failed", "refunded"), nullable=False, default="pending")
    paid_at        = db.Column(db.DateTime, nullable=True)
    created_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    client = db.relationship("User", foreign_keys=[client_id])
    lawyer = db.relationship("User", foreign_keys=[lawyer_id])

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "case_id":        self.case_id,
            "client_id":      self.client_id,
            "lawyer_id":      self.lawyer_id,
            "amount":         float(self.amount),
            "currency":       self.currency,
            "gateway_txn_id": self.gateway_txn_id,
            "payment_type":   self.payment_type,
            "status":         self.status,
            "paid_at":        self.paid_at.isoformat()   if self.paid_at    else None,
            "created_at":     self.created_at.isoformat(),
        }


class Dispute(db.Model):
    __tablename__ = "disputes"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filed_by    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),   nullable=False)
    against     = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),   nullable=False)
    case_id     = db.Column(db.Integer, db.ForeignKey("cases.id", ondelete="SET NULL"),  nullable=True)
    subject     = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text,         nullable=True)
    severity    = db.Column(db.Enum("low", "medium", "high"), nullable=False, default="medium")
    status      = db.Column(db.Enum("open", "investigating", "resolved", "dismissed"), nullable=False, default="open")
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    filer    = db.relationship("User", foreign_keys=[filed_by])
    accused  = db.relationship("User", foreign_keys=[against])
    resolver = db.relationship("User", foreign_keys=[resolved_by])

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "filed_by":    self.filed_by,
            "filer_name":  self.filer.full_name  if self.filer   else None,
            "against":     self.against,
            "accused_name":self.accused.full_name if self.accused else None,
            "case_id":     self.case_id,
            "subject":     self.subject,
            "description": self.description,
            "severity":    self.severity,
            "status":      self.status,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at":  self.created_at.isoformat(),
        }
