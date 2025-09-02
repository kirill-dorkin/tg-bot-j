#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: pretty.sh <title> <command...>" >&2
  exit 2
fi

TITLE="$1"; shift
CMD="$*"

LOGFILE="${LOGFILE:-$(mktemp -t make_dev_XXXX.log)}"

(
  bash -lc "$CMD"
) >"$LOGFILE" 2>&1 &
pid=$!

spinner='-\\|/'
i=0
printf "⏳ %s " "$TITLE"
while kill -0 "$pid" >/dev/null 2>&1; do
  i=$(((i+1) % 4))
  printf "\r⏳ %s %s" "$TITLE" "${spinner:$i:1}"
  sleep 0.2
done

if wait "$pid"; then
  printf "\r✅ %s\n" "$TITLE"
  rm -f "$LOGFILE" || true
else
  status=$?
  printf "\r❌ %s\n" "$TITLE"
  echo "--- Last 80 lines of log ---"
  tail -n 80 "$LOGFILE" || true
  echo "Full log: $LOGFILE"
  exit "$status"
fi

