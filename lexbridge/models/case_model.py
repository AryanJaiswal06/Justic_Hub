# models/case_model.py — Case, CaseUpdate, Conversation, Message, Rating
from datetime import datetime
from extensions import db


class Case(db.Model):
    __tablename__ = "cases"

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    case_number  = db.Column(db.String(30),  nullable=False, unique=True)
    client_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    lawyer_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),  nullable=True)
    case_type    = db.Column(db.String(80),  nullable=False)
    title        = db.Column(db.String(255), nullable=False)
    description  = db.Column(db.Text,        nullable=True)
    priority     = db.Column(db.Enum("low", "medium", "high", "urgent"), nullable=False, default="medium")
    status       = db.Column(db.Enum("pending", "active", "in_progress", "closed", "dismissed"), nullable=False, default="pending")
    stage        = db.Column(db.String(80),  nullable=True)
    next_hearing = db.Column(db.Date,         nullable=True)
    opened_at    = db.Column(db.DateTime,     nullable=False, default=datetime.utcnow)
    closed_at    = db.Column(db.DateTime,     nullable=True)
    updated_at   = db.Column(db.DateTime,     nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    client  = db.relationship("User", foreign_keys=[client_id])
    lawyer  = db.relationship("User", foreign_keys=[lawyer_id])
    updates = db.relationship("CaseUpdate", back_populates="case", cascade="all, delete-orphan", order_by="CaseUpdate.created_at")

    @staticmethod
    def generate_case_number() -> str:
        import random, string
        prefix = "LC"
        suffix = "".join(random.choices(string.digits, k=6))
        return f"{prefix}-{suffix}"

    def to_dict(self, include_updates: bool = False) -> dict:
        data = {
            "id":           self.id,
            "case_number":  self.case_number,
            "client_id":    self.client_id,
            "lawyer_id":    self.lawyer_id,
            "case_type":    self.case_type,
            "title":        self.title,
            "description":  self.description,
            "priority":     self.priority,
            "status":       self.status,
            "stage":        self.stage,
            "next_hearing": self.next_hearing.isoformat() if self.next_hearing else None,
            "opened_at":    self.opened_at.isoformat()    if self.opened_at    else None,
            "closed_at":    self.closed_at.isoformat()    if self.closed_at    else None,
            "updated_at":   self.updated_at.isoformat()   if self.updated_at   else None,
        }
        if self.client:
            data["client_name"] = self.client.full_name
        if self.lawyer:
            data["lawyer_name"] = self.lawyer.full_name
        if include_updates:
            data["updates"] = [u.to_dict() for u in self.updates]
        return data


class CaseUpdate(db.Model):
    __tablename__ = "case_updates"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    case_id     = db.Column(db.Integer, db.ForeignKey("cases.id",  ondelete="CASCADE"), nullable=False)
    author_id   = db.Column(db.Integer, db.ForeignKey("users.id",  ondelete="CASCADE"), nullable=False)
    update_type = db.Column(db.Enum("status_change", "note", "hearing_scheduled", "document_added", "lawyer_assigned"), nullable=False)
    content     = db.Column(db.Text,     nullable=False)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    case   = db.relationship("Case",  back_populates="updates")
    author = db.relationship("User",  foreign_keys=[author_id])

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "case_id":     self.case_id,
            "author_id":   self.author_id,
            "author_name": self.author.full_name if self.author else None,
            "update_type": self.update_type,
            "content":     self.content,
            "created_at":  self.created_at.isoformat(),
        }


class Conversation(db.Model):
    __tablename__ = "conversations"

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    case_id         = db.Column(db.Integer, db.ForeignKey("cases.id",  ondelete="SET NULL"), nullable=True)
    participant_a   = db.Column(db.Integer, db.ForeignKey("users.id",  ondelete="CASCADE"),  nullable=False)
    participant_b   = db.Column(db.Integer, db.ForeignKey("users.id",  ondelete="CASCADE"),  nullable=False)
    last_message_at = db.Column(db.DateTime, nullable=True)
    created_at      = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user_a    = db.relationship("User", foreign_keys=[participant_a])
    user_b    = db.relationship("User", foreign_keys=[participant_b])
    messages  = db.relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "case_id":         self.case_id,
            "participant_a":   self.participant_a,
            "participant_b":   self.participant_b,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "created_at":      self.created_at.isoformat(),
        }


class Message(db.Model):
    __tablename__ = "messages"

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id       = db.Column(db.Integer, db.ForeignKey("users.id",          ondelete="CASCADE"), nullable=False)
    content         = db.Column(db.Text,     nullable=False)
    is_read         = db.Column(db.Boolean,  nullable=False, default=False)
    sent_at         = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    conversation = db.relationship("Conversation", back_populates="messages")
    sender       = db.relationship("User", foreign_keys=[sender_id])

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "conversation_id": self.conversation_id,
            "sender_id":       self.sender_id,
            "sender_name":     self.sender.full_name if self.sender else None,
            "content":         self.content,
            "is_read":         self.is_read,
            "sent_at":         self.sent_at.isoformat(),
        }


class Rating(db.Model):
    __tablename__ = "ratings"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    case_id     = db.Column(db.Integer, db.ForeignKey("cases.id",  ondelete="CASCADE"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id",  ondelete="CASCADE"), nullable=False)
    lawyer_id   = db.Column(db.Integer, db.ForeignKey("users.id",  ondelete="CASCADE"), nullable=False)
    score       = db.Column(db.SmallInteger, nullable=False)
    review      = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("case_id", "reviewer_id", name="uq_rating"),)

    reviewer = db.relationship("User", foreign_keys=[reviewer_id])
    lawyer   = db.relationship("User", foreign_keys=[lawyer_id])

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "case_id":       self.case_id,
            "reviewer_id":   self.reviewer_id,
            "lawyer_id":     self.lawyer_id,
            "score":         self.score,
            "review":        self.review,
            "reviewer_name": self.reviewer.full_name if self.reviewer else None,
            "created_at":    self.created_at.isoformat(),
        }
