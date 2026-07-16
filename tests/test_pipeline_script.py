"""
PRJ-004 REQ-004-25 / T13 — run_pipeline_scheduled.sh failure surfacing.

Drives the REAL wrapper script in a sandboxed temp project dir (via the
PATHFINDER_PROJECT_DIR override): stub agents exit 0/1, a stub `osascript`
shadows the real one so no macOS notifications fire, and a stub venv
activate satisfies the `source`. Asserts the marker-file contract:
  - a failed step writes logs/LAST_RUN_FAILED (with the step name) and the
    script exits non-zero;
  - a clean run removes LAST_RUN_FAILED and stamps logs/LAST_RUN_OK.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "run_pipeline_scheduled.sh")


class TestPipelineScriptMarkers(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pf-script-test-")
        # Stub venv activation (the script sources it relative to PROJECT_DIR)
        os.makedirs(os.path.join(self.dir, "venv", "bin"))
        with open(os.path.join(self.dir, "venv", "bin", "activate"), "w") as f:
            f.write("# stub venv activate for script test\n")
        # Stub osascript so no real notification fires
        self.bindir = os.path.join(self.dir, "stub-bin")
        os.makedirs(self.bindir)
        osa = os.path.join(self.bindir, "osascript")
        with open(osa, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(osa, 0o755)
        os.makedirs(os.path.join(self.dir, "agents"))
        os.makedirs(os.path.join(self.dir, "logs"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write_agents(self, failing: str | None):
        """Create the four stub agent scripts; `failing` (basename) exits 1."""
        for name in ("company_agent.py", "job_agent.py",
                     "match_agent.py", "resume_optimizer.py"):
            path = os.path.join(self.dir, "agents", name)
            code = 1 if name == failing else 0
            with open(path, "w") as f:
                f.write(f"import sys\nsys.exit({code})\n")

    def _run(self):
        env = {**os.environ,
               "PATHFINDER_PROJECT_DIR": self.dir,
               "PATH": f"{self.bindir}:{os.environ['PATH']}"}
        return subprocess.run(["bash", SCRIPT], env=env,
                              capture_output=True, text=True, timeout=60)

    def test_failed_step_writes_marker_and_exits_nonzero(self):
        self._write_agents(failing="job_agent.py")
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        marker = os.path.join(self.dir, "logs", "LAST_RUN_FAILED")
        self.assertTrue(os.path.exists(marker), "LAST_RUN_FAILED must exist")
        content = open(marker).read()
        self.assertIn("Job Agent", content)   # step name recorded
        self.assertIn("log=", content)        # log path recorded
        # A failed run must NOT stamp LAST_RUN_OK
        self.assertFalse(os.path.exists(
            os.path.join(self.dir, "logs", "LAST_RUN_OK")))

    def test_clean_run_clears_marker_and_stamps_ok(self):
        # Seed a stale failure marker from a previous run
        with open(os.path.join(self.dir, "logs", "LAST_RUN_FAILED"), "w") as f:
            f.write("stale\n")
        self._write_agents(failing=None)
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(os.path.exists(
            os.path.join(self.dir, "logs", "LAST_RUN_FAILED")),
            "clean run must remove the failure marker")
        ok = os.path.join(self.dir, "logs", "LAST_RUN_OK")
        self.assertTrue(os.path.exists(ok), "clean run must stamp LAST_RUN_OK")
        self.assertRegex(open(ok).read().strip(),
                         r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_agents_run_with_lock_wait_mode(self):
        """BUG-73: the pipeline must export PATHFINDER_LOCK_WAIT=1 so its
        phases queue behind a run-lock holder instead of aborting the run."""
        for name in ("company_agent.py", "job_agent.py",
                     "match_agent.py", "resume_optimizer.py"):
            path = os.path.join(self.dir, "agents", name)
            with open(path, "w") as f:
                f.write(
                    "import os\n"
                    "with open(os.path.join('logs', 'lock_wait_seen'), 'a') as fh:\n"
                    "    fh.write(os.environ.get('PATHFINDER_LOCK_WAIT', '') + '\\n')\n"
                )
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        seen = open(os.path.join(self.dir, "logs", "lock_wait_seen")).read()
        self.assertEqual(seen.split(), ["1", "1", "1", "1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
