from __future__ import annotations

PROTOCOL_VERSION = "v1"

# Drift SLO thresholds in milliseconds.
DRIFT_WARN_MS = 2.0
DRIFT_CRITICAL_MS = 8.0
DRIFT_HISTORY_MAXLEN = 120
DRIFT_SUSTAINED_WARN_SAMPLES = 3
DRIFT_SUSTAINED_CRITICAL_SAMPLES = 2

# Minimum scheduling lead time for PLAY_AT.
MIN_PLAY_AT_LEAD_MS = 1500
