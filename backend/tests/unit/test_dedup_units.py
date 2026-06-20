"""Unit tests: flatten projection, fake-engine clustering/scores, survivor field union (T041)."""
from __future__ import annotations

import uuid

from src.integrations.dedup_engine import FakeDedupEngine
from src.services import cluster_service, contact_flatten


def test_flatten_projects_match_columns():
    payload = {
        "names": [{"displayName": "John Smith", "givenName": "John", "familyName": "Smith",
                   "metadata": {"primary": True}}],
        "emailAddresses": [{"value": "john@x.com", "metadata": {"primary": True}}],
        "phoneNumbers": [{"value": "+1 202 555 0100", "metadata": {"primary": True}}],
        "organizations": [{"name": "Acme"}],
    }
    row = contact_flatten.flatten_contact(uuid.uuid4(), payload)
    assert row["first_name"] == "John"
    assert row["last_name"] == "Smith"
    assert row["email"] == "john@x.com"
    assert row["phone"] == "+1 202 555 0100"
    assert row["organization"] == "Acme"


def test_fake_engine_clusters_by_phone_with_high_score():
    rows = [
        {"wcc_id": "a", "phone": "+1-202-555-0100", "email": "a@x.com"},
        {"wcc_id": "b", "phone": "(202) 555 0100", "email": "b@y.com"},
        {"wcc_id": "c", "phone": "+1-303-555-0000", "email": "c@z.com"},
    ]
    out = {m.wcc_id: m for m in FakeDedupEngine().run("r", rows)}
    assert out["a"].z_cluster == out["b"].z_cluster  # same phone → same cluster
    assert out["a"].z_cluster != out["c"].z_cluster
    assert out["a"].z_max_score > out["c"].z_max_score  # phone match scores higher


def test_survivor_union_merges_emails_and_flags_conflict():
    class C:
        def __init__(self, payload):
            self.payload = payload
            self.id = uuid.uuid4()

    survivor = C({
        "names": [{"displayName": "John Smith"}],
        "emailAddresses": [{"value": "john@x.com"}],
    })
    other = C({
        "names": [{"displayName": "Jon Smith"}],
        "emailAddresses": [{"value": "jon@y.com"}],
    })
    merged, conflicts = cluster_service._build_merged_payload(survivor, [other])
    values = {e["value"] for e in merged["emailAddresses"]}
    assert values == {"john@x.com", "jon@y.com"}
    # Names differ → a surfaced conflict defaulting to the survivor's name.
    name_conflict = next(c for c in conflicts if c["field"] == "names")
    assert name_conflict["chosen"] == "John Smith"
