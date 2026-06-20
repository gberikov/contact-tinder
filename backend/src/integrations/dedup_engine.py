"""Deduplication engine seam (Constitution Principle IV — Zingg/Spark behind a seam).

The backend and CI depend only on the `DedupEngine` protocol and the `FakeDedupEngine`
(deterministic, Spark-free). The real `ZinggDedupEngine` lives in `backend/dedup/` and runs only
inside the `dedup` container; it is never imported by the default CI lane.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MatchRow:
    """One engine output row: a contact's cluster assignment + Zingg-style scores."""

    wcc_id: str
    z_cluster: str
    z_min_score: float
    z_max_score: float


class DedupEngine(Protocol):
    """Maps flattened contact rows to clustered match rows.

    `rows` are dicts produced by `contact_flatten.flatten_contact` (keys include `wcc_id`,
    `first_name`, `last_name`, `full_name`, `email`, `phone`, `organization`).
    """

    def run(self, run_id: str, rows: Sequence[dict]) -> Iterable[MatchRow]:  # pragma: no cover
        ...


_NON_DIGITS = re.compile(r"\D+")


def _norm_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = _NON_DIGITS.sub("", value)
    # Compare on the last 10 digits to tolerate country-code / formatting differences.
    return digits[-10:] if len(digits) >= 7 else None


def _email_localpart(value: str | None) -> str | None:
    if not value or "@" not in value:
        return None
    return value.strip().lower().split("@", 1)[0]


class FakeDedupEngine:
    """Deterministic rule-based matcher for tests/CI (no Spark/JVM).

    Two contacts cluster together when they share a normalised phone (last 10 digits) or an
    email local-part. Clustering is transitive (union-find), mirroring Zingg's `z_cluster`
    behaviour. Scores are synthetic but stable: phone matches score higher than email-only.
    """

    def run(self, run_id: str, rows: Sequence[dict]) -> list[MatchRow]:
        ids = [str(r["wcc_id"]) for r in rows]
        parent: dict[str, str] = {i: i for i in ids}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        by_phone: dict[str, str] = {}
        by_email: dict[str, str] = {}
        strong: set[str] = set()  # cluster roots that contain at least one phone match
        for r in rows:
            wid = str(r["wcc_id"])
            phone = _norm_phone(r.get("phone"))
            email = _email_localpart(r.get("email"))
            if phone:
                if phone in by_phone:
                    union(wid, by_phone[phone])
                    strong.add(find(wid))
                else:
                    by_phone[phone] = wid
            if email:
                if email in by_email:
                    union(wid, by_email[email])
                else:
                    by_email[email] = wid

        out: list[MatchRow] = []
        for wid in ids:
            root = find(wid)
            is_strong = root in strong or find(root) in strong
            score = 0.95 if is_strong else 0.78
            out.append(
                MatchRow(wcc_id=wid, z_cluster=root, z_min_score=score, z_max_score=score)
            )
        return out


def get_engine(name: str):
    """Engine factory. Defaults to the fake engine; `zingg` is resolved lazily so the heavy
    Spark/Zingg import never loads in the backend/CI process."""
    if name == "zingg":  # pragma: no cover - exercised only in the dedup container
        from dedup.zingg_engine import ZinggDedupEngine

        return ZinggDedupEngine()
    return FakeDedupEngine()
