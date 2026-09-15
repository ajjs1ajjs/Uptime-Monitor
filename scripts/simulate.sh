#!/usr/bin/env bash
# Uptime-Monitor simulation: flood + chaos + failover without a datacenter.
# Usage: bash scripts/simulate.sh [--big]
#   default: 60 sites x 2 cycles (fast, <5s)
#   --big:   200 sites x 3 cycles (soak-ish, ~1-2 min)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[sim] 1/3 unit sims..."
go test ./internal/sim/ -v 2>&1 | tail -8

if [ "${1:-}" = "--big" ]; then
  SITES=200; CYCLES=3
else
  SITES=60; CYCLES=2
fi

echo "[sim] 2/3 CLI drills ($SITES sites x $CYCLES cycles)..."
go run ./cmd/uptime-monitor drill flood --sites "$SITES" --cycles "$CYCLES"
go run ./cmd/uptime-monitor drill chaos
go run ./cmd/uptime-monitor drill failover
echo "[sim] ALL PASS"
