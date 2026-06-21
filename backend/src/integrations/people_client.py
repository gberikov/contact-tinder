"""PeopleClient seam over the Google People API.

The seam lets tests inject a fake so CI never calls live Google (Constitution Principle IV).
The client performs ONE page fetch per call and raises typed errors; retry/backoff and cursor
persistence are the worker's responsibility (research D3/D9).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# personFields captured (FR-004 + identity metadata).
PERSON_FIELDS = (
    "names,nicknames,emailAddresses,phoneNumbers,addresses,organizations,"
    "biographies,birthdays,urls,memberships,photos,metadata"
)
PAGE_SIZE_MAX = 1000


class RateLimitedError(Exception):
    """429 / quota exceeded — transient, retryable."""

    def __init__(self, retry_after: float | None = None):
        super().__init__("rate limited")
        self.retry_after = retry_after


class TransientError(Exception):
    """5xx / network — transient, retryable."""


class AuthError(Exception):
    """401 / invalid_grant — token expired or revoked (FR-017)."""


class ContactNotFoundError(Exception):
    """404 on delete — the contact is already gone in Google (treat as success, FR-024)."""


@dataclass
class ConnectionsPage:
    people: list[dict]
    next_page_token: str | None
    next_sync_token: str | None
    total_estimate: int | None = None


class PeopleClient(Protocol):
    def list_connections(self, page_token: str | None) -> ConnectionsPage:
        """Fetch one page of the authenticated user's personal connections."""
        ...


class GooglePeopleClient:
    """Google-backed implementation. Constructed with an authorized credentials object."""

    def __init__(self, credentials, page_size: int = PAGE_SIZE_MAX):
        self._credentials = credentials
        self._page_size = min(page_size, PAGE_SIZE_MAX)

    def _service(self):
        # Imported lazily so tests that use a fake don't need google libs installed.
        from googleapiclient.discovery import build

        return build("people", "v1", credentials=self._credentials, cache_discovery=False)

    def list_connections(self, page_token: str | None) -> ConnectionsPage:
        from googleapiclient.errors import HttpError

        try:
            request = (
                self._service()
                .people()
                .connections()
                .list(
                    resourceName="people/me",
                    pageSize=self._page_size,
                    personFields=PERSON_FIELDS,
                    sources=["READ_SOURCE_TYPE_CONTACT"],
                    requestSyncToken=True,
                    pageToken=page_token,
                )
            )
            response = request.execute()
        except HttpError as exc:  # pragma: no cover - exercised via integration env
            status = getattr(exc.resp, "status", None)
            if status == 429:
                retry_after = exc.resp.get("retry-after") if exc.resp else None
                raise RateLimitedError(float(retry_after) if retry_after else None) from exc
            if status in (401, 403):
                raise AuthError() from exc
            if status and 500 <= int(status) < 600:
                raise TransientError() from exc
            raise

        return ConnectionsPage(
            people=response.get("connections", []),
            next_page_token=response.get("nextPageToken"),
            next_sync_token=response.get("nextSyncToken"),
            total_estimate=response.get("totalItems"),
        )


# ---- Write seam (feature 003) --------------------------------------------------------------
# The ONLY Google writes in the product. Faked in CI so delete/restore, idempotency, and
# partial-failure retry are tested without mutating real data (Principle IV).

# personFields written back when re-creating a contact on undo (mirror what we captured).
WRITE_PERSON_FIELDS = (
    "names,nicknames,emailAddresses,phoneNumbers,addresses,organizations,"
    "biographies,birthdays,urls"
)


class PeopleWriteClient(Protocol):
    def delete_contact(self, resource_name: str) -> None:
        """Delete one contact. Raise ContactNotFoundError if already absent (FR-024)."""
        ...

    def create_contact(self, payload: dict) -> str:
        """Re-create a contact from a captured Person payload; return its new resourceName."""
        ...

    # ---- Label / contact-group write (feature 004) -----------------------------------------
    # Reuses the SAME `…/auth/contacts` scope as delete (research D1 — no new OAuth scope).
    def ensure_label(self, name: str) -> str:
        """Ensure a contact group named `name` exists; return its resourceName (create-or-reuse)."""
        ...

    def add_label_members(self, group_resource_name: str, resource_names: list[str]) -> None:
        """Add contacts to the group. Raise ContactNotFoundError if a contact is absent (FR-012a)."""
        ...

    def remove_label_members(self, group_resource_name: str, resource_names: list[str]) -> None:
        """Remove contacts from the group (undo). Raise ContactNotFoundError if absent."""
        ...


class GooglePeopleWriteClient:
    """Google-backed write client. Requires the `…/auth/contacts` scope (research D8/D9)."""

    def __init__(self, credentials):
        self._credentials = credentials

    def _service(self):
        from googleapiclient.discovery import build

        return build("people", "v1", credentials=self._credentials, cache_discovery=False)

    def delete_contact(self, resource_name: str) -> None:  # pragma: no cover - integration env
        from googleapiclient.errors import HttpError

        try:
            self._service().people().deleteContact(resourceName=resource_name).execute()
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status == 404:
                raise ContactNotFoundError(resource_name) from exc
            if status == 429:
                retry_after = exc.resp.get("retry-after") if exc.resp else None
                raise RateLimitedError(float(retry_after) if retry_after else None) from exc
            if status in (401, 403):
                raise AuthError() from exc
            if status and 500 <= int(status) < 600:
                raise TransientError() from exc
            raise

    def create_contact(self, payload: dict) -> str:  # pragma: no cover - integration env
        from googleapiclient.errors import HttpError

        # Strip server-managed fields; keep the user-editable Person body.
        body = {k: v for k, v in payload.items() if k not in ("resourceName", "etag", "metadata")}
        try:
            created = (
                self._service()
                .people()
                .createContact(body=body, personFields=WRITE_PERSON_FIELDS)
                .execute()
            )
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status == 429:
                retry_after = exc.resp.get("retry-after") if exc.resp else None
                raise RateLimitedError(float(retry_after) if retry_after else None) from exc
            if status in (401, 403):
                raise AuthError() from exc
            if status and 500 <= int(status) < 600:
                raise TransientError() from exc
            raise
        return created["resourceName"]

    # ---- Label / contact-group write (feature 004) -----------------------------------------

    def ensure_label(self, name: str) -> str:  # pragma: no cover - integration env
        from googleapiclient.errors import HttpError

        service = self._service()
        try:
            existing = service.contactGroups().list(pageSize=1000).execute()
            for group in existing.get("contactGroups", []):
                if group.get("name") == name and group.get("groupType") == "USER_CONTACT_GROUP":
                    return group["resourceName"]
            created = (
                service.contactGroups()
                .create(body={"contactGroup": {"name": name}})
                .execute()
            )
        except HttpError as exc:
            raise self._map_error(exc) from exc
        return created["resourceName"]

    def add_label_members(
        self, group_resource_name: str, resource_names: list[str]
    ) -> None:  # pragma: no cover - integration env
        self._modify_members(group_resource_name, add=resource_names, remove=[])

    def remove_label_members(
        self, group_resource_name: str, resource_names: list[str]
    ) -> None:  # pragma: no cover - integration env
        self._modify_members(group_resource_name, add=[], remove=resource_names)

    def _modify_members(
        self, group_resource_name: str, *, add: list[str], remove: list[str]
    ) -> None:  # pragma: no cover - integration env
        from googleapiclient.errors import HttpError

        body: dict = {}
        if add:
            body["resourceNamesToAdd"] = add
        if remove:
            body["resourceNamesToRemove"] = remove
        try:
            result = (
                self._service()
                .contactGroups()
                .members()
                .modify(resourceName=group_resource_name, body=body)
                .execute()
            )
        except HttpError as exc:
            raise self._map_error(exc) from exc
        # members.modify reports absent contacts in-band rather than via 404.
        requested = set(add) | set(remove)
        not_found = set(result.get("notFoundResourceNames", []))
        if requested and requested <= not_found:
            raise ContactNotFoundError(next(iter(requested)))

    @staticmethod
    def _map_error(exc) -> Exception:  # pragma: no cover - integration env
        status = getattr(exc.resp, "status", None)
        if status == 404:
            return ContactNotFoundError()
        if status == 429:
            retry_after = exc.resp.get("retry-after") if exc.resp else None
            return RateLimitedError(float(retry_after) if retry_after else None)
        if status in (401, 403):
            return AuthError()
        if status and 500 <= int(status) < 600:
            return TransientError()
        return exc


class FakePeopleWriteClient:
    """In-memory write client for CI. Records deletes/creates, group create + membership."""

    def __init__(self, *, absent: set[str] | None = None):
        self.absent = set(absent or ())
        self.deleted: list[str] = []
        self.created: dict[str, dict] = {}
        self._seq = 0
        # Label / contact-group state (feature 004).
        self.groups: dict[str, str] = {}  # name -> group resourceName
        self.created_groups: list[str] = []  # records each CREATE (assert ensured-once)
        self.group_members: dict[str, set[str]] = {}  # group resourceName -> member resourceNames
        self._group_seq = 0

    def delete_contact(self, resource_name: str) -> None:
        if resource_name in self.absent:
            raise ContactNotFoundError(resource_name)
        self.deleted.append(resource_name)

    def create_contact(self, payload: dict) -> str:
        self._seq += 1
        rn = f"people/restored{self._seq}"
        self.created[rn] = payload
        return rn

    def ensure_label(self, name: str) -> str:
        if name not in self.groups:
            self._group_seq += 1
            rn = f"contactGroups/{name}-{self._group_seq}"
            self.groups[name] = rn
            self.group_members[rn] = set()
            self.created_groups.append(rn)
        return self.groups[name]

    def add_label_members(self, group_resource_name: str, resource_names: list[str]) -> None:
        members = self.group_members.setdefault(group_resource_name, set())
        for rn in resource_names:
            if rn in self.absent:
                raise ContactNotFoundError(rn)
            members.add(rn)

    def remove_label_members(self, group_resource_name: str, resource_names: list[str]) -> None:
        members = self.group_members.setdefault(group_resource_name, set())
        for rn in resource_names:
            if rn in self.absent:
                raise ContactNotFoundError(rn)
            members.discard(rn)


def get_write_client(kind: str, *, credentials=None) -> PeopleWriteClient:
    """Factory: 'google' → real client (needs credentials); anything else → in-memory fake."""
    if kind == "google":
        return GooglePeopleWriteClient(credentials)
    return FakePeopleWriteClient()
