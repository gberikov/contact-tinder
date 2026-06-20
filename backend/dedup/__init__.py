"""Spark/Zingg deduplication engine — runs ONLY inside the `dedup` container.

Never imported by the backend/CI process (Constitution IV). The backend talks to this through the
`DedupEngine` seam in `src.integrations.dedup_engine`; `get_engine("zingg")` imports it lazily.
"""
