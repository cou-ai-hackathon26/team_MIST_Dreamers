"""Up to two services kept in one text column, e.g. `messages.service_id` (no DB migration).

"old_age_allowance,widow_allowance" <-> ("old_age_allowance", "widow_allowance").
"""

SEPARATOR = ","


class ServiceSet:
    @staticmethod
    def format(ids: tuple[str, ...] | list[str]) -> str:
        """Joins the ids in order, dropping empty and repeated ones."""
        seen: list[str] = []
        for raw in ids:
            item = raw.strip()
            if item and item not in seen:
                seen.append(item)
        return SEPARATOR.join(seen)

    @staticmethod
    def parse(text: str | None) -> tuple[str, ...]:
        """The ids in the stored order; an old single id gives a 1-tuple, None or "" gives ()."""
        joined = ServiceSet.format((text or "").split(SEPARATOR))
        return tuple(joined.split(SEPARATOR)) if joined else ()
