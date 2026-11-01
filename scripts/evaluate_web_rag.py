"""Small, deterministic English retrieval benchmark; no model API spend."""

import json
import os
import statistics
import tempfile
from pathlib import Path

from heritagelink.web.schemas import Brief
from heritagelink.web.service import HeritageService

CASES = [
    ("carved lacquer box", "lacquer"),
    ("blue white porcelain", "porcelain"),
    ("silk embroidery", "silk"),
    ("jade carving", "jade"),
    ("bamboo brush holder", "bamboo"),
    ("celadon tea bowl", "celadon"),
    ("calligraphy happiness", "calligraphy"),
    ("woodblock print", "woodblock"),
    ("porcelain teapot", "porcelain"),
    ("incense lacquer", "lacquer"),
    ("zxqvnonexistent", None),
    ("cloisonne enamel", None),
]


def main():
    os.environ["LLM_ENABLED"] = "false"
    os.environ["VECTOR_BACKEND"] = "sqlite"
    with tempfile.TemporaryDirectory() as directory:
        os.environ["VECTOR_SQLITE_PATH"] = str(Path(directory) / "vectors.db")
        service = HeritageService(Path(__file__).resolve().parents[1])
        rows = []
        for query, expected in CASES:
            result = service.advise(Brief(query=query))
            sources = result["sources"]
            passed = (
                any(expected in source["passage"].lower() for source in sources[:3])
                if expected
                else not sources
            )
            rows.append(
                {
                    "query": query,
                    "expected_term": expected,
                    "passed": passed,
                    "source_ids": [s["id"] for s in sources],
                    "retrieval_ms": result["trace"]["retrieval_ms"],
                }
            )
        report = {
            "benchmark": "English lexical retrieval smoke set v1",
            "limitations": "Hand-authored in-domain cases; not a general quality estimate. "
            "Term presence does not measure factual entailment or user value.",
            "cases": rows,
            "passed": sum(row["passed"] for row in rows),
            "total": len(rows),
            "median_retrieval_ms": statistics.median(r["retrieval_ms"] for r in rows),
        }
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
