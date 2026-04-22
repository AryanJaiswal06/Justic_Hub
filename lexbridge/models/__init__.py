# models package — exports all database models so they're registered with SQLAlchemy.
# Importing from `models` also works (e.g. `from models import Case`).

from .user_model     import User, LawyerProfile, AuthToken
from .case_model     import Case, CaseUpdate, Conversation, Message, Rating
from .document_model import Document, Notification, Payment, Dispute
from .request_model  import CaseRequest

__all__ = [
    "User", "LawyerProfile", "AuthToken",
    "Case", "CaseUpdate", "Conversation", "Message", "Rating",
    "Document", "Notification", "Payment", "Dispute",
    "CaseRequest",
]
