"""Use cases: show and delete a phone number's history (FR-APP-05, NFR-PRIV-03).

Phone calls and the app share one history per number, so a checklist from a call shows in the app (S5).
"""

from app.application.dto import HistoryResult
from app.application.ports.repositories import ChecklistRepo, ConversationRepo
from app.domain.value_objects import PhoneNumber

MAX_LIMIT = 200


class GetHistory:
    def __init__(self, conversations: ConversationRepo, checklists: ChecklistRepo) -> None:
        self._conversations = conversations
        self._checklists = checklists

    def execute(self, phone: str, limit: int = 50) -> HistoryResult:
        number = PhoneNumber.parse(phone)  # raises InvalidPhone
        limit = max(1, min(limit, MAX_LIMIT))
        return HistoryResult(
            phone=number.e164,
            messages=tuple(self._conversations.recent_messages(number, limit)),
            checklists=tuple(self._checklists.list_for_phone(number, limit)),
        )


class DeleteHistory:
    def __init__(self, conversations: ConversationRepo, checklists: ChecklistRepo) -> None:
        self._conversations = conversations
        self._checklists = checklists

    def execute(self, phone: str) -> bool:
        """True if anything was deleted (messages or checklists)."""
        number = PhoneNumber.parse(phone)
        removed_conversation = self._conversations.delete_for_phone(number)
        removed_checklists = self._checklists.delete_for_phone(number)
        return removed_conversation or removed_checklists > 0
