# models/request_model.py — CaseRequest: two-way interest/assignment workflow
#
# A CaseRequest represents either:
#   • A CLIENT requesting a specific LAWYER to handle their case
#   • A LAWYER expressing interest in an unassigned CASE
#
# The receiving party (lawyer for client-initiated, client for lawyer-initiated)
# can ACCEPT or REJECT. On acceptance, the case is assigned to the lawyer.

from datetime import datetime
from extensions import db


class CaseRequest(db.Model):
    __tablename__ = "case_requests"

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    case_id       = db.Column(db.Integer, db.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    client_id     = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lawyer_id     = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    initiated_by  = db.Column(db.Enum("client", "lawyer", name="req_initiated_by"), nullable=False)
    message       = db.Column(db.Text, nullable=True)
    status        = db.Column(
        db.Enum("pending", "accepted", "rejected", "withdrawn", name="req_status"),
        nullable=False, default="pending",
    )
    created_at    = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    responded_at  = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        # Prevent duplicate pending requests between the same pair for the same case
        db.UniqueConstraint("case_id", "client_id", "lawyer_id", "initiated_by",
                            name="uq_case_request_pair"),
    )

    # Relationships
    case   = db.relationship("Case",  foreign_keys=[case_id])
    client = db.relationship("User",  foreign_keys=[client_id])
    lawyer = db.relationship("User",  foreign_keys=[lawyer_id])

    def to_dict(self) -> dict:
        data = {
            "id":           self.id,
            "case_id":      self.case_id,
            "client_id":    self.client_id,
            "lawyer_id":    self.lawyer_id,
            "initiated_by": self.initiated_by,
            "message":      self.message,
            "status":       self.status,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
        }
        if self.case:
            data["case_title"]  = self.case.title
            data["case_number"] = self.case.case_number
            data["case_type"]   = self.case.case_type
            data["case_priority"] = self.case.priority
        if self.client:
            data["client_name"]  = self.client.full_name
            data["client_email"] = self.client.email
            data["client_phone"] = self.client.phone
        if self.lawyer:
            data["lawyer_name"]  = self.lawyer.full_name
            data["lawyer_email"] = self.lawyer.email
            data["lawyer_phone"] = self.lawyer.phone
            if self.lawyer.lawyer_profile:
                data["lawyer_specializations"] = self.lawyer.lawyer_profile.specializations
                data["lawyer_experience"]     = self.lawyer.lawyer_profile.experience_years
                data["lawyer_fee"]            = (
                    float(self.lawyer.lawyer_profile.consultation_fee)
                    if self.lawyer.lawyer_profile.consultation_fee else None
                )
        return data

    def __repr__(self) -> str:
        return (
            f"<CaseRequest {self.id} case={self.case_id} "
            f"client={self.client_id} lawyer={self.lawyer_id} "
            f"by={self.initiated_by} status={self.status}>"
        )
