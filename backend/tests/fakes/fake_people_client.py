"""In-memory fake PeopleClient for deterministic tests (no live Google — Principle IV)."""
from __future__ import annotations

from src.integrations.people_client import ConnectionsPage


def make_person(i: int, *, full: bool = False) -> dict:
    person: dict = {
        "resourceName": f"people/c{i}",
        "etag": f"etag{i}",
        "names": [{"displayName": f"Contact {i}", "metadata": {"primary": True}}],
        "emailAddresses": [{"value": f"contact{i}@example.com", "metadata": {"primary": True}}],
        "phoneNumbers": [{"value": f"+100000{i:04d}", "metadata": {"primary": True}}],
    }
    if full:
        person.update(
            {
                "addresses": [{"formattedValue": f"{i} Main St"}],
                "organizations": [{"name": f"Org {i}"}],
                "biographies": [{"value": f"note {i}"}],
                "memberships": [{"contactGroupMembership": {"contactGroupId": "friends"}}],
                "photos": [{"url": f"https://photos.example/{i}.jpg"}],
            }
        )
    return person


class FakePeopleClient:
    """Paginates a fixed list of people. Optionally injects errors per call."""

    def __init__(self, people: list[dict], *, page_size: int = 2, errors: list | None = None,
                 sync_token: str = "SYNC123"):
        self._people = people
        self._page_size = page_size
        self._errors = errors or []  # list of exceptions to raise on successive calls
        self._sync_token = sync_token
        self.calls = 0

    def list_connections(self, page_token: str | None) -> ConnectionsPage:
        self.calls += 1
        if self._errors:
            err = self._errors.pop(0)
            if err is not None:
                raise err
        start = int(page_token) if page_token else 0
        chunk = self._people[start : start + self._page_size]
        next_start = start + self._page_size
        has_more = next_start < len(self._people)
        return ConnectionsPage(
            people=chunk,
            next_page_token=str(next_start) if has_more else None,
            next_sync_token=None if has_more else self._sync_token,
            total_estimate=len(self._people),
        )
