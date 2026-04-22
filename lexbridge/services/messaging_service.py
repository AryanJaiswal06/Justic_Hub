# services/messaging_service.py — Conversation & message helpers
from datetime import datetime
from extensions import db
from models.case_model import Conversation, Message


def get_or_create_conversation(user_a: int, user_b: int, case_id: int | None = None) -> int:
    """
    Return an existing conversation ID between two users (optionally scoped to a case),
    or create one. Deduplication is enforced here in code because MySQL UNIQUE with
    nullable case_id is unreliable (NULL != NULL in unique indexes).
    """
    # Normalise pair so (a,b) and (b,a) always map to the same row
    lo, hi = (user_a, user_b) if user_a < user_b else (user_b, user_a)

    query = Conversation.query.filter_by(participant_a=lo, participant_b=hi)
    if case_id:
        query = query.filter_by(case_id=case_id)
    else:
        query = query.filter(Conversation.case_id.is_(None))

    conv = query.first()
    if not conv:
        conv = Conversation(participant_a=lo, participant_b=hi, case_id=case_id)
        db.session.add(conv)
        db.session.commit()

    return conv.id


def send_message(conversation_id: int, sender_id: int, content: str) -> dict:
    """Persist a message and bump the conversation's last_message_at timestamp."""
    msg = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        content=content,
        sent_at=datetime.utcnow(),
    )
    db.session.add(msg)

    conv = Conversation.query.get(conversation_id)
    if conv:
        conv.last_message_at = msg.sent_at

    db.session.commit()
    return msg.to_dict()


def get_messages(conversation_id: int, limit: int = 50, before_id: int | None = None) -> list[dict]:
    """
    Return up to `limit` messages in a conversation, oldest-first.
    Optionally paginate backwards using `before_id` (cursor-based pagination).
    """
    query = Message.query.filter_by(conversation_id=conversation_id)
    if before_id:
        query = query.filter(Message.id < before_id)
    messages = query.order_by(Message.id.desc()).limit(limit).all()
    return [m.to_dict() for m in reversed(messages)]


def mark_messages_read(conversation_id: int, reader_id: int) -> int:
    """Mark all unread messages in the conversation that were NOT sent by the reader."""
    updated = (
        Message.query
        .filter_by(conversation_id=conversation_id, is_read=False)
        .filter(Message.sender_id != reader_id)
        .update({"is_read": True})
    )
    db.session.commit()
    return updated


def get_conversations_for_user(user_id: int) -> list[dict]:
    """Return all conversations a user participates in, most recently active first."""
    convs = (
        Conversation.query
        .filter(
            (Conversation.participant_a == user_id) |
            (Conversation.participant_b == user_id)
        )
        .order_by(Conversation.last_message_at.desc().nullslast())
        .all()
    )
    result = []
    for c in convs:
        d = c.to_dict()
        # Determine the "other" user from this user's perspective
        other_id = c.participant_b if c.participant_a == user_id else c.participant_a
        from models.user_model import User
        other = User.query.get(other_id)
        d["other_user_id"]   = other_id
        d["other_user_name"] = other.full_name if other else "Unknown"
        # Count unread messages for this user
        d["unread_count"] = (
            Message.query
            .filter_by(conversation_id=c.id, is_read=False)
            .filter(Message.sender_id != user_id)
            .count()
        )
        # Last message preview
        last = (
            Message.query
            .filter_by(conversation_id=c.id)
            .order_by(Message.id.desc())
            .first()
        )
        d["last_message"] = last.content[:80] if last else None
        result.append(d)
    return result
