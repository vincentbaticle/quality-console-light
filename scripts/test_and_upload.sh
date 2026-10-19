#!/usr/bin/env bash
set -uo pipefail

job_name=$1
artifact_type=$2
reports_dir=$3
shift 3

rm -rf "$reports_dir"
pdm run pytest --junitxml="$reports_dir/junit.xml" --html="$reports_dir/report.html" --self-contained-html "$@"
status=$?

coverage="coverage.${job_name%-tests}.xml"
if [ -s "$coverage" ]; then cp "$coverage" "$reports_dir/coverage.xml"; fi

CI_JOB_NAME="$job_name" \
CI_PIPELINE_ID=local \
CI_JOB_ID="" \
CI_COMMIT_SHORT_SHA="$(git rev-parse --short HEAD)" \
CI_JOB_STATUS="$([ "$status" -eq 0 ] && echo success || echo failed)" \
STORAGE_EMULATOR_HOST="$RESULTS_EMULATOR_HOST" \
pdm run python -m scripts.upload_results "$artifact_type" "$reports_dir"

exit "$status"
