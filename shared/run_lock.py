"""
Cross-process run lock — one PathFinder agent at a time (BUG-73).

openpyxl's wb.save() truncates and rewrites pathfinder_dashboard.xlsx in
place, so a second agent process reading the file mid-save dies with an
EOFError deep in zipfile, and two concurrent writers silently lose one
writer's rows (last save wins). Observed 2026-07-16: a manual job_agent run
collided with the still-running scheduled pipeline.

Every agent entry point takes this exclusive flock for the whole run. The
kernel releases a flock on process exit, so a crashed agent can never leave
a stale lock behind — the holder text inside the file is informational only.
"""
import fcntl
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK_PATH    = os.path.join(PROJECT_ROOT, "logs", "pathfinder.lock")


class AgentAlreadyRunning(RuntimeError):
    """Another PathFinder agent process holds the run lock."""


def acquire_run_lock(agent_name: str, lock_path: str = LOCK_PATH):
    """Take the exclusive cross-process run lock; returns the open lockfile.

    Keep the returned file object referenced for the whole run — closing it
    (or process exit, clean or not) releases the lock.

    Fail-fast by default: raises AgentAlreadyRunning naming the holder so a
    manual run aborts before touching the workbook. PATHFINDER_LOCK_WAIT=1
    blocks until the lock frees instead — the scheduled pipeline sets it so
    its phases queue behind a straggler rather than abort the daily run.
    """
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    f = open(lock_path, "a+")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.seek(0)
        holder = f.read().strip() or "holder unknown"
        if os.environ.get("PATHFINDER_LOCK_WAIT") == "1":
            print(f"⏳ Run lock held ({holder}) — waiting for it to finish...")
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        else:
            f.close()
            raise AgentAlreadyRunning(
                f"Another PathFinder agent is already running ({holder}).\n"
                f"The scheduled pipeline may still be in flight — check "
                f"logs/pipeline-*.log, or ps aux | grep agents/.\n"
                f"Rerun after it finishes, or queue behind it with "
                f"PATHFINDER_LOCK_WAIT=1."
            ) from None
    f.seek(0)
    f.truncate()
    f.write(f"agent={agent_name} pid={os.getpid()} "
            f"started={time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.flush()
    return f
