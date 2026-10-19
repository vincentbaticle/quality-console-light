#!/usr/bin/env bash
set -uo pipefail

script=$1
job_name=$2
reports_dir=reports/perf

rm -rf "$reports_dir"
mkdir -p "$reports_dir"
k6 run --quiet \
  -e BASE_URL="${PERF_BASE_URL:-http://localhost:8080}" \
  -e REPORTS_DIR="$reports_dir" \
  "perf/$script"
status=$?

CI_JOB_NAME="$job_name" \
CI_PIPELINE_ID=local \
CI_JOB_ID="" \
CI_COMMIT_SHORT_SHA="$(git rev-parse --short HEAD)" \
CI_JOB_STATUS="$([ "$status" -eq 0 ] && echo success || echo failed)" \
STORAGE_EMULATOR_HOST="$RESULTS_EMULATOR_HOST" \
pdm run python -m scripts.upload_results performance "$reports_dir"

exit "$status"
