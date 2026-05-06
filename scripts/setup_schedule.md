# Daily Pipeline Schedule — Setup

Schedules the PathFinder pipeline to run automatically at 04:00 every day so
results are ready when you wake up. Built on macOS `launchd` + `pmset`.

## Prerequisites

1. Mac must be **plugged into power** during the scheduled window — the
   default battery-saver policy will block scheduled wake otherwise.
2. Mac can be asleep but **must not be powered off** (lid closed is fine
   when externally powered).
3. `Notification Center` permissions: System Settings → Notifications →
   Script Editor (or `osascript`) → allow notifications. First run will
   prompt; if you miss it, run the wrapper manually once to retrigger.

## Install

```bash
# 1. Copy the plist into LaunchAgents
cp scripts/com.pathfinder.daily.plist ~/Library/LaunchAgents/

# 2. Load it (this registers the schedule with launchd)
launchctl load ~/Library/LaunchAgents/com.pathfinder.daily.plist

# 3. Verify it's registered
launchctl list | grep pathfinder
# expected output: -<PID-or-dash> 0 com.pathfinder.daily

# 4. Schedule the system to wake (or power on) at 03:55 each day so the
#    4:00 fire actually triggers. Requires sudo.
sudo pmset repeat wakeorpoweron MTWRFSU 03:55:00

# 5. Confirm the wake schedule
pmset -g sched
```

## Test Without Waiting

Manually fire the job to confirm the wrapper, logs, and notifications work:

```bash
launchctl start com.pathfinder.daily
# then watch the latest run log
ls -t logs/pipeline-*.log | head -1 | xargs tail -f
```

You should see a "PathFinder — Pipeline complete" notification when it
finishes (or "FAILED at <step>" if a step exits nonzero).

## Disable Temporarily

```bash
launchctl unload ~/Library/LaunchAgents/com.pathfinder.daily.plist
# re-enable with `launchctl load`
```

## Remove Wake Schedule

```bash
sudo pmset repeat cancel
```

## Failure Modes & Where to Look

- **No log written, no notification:** Mac was asleep without external
  power, or `pmset repeat` wasn't installed. Check `pmset -g sched`.
- **Notification fired but no log:** osascript ran but `python` couldn't
  start. Check `logs/launchd.err.log`.
- **Step failed:** notification subtitle names the step (e.g. "FAILED at
  2/4 Job Agent"); per-run log in `logs/pipeline-YYYYMMDD-HHMMSS.log` has
  the traceback.
- **API key 429 / quota exhausted overnight:** transient; next-day run
  retries with fresh quota window.
