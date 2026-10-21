# Test results in a bucket

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

How a test run ends up on the **Test results** page of the Quality Console, all on the laptop: the tests write JUnit and HTML reports, an uploader puts them in a Cloud Storage bucket the way a CI test runner does, an indexer summarises the bucket, and the console reads that summary. The bucket is a local Cloud Storage emulator, so nothing needs a cloud account.

> **TL;DR**
>
> - `mise run up` starts the bucket (`gcs`, port 4443), `mise run results:seed` fills it with four weeks of made-up CI history, <http://localhost:8081/test-results> shows it.
> - Every `mise run test:unit` / `mise run test:integration` uploads its own run afterwards, like a CI job's upload step; **Refresh** on the page (or `mise run results:index`) makes it appear.
> - The indexing runs on demand here. In production a scheduler runs it every 30 minutes: that schedule is kept, ready, in `gitlab-ci/results_stage.yml`.

## The chain, end to end

1. **Tests write reports.** The mise test tasks run pytest with `--junitxml` and `--html` into `reports/unit/`, `reports/integration/` or `reports/acceptance/`. Each test declares who it belongs to with `metadata_test(...)` (system, product, business capability, component, group, testing scope, tags, every value a catalog entry, see [The software catalog](catalog-and-metadata.md)); `tests/conftest.py` writes it as JUnit `<properties>` of every test. A Gherkin run from the console goes the same way, through the runner.
2. **An uploader sends them to the bucket.** `scripts/test_and_upload.sh` runs after the tests whatever their outcome, sets the job context a CI job would have (`CI_JOB_NAME`, `CI_PIPELINE_ID`, `CI_COMMIT_SHORT_SHA`, `CI_JOB_STATUS`...), and calls `scripts/upload_results.py`. A bucket that is not running skips the upload with the reason; the tests' verdict stands. In CI, the same script runs in the jobs' `after_script`.
3. **The bucket keeps one folder per run.** Under `test-runner/reports/<env>/<artifact type>/<YYYYMMDD_HHMMSS>_<pipeline id>/<job name>/`: `metadata.json` first, then `junit.xml`, `report.html`, or a k6 `summary.json` for a load test.
4. **An indexer summarises the bucket.** `scripts/build_results_index.py` lists every `metadata.json`, groups runs by month, writes one shard per month under `test-runner/run-index/`, then the header `index.json` last. This is the scheduled job.
5. **The console reads the index.** The list, counters, filters and trends never crawl the bucket: they read the index. A run page reads that run's folder. A report file is served from the bucket, an HTML report sandboxed so it cannot run scripts in the console.

## What the bucket holds

```text
test-results/
  test-runner/
    reports/
      local/backend/20261008_154917_local/unit-tests/
        metadata.json
        junit.xml
        report.html
      sta/performance/20261007_060900_184084/perf-customer-welcome-baseline/
        metadata.json
        summary.json
        report.html
    run-index/
      index.json        generated_at, run_count, the month shards
      2026-10.json      the runs of October, newest first
      2026-09.json
```

Three rules of that layout are contracts between the writer and the readers, and the code says so where it applies them:

- **The run folder name is UTC and zero-padded** (`run_folder_name` in `src/test_results/layout.py`): its text order is its time order, which lets a real indexer bound its listing to recent months.
- **`metadata.json` also travels as object metadata** (`run-index` key, when under 6 KiB): the indexer reads it straight from the listing and skips a download per run.
- **The index lives beside the reports, never inside**: a crawl of `reports/**/metadata.json` cannot pick it up.

## A job fails as a whole, its tests say how much

A job of ten tests where eight pass and two do not is a failed job: CI says `failed`, whatever the two did. Its JUnit report tells them apart:

- **failed** (`<failure>`): the test ran and an assertion did not hold, the product misbehaved;
- **error** (`<error>`): the test never reached an assertion, its setup broke (a fixture, a page that never loaded, a service down).

`metadata.json` keeps the counts of its reports (`test_counts`: `total`, `passed`, `failed`, `errors`, `skipped`), so the index carries them without opening any report: each run card of the list says `8/10 passed · 2 errors`, and the catalog map says, for each item, how many tests of its last runs passed and which jobs failed with what. The seeded `e2e-checkout-chromium` job shows it: ten browser tests of the checkout, two in error for the last three days (a page that never draws its workflow steps), so the checkout product, the orders system and the storefront web component turn red on the map, `8/10 passed, 2 errors`.

## Mocked or real

The local stack keeps everything real that can run on a laptop, and makes up only what cannot exist here.

- **Real**: the bucket server ([`fake-gcs-server`](https://github.com/fsouza/fake-gcs-server), which implements the Cloud Storage API), the Google client library that talks to it, the uploads, the listings with object metadata, the index files, the reports of the runs you start yourself.
- **Made up**: the history `mise run results:seed` writes (`scripts/seed_results.py`): API, browser and load test jobs, on `int` and `sta`, over four weeks, with flaky tests that fail now and then, a browser job whose last three days have two tests in error, and load tests that sometimes break a threshold. It goes through the same `upload_run` as a real run, so it has exactly the shape a real one has. It is deterministic: the same seed writes the same history.
- **Simplified**: the indexer crawls the whole bucket on each run. A production one bounds its listing to recent months and reuses the previous index; a demo bucket is small enough not to need it.

The bucket survives `mise run down` (the `results-bucket` Docker volume), like a real bucket outlives the services that read it. `docker volume rm quality-console_results-bucket` empties it.

## Schedules, kept for later

Two schedules make this chain run by itself in a real project. Neither runs here, both are written down so they can be switched on.

**The index rebuild, every 30 minutes.** `gitlab-ci/results_stage.yml` holds a `results-index` job that only runs in a scheduled pipeline whose `SCHEDULE_TASK` variable is `results-index`; every other job stays out of that pipeline (`gitlab-ci/rules.yml`). To switch it on in GitLab:

1. **Build > Pipeline schedules > New schedule**.
2. Interval pattern `*/30 * * * *`, target branch `main`.
3. Variable `SCHEDULE_TASK` = `results-index`.
4. Variables `RESULTS_BUCKET` (the bucket name) and the bucket credentials (see below), as CI/CD variables of the project.

**The tests themselves, nightly.** A scheduled pipeline without `SCHEDULE_TASK` runs the whole test suite like any pipeline on `main`, and its jobs upload their results. To switch it on: a second schedule, interval `0 5 * * *`, no variable.

## Using a real bucket instead

The code does not change, only its settings: unset `STORAGE_EMULATOR_HOST`, set `RESULTS_BUCKET` to the real bucket, and give the Google client credentials (`GOOGLE_APPLICATION_CREDENTIALS` pointing at a service account key, or `gcloud auth application-default login` on a laptop).

A personal bucket costs nothing at this size: Google Cloud's free tier includes a few GB of standard storage in some US regions, which a demo's reports never come close to. It needs a Google account with billing enabled, even when nothing is billed.

## Where the code is

- `src/test_results/`: the shared contract. `layout.py` (paths and names), `models.py` (what the files hold), `junit.py` and `k6.py` (report parsing), `uploader.py` (the CI side), `index.py` (the scheduled side), `reader.py` (the console side), `storage.py` (emulator or real bucket).
- `scripts/`: `test_and_upload.sh` and `upload_results.py` (after the tests), `build_results_index.py` (the scheduled job), `seed_results.py` (the made-up history).
- `src/quality_console/results.py` and `src/quality_console/templates/results.html` (runs and the selected run, Details and Trends tabs), `trends.html` (every job at a glance): the console pages. `src/test_results/trends.py` computes pass rates and streaks, `src/quality_console/charts.py` draws the dated chart as inline SVG (no JavaScript, works offline).
- Tests: `tests/unit/test_results_rules.py` (names, paths, parsing), `tests/unit/test_results_trends.py` (pass rates, streaks, chart), `tests/integration/test_results_bucket_gcs.py` (upload, index, read against a real emulator), `tests/integration/test_console_results_gcs.py` (the pages).

---

See also: [Quality Console demo](demos/quality-console.md), [README.md](../README.md).
