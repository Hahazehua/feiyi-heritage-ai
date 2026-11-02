"""Submit reproducible failure/retry, rerun and native backfill exercises."""
import json
import argparse
from datetime import datetime
from pathlib import Path
import subprocess

CLI = Path(__file__).resolve().parent / "cli.sh"


def cli(*args):
    subprocess.run(["bash", str(CLI), *args], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="exercise_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()
    conf = {"business_date": "2026-09-06", "as_of": "2026-09-11T00:00:00Z", "refresh_days": 30, "fail_once": True}
    cli("dags", "trigger", "haha_daily_publish", "--run-id", args.prefix + "_retry", "--conf", json.dumps(conf))
    conf["fail_once"] = False
    cli("dags", "trigger", "haha_daily_publish", "--run-id", args.prefix + "_idempotent", "--conf", json.dumps(conf))
    print("Retry/rerun submitted. Native historical backfill is a separate backfill_step07.py exercise.")
