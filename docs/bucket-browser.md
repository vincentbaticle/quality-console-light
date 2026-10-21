# Bucket browser: the files of the Cloud Storage buckets

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

**Bucket browser** lists the buckets the console's storage client sees, then their folders and files, opened in place or downloaded.

> **TL;DR**
>
> - Locally the buckets of the storage emulator (`mise run up`); against a real project, those Application Default Credentials can list.
> - `test-results` is `live`: every test run writes a folder. `finance-exports` and `catalog-feeds` are `static`: loaded once from `buckets/` at start-up.
> - A file opens in a new tab, sandboxed: an HTML report cannot run its scripts. **download** saves it.

## What to look at

- `test-results/test-runner/reports/<env>/<type>/<run>/<job>/`: one run, its JUnit report, its HTML report, its coverage. The layout is the contract of `src/test_results/layout.py`, see [Test results in a bucket](test-results.md).
- The team buckets: the files the Gherkin feature `bucket-checks/file-contracts.feature` checks: names, not empty, format, freshness, and a manifest listing exactly the files.

## Where it lives

`src/quality_console/tools/bucket.py`; the emulator is the `gcs` service of `docker-compose.yml`, fed from `buckets/`.
