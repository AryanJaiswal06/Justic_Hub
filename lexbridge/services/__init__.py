# services package — re-exports helper services.
from .notification_service import (
    create_notification,
    notify_case_update,
    notify_new_message,
    notify_payment,
    notify_lawyer_verified,
    send_verification_email,
    send_password_reset_email,
    send_case_accepted_email,
    send_lawyer_verified_email,
)
from .messaging_service import (
    get_or_create_conversation,
    send_message,
    get_messages,
    mark_messages_read,
    get_conversations_for_user,
)

__all__ = [
    "create_notification", "notify_case_update", "notify_new_message",
    "notify_payment", "notify_lawyer_verified",
    "send_verification_email", "send_password_reset_email",
    "send_case_accepted_email", "send_lawyer_verified_email",
    "get_or_create_conversation", "send_message", "get_messages",
    "mark_messages_read", "get_conversations_for_user",
]
