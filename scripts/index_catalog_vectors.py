"""Index public catalogue references, or verify an existing index without writing."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from heritagelink.catalog import load_reference_catalog  # noqa: E402
from heritagelink.vector_search import (  # noqa: E402
    EMBEDDING_DIMENSION,
    EMBEDDING_VERSION,
    CatalogSearch,
    VectorSearchSettings,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("sqlite", "firestore"))
    parser.add_argument("--project-id", help="GCP project ID; credentials come from ADC")
    parser.add_argument("--verify", action="store_true", help="Read-only check; never imports data")
    args = parser.parse_args()
    if args.backend:
        os.environ["VECTOR_BACKEND"] = args.backend
    if args.project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = args.project_id
    try:
        settings = VectorSearchSettings.from_env()
        items = load_reference_catalog(
            ROOT / "data" / "catalog" / "heritage_products.csv", project_root=ROOT
        )
        service = CatalogSearch(items, settings, ROOT)
        if not args.verify:
            count = service.index()
            print(f"Indexed {count} public reference records ({settings.backend}).")
        count = service.verify()
        print(f"Verified {count} records. Corpus: {service.corpus_id}")
        print(f"Embedding: {EMBEDDING_VERSION}; dimensions: {EMBEDDING_DIMENSION}")
        print("Lexical feature similarity only; no learned semantic model or translation.")
        return 0
    except Exception as exc:
        # Do not print credentials, client request bodies or raw catalogue/query data.
        print(f"Vector index operation failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
