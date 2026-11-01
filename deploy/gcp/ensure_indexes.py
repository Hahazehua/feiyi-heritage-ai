"""Create only missing catalog vector indexes and wait until both are READY."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time


def index_fields(category: bool) -> list[dict]:
    fields = [{"field-path": "corpus_id", "order": "ascending"}]
    if category:
        fields.append({"field-path": "category", "order": "ascending"})
    fields.append({"field-path": "embedding", "vector-config": {"dimension": 256, "flat": {}}})
    return fields


def matches(index: dict, category: bool, collection: str) -> bool:
    if f"/collectionGroups/{collection}/indexes/" not in index.get("name", ""):
        return False
    if index.get("queryScope") != "COLLECTION":
        return False
    fields = [field for field in index.get("fields", []) if field.get("fieldPath") != "__name__"]
    expected_names = (
        ["corpus_id", "category", "embedding"] if category else ["corpus_id", "embedding"]
    )
    if [field.get("fieldPath") for field in fields] != expected_names:
        return False
    return all(field.get("order") == "ASCENDING" for field in fields[:-1]) and fields[-1].get(
        "vectorConfig"
    ) == {"dimension": 256, "flat": {}}


def ensure_indexes(project: str, collection: str, timeout: int = 900) -> None:
    common = [f"--project={project}", "--database=(default)", "--format=json", "--quiet"]

    def list_indexes() -> list[dict]:
        result = subprocess.run(
            ["gcloud", "firestore", "indexes", "composite", "list", *common],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            print(result.stderr, file=sys.stderr, end="")
            result.check_returncode()
        return json.loads(result.stdout)

    existing = list_indexes()
    for category in (False, True):
        if not any(matches(index, category, collection) for index in existing):
            subprocess.run(
                [
                    "gcloud",
                    "firestore",
                    "indexes",
                    "composite",
                    "create",
                    *common,
                    f"--collection-group={collection}",
                    "--query-scope=collection",
                    "--async",
                    f"--field-config={json.dumps(index_fields(category))}",
                ],
                check=True,
            )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        indexes = list_indexes()
        needed = [
            next((index for index in indexes if matches(index, category, collection)), {})
            for category in (False, True)
        ]
        if all(index.get("state") == "READY" for index in needed):
            print("Both catalog vector indexes are READY.", flush=True)
            return
        if any(index.get("state") == "NEEDS_REPAIR" for index in needed):
            raise RuntimeError(
                "A matching index needs repair; inspect Firestore Indexes in Console"
            )
        print("Waiting for Firestore vector indexes...", flush=True)
        time.sleep(15)
    raise TimeoutError(
        "Indexes are still building. Re-run the deployment script after they are READY."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--collection", default="heritage_catalog_vectors")
    args = parser.parse_args()
    ensure_indexes(args.project_id, args.collection)


if __name__ == "__main__":
    main()
