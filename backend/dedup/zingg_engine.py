"""Real Zingg/Spark dedup engine (research D1/D2/D3/D5).

Runs ONLY inside the `dedup` container. Implements the `DedupEngine` seam: takes flattened
contact rows, runs Zingg's `match` phase with the bundled pre-trained model (no labeling at
runtime), and yields `MatchRow`s (z_cluster, z_minScore, z_maxScore).

This module is marked no-cover: it requires Spark + the JVM + the `zingg` package and is never
imported by the default CI lane.
"""
from __future__ import annotations

import csv
import os
import tempfile
from collections.abc import Iterable, Sequence

from src.core.config import get_settings
from src.integrations.dedup_engine import MatchRow

from dedup.field_defs import INPUT_SCHEMA, contact_field_definitions

_COLUMNS = (
    "wcc_id",
    "first_name",
    "last_name",
    "full_name",
    "email",
    "phone",
    "organization",
)


class ZinggDedupEngine:  # pragma: no cover - container-only
    """Runs the Zingg `match` phase against a bundled model and returns cluster assignments."""

    def run(self, run_id: str, rows: Sequence[dict]) -> Iterable[MatchRow]:
        # ZinggWithSpark (not bare Zingg) sets up the SparkSession; the official zingg/zingg image
        # provides Spark + the Zingg jar on the classpath (see Dockerfile.dedup).
        from zingg.client import Arguments, ClientOptions, ZinggWithSpark

        settings = get_settings()
        workdir = tempfile.mkdtemp(prefix=f"zingg-{run_id}-")
        input_path = os.path.join(workdir, "input.csv")
        output_path = os.path.join(workdir, "output")
        self._write_input_csv(rows, input_path)

        args = Arguments()
        args.setFieldDefinition(contact_field_definitions())
        args.setModelId(settings.dedup_model_id)
        args.setZinggDir(settings.dedup_zingg_dir)
        args.setNumPartitions(settings.dedup_num_partitions)

        from zingg.pipes import CsvPipe

        input_pipe = CsvPipe("dedup_input", input_path, INPUT_SCHEMA)
        output_pipe = CsvPipe("dedup_output", output_path)
        args.setData(input_pipe)
        args.setOutput(output_pipe)

        options = ClientOptions([ClientOptions.PHASE, "match"])
        ZinggWithSpark(args, options).initAndExecute()

        return list(self._read_output(output_path))

    @staticmethod
    def _write_input_csv(rows: Sequence[dict], path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_COLUMNS)
            for r in rows:
                writer.writerow({c: (r.get(c) or "") for c in _COLUMNS})

    @staticmethod
    def _read_output(output_dir: str) -> Iterable[MatchRow]:
        # Zingg match output columns: z_minScore, z_maxScore, z_cluster, <original columns...>
        for name in sorted(os.listdir(output_dir)):
            if not name.endswith(".csv"):
                continue
            with open(os.path.join(output_dir, name), encoding="utf-8") as fh:
                for line in fh:
                    parts = line.rstrip("\n").split(",")
                    if len(parts) < 4:
                        continue
                    z_min, z_max, z_cluster, wcc_id = parts[0], parts[1], parts[2], parts[3]
                    try:
                        yield MatchRow(
                            wcc_id=wcc_id,
                            z_cluster=z_cluster,
                            z_min_score=float(z_min),
                            z_max_score=float(z_max),
                        )
                    except ValueError:
                        continue  # header / malformed line
