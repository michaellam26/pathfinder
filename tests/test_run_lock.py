"""
Tests for shared/run_lock.py (BUG-73) — cross-process agent run lock.

flock contention is per open-file-description, so a second open()+flock in
the same process conflicts exactly like a second process would — no
subprocess machinery needed to exercise the collision paths.
"""
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.run_lock import acquire_run_lock, AgentAlreadyRunning


class TestRunLock(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pf-runlock-test-")
        self.lock_path = os.path.join(self.dir, "logs", "pathfinder.lock")
        self._saved_wait = os.environ.pop("PATHFINDER_LOCK_WAIT", None)

    def tearDown(self):
        if self._saved_wait is not None:
            os.environ["PATHFINDER_LOCK_WAIT"] = self._saved_wait
        else:
            os.environ.pop("PATHFINDER_LOCK_WAIT", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_acquire_creates_dir_and_records_holder(self):
        f = acquire_run_lock("job_agent", self.lock_path)
        try:
            with open(self.lock_path) as fh:
                content = fh.read()
            self.assertIn("agent=job_agent", content)
            self.assertIn(f"pid={os.getpid()}", content)
        finally:
            f.close()

    def test_second_acquire_fails_fast_naming_holder(self):
        f = acquire_run_lock("job_agent", self.lock_path)
        try:
            with self.assertRaises(AgentAlreadyRunning) as cm:
                acquire_run_lock("match_agent", self.lock_path)
            self.assertIn("agent=job_agent", str(cm.exception))
        finally:
            f.close()

    def test_close_releases_lock_for_next_agent(self):
        acquire_run_lock("job_agent", self.lock_path).close()
        f2 = acquire_run_lock("match_agent", self.lock_path)
        try:
            with open(self.lock_path) as fh:
                self.assertIn("agent=match_agent", fh.read())
        finally:
            f2.close()

    def test_wait_mode_blocks_until_holder_releases(self):
        os.environ["PATHFINDER_LOCK_WAIT"] = "1"
        holder = acquire_run_lock("company_agent", self.lock_path)
        releaser = threading.Timer(0.3, holder.close)
        releaser.start()
        start = time.monotonic()
        f2 = acquire_run_lock("job_agent", self.lock_path)
        elapsed = time.monotonic() - start
        try:
            releaser.join()
            self.assertGreaterEqual(elapsed, 0.25)
        finally:
            f2.close()

    def test_holder_text_survives_for_diagnostics_after_crash(self):
        """A dead holder's flock is gone but its text remains — a fresh
        acquire must succeed and overwrite the stale text."""
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        with open(self.lock_path, "w") as fh:
            fh.write("agent=job_agent pid=99999 started=2026-07-16 04:00:00\n")
        f = acquire_run_lock("match_agent", self.lock_path)
        try:
            with open(self.lock_path) as fh:
                content = fh.read()
            self.assertIn("agent=match_agent", content)
            self.assertNotIn("pid=99999", content)
        finally:
            f.close()


if __name__ == "__main__":
    unittest.main()
