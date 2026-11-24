"""Use case: delete one checklist from a phone number's history (NFR-PRIV-03).

The app's History page lets the user choose which answers to delete. Only this number's checklist
can be deleted: an id that belongs to another number counts as "not found".
"""

from app.application.ports.repositories import ChecklistRepo
from app.domain.errors import NotFound
from app.domain.value_objects import PhoneNumber


class DeleteChecklist:
    def __init__(self, checklists: ChecklistRepo) -> None:
        self._checklists = checklists

    def execute(self, phone: str, checklist_id: str) -> None:
        number = PhoneNumber.parse(phone)  # raises InvalidPhone (422)
        if not self._checklists.delete_one(number, checklist_id.strip()):
            raise NotFound(f"checklist {checklist_id!r}")
