"""Contract: the contact-group write seam (feature 004) — ensure-once, membership, absent→error."""
from __future__ import annotations

import pytest

from src.integrations.people_client import ContactNotFoundError, FakePeopleWriteClient


def test_ensure_label_creates_once_then_reuses():
    client = FakePeopleWriteClient()
    first = client.ensure_label("Process")
    second = client.ensure_label("Process")
    assert first == second
    assert len(client.created_groups) == 1  # created exactly once, reused thereafter


def test_add_and_remove_members_track_membership():
    client = FakePeopleWriteClient()
    group = client.ensure_label("Process")
    client.add_label_members(group, ["people/c1", "people/c2"])
    assert client.group_members[group] == {"people/c1", "people/c2"}

    client.remove_label_members(group, ["people/c1"])
    assert client.group_members[group] == {"people/c2"}


def test_absent_member_raises_contact_not_found():
    client = FakePeopleWriteClient(absent={"people/gone"})
    group = client.ensure_label("Process")
    with pytest.raises(ContactNotFoundError):
        client.add_label_members(group, ["people/gone"])
