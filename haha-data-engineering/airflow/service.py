"""在 WSL 中后台启动/停止本练习的 Airflow；启动日志留在用户 Linux 目录。"""
import argparse
import os
from pathlib import Path
import signal
import subprocess

root = Path.home() / ".local/share/haha-airflow"
pidfile = root / "service.pid"
start = "/mnt/f/HC/hackathon/haha-data-engineering/airflow/start.sh"
parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["start", "stop", "status"])
args = parser.parse_args()
pid = int(pidfile.read_text()) if pidfile.exists() else None
running = bool(pid and Path(f"/proc/{pid}/cmdline").exists()
               and b"airflow" in Path(f"/proc/{pid}/cmdline").read_bytes())
if args.action == "start" and not running:
    root.mkdir(parents=True, exist_ok=True)
    with (root / "standalone.log").open("ab") as log:
        child = subprocess.Popen(["bash", start], stdout=log, stderr=log, start_new_session=True)
    pidfile.write_text(str(child.pid))
    print(f"Airflow starting, pid={child.pid}, log={root / 'standalone.log'}")
elif args.action == "stop" and running:
    os.killpg(pid, signal.SIGTERM)
    pidfile.unlink()
    print("Airflow stop requested")
else:
    print("running" if running else "stopped")
