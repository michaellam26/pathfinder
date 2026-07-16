#!/bin/bash
# PathFinder daily pipeline runner — invoked by launchd at ~4am.
#
# Stops at the first failed step (set -e) so we never feed half-baked data
# to a downstream agent. macOS notifications surface success/failure since
# the user is asleep when this runs and only sees results in the morning.

set -e
set -u
set -o pipefail

# PATHFINDER_PROJECT_DIR override exists for the test harness only.
PROJECT_DIR="${PATHFINDER_PROJECT_DIR:-/Users/michaelnomad/pathfinder}"
cd "$PROJECT_DIR"

# BUG-73: agents take an exclusive run lock (shared/run_lock.py). The pipeline
# queues behind a lock holder instead of failing the daily run; manual runs
# (no env var) fail fast with a message naming the holder.
export PATHFINDER_LOCK_WAIT=1

mkdir -p logs
LOG_FILE="logs/pipeline-$(date +%Y%m%d-%H%M%S).log"

notify() {
    # $1=subtitle (status), $2=message
    osascript -e "display notification \"$2\" with title \"PathFinder\" subtitle \"$1\"" 2>/dev/null || true
}

run_step() {
    local step_name="$1"
    local script_path="$2"
    {
        echo ""
        echo "=== [$step_name] start: $(date '+%Y-%m-%d %H:%M:%S') ==="
    } >> "$LOG_FILE"
    if ! python "$script_path" >> "$LOG_FILE" 2>&1; then
        echo "=== [$step_name] FAILED: $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG_FILE"
        # PRJ-004 REQ-004-25: persistent failure marker — a missed macOS
        # notification must not be the only trace of a failed daily run.
        printf '%s\nstep=%s\nlog=%s\n' "$(date '+%F %T')" "$step_name" "$LOG_FILE" \
            > "$PROJECT_DIR/logs/LAST_RUN_FAILED"
        notify "FAILED at $step_name" "Check $LOG_FILE"
        exit 1
    fi
    echo "=== [$step_name] ok:    $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG_FILE"
}

# shellcheck disable=SC1091
source venv/bin/activate

echo "PathFinder pipeline run started: $(date)" > "$LOG_FILE"

run_step "1/4 Company Agent"     "agents/company_agent.py"
run_step "2/4 Job Agent"         "agents/job_agent.py"
run_step "3/4 Match Agent"       "agents/match_agent.py"
run_step "4/4 Resume Optimizer"  "agents/resume_optimizer.py"

echo "" >> "$LOG_FILE"
echo "Pipeline complete: $(date)" >> "$LOG_FILE"
# PRJ-004 REQ-004-25: success clears the failure marker and stamps LAST_RUN_OK.
# A stale LAST_RUN_OK (>36h) is itself the "runs stopped firing" signal that a
# failure marker alone cannot provide (launchd-never-ran failure mode).
rm -f "$PROJECT_DIR/logs/LAST_RUN_FAILED"
date '+%F %T' > "$PROJECT_DIR/logs/LAST_RUN_OK"
notify "Pipeline complete" "$(basename "$LOG_FILE")"
