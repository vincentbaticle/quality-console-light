# Gherkin scenarios, run from the Quality Console

The acceptance scenarios describe each product in its own words, in `features/<product>/*.feature`. They run with pytest-bdd against the stack `mise run up` started, from a terminal or with one click in the console, and every run is filed in the test results like a CI job.

> **TL;DR**
>
> - One folder per product of the catalog: `customer-welcome`, `checkout`, `account-access`, `partner-contracts`, `bucket-checks`, `quality-console`. The console titles and describes each section from the catalog.
> - A badge beside each feature says what drives it (`@tool-pytest`, `@tool-playwright`, `@tool-schemathesis`, `@tool-k6`). The `playwright` ones click the storefront page, written from recorded journeys: [Recorded scenarios](recorded-scenarios.md).
> - Every scenario says its goal: a `Goal:` line under the `Scenario:` line, shown in the console under the scenario's name. A unit test refuses a scenario without one.
> - The storefront products and their scenarios point to each other: **🛍️ Try it by hand** on a Gherkin section opens the product in Live experimentation, **🥒 The scenarios that prove it** under a product card opens its Gherkin section.
> - Steps live in `tests/acceptance/test_<product>.py` (and the shared ones in `tests/acceptance/conftest.py`), marker `acceptance`, metadata like any test.
> - Terminal: `mise run test:acceptance` (all), or `-- --only-feature=checkout/place-order.feature`, or add `--only-scenario="A closed customer cannot order"`.
> - Console: **Tools**, **Gherkin scenarios**, **Run feature** or **Run** on one scenario. The verdict shows on top, with the pytest output and a link to the run in Test results.
> - Stack not running: the scenarios skip and say how to start it.

## Why scenarios beside the integration tests

Integration tests answer "does this piece work with its real neighbour?", each in its own throwaway containers. Scenarios answer "does the product do what we promised its user?", on the assembled stack, in sentences a product owner can read and challenge. They are few, one behaviour each, and their steps hide every technical detail.

## How a click runs a scenario

1. The console (`src/quality_console/tools/gherkin.py`) lists the feature files it reads from the mounted `features/` folder.
2. **Run** posts the feature path and the scenario name to the Gherkin runner (`src/gherkin_runner/`, service `runner`), which checks the feature exists.
3. The runner starts `pytest tests/acceptance -m acceptance --only-feature=... --only-scenario=...`; `tests/acceptance/conftest.py` keeps only the matching scenarios.
4. The scenarios call the stack by its compose aliases (`http://front`, `http://mailpit:8025`, `http://console:8000`).
5. The runner reads the JUnit report for the verdict and uploads the run to the results bucket under `local/acceptance/`, job `acceptance-<product>`.

The runner sees `features/` and `tests/` mounted read-only: edit a scenario or a step and run it again, no rebuild.

## Scenario outlines: one check, many buckets

`bucket-checks/file-contracts.feature` is written once and runs once per row of its `Examples`: each team bucket brings its prefix, its name pattern, its format and its freshness. The console shows the rows under the scenario; one click runs every row. Patterns avoid backslashes (`[0-9]`, `[.]`): a Gherkin table reads a backslash as an escape.

The map of every journey and of the paths its scenarios walk: [Scenario design](scenario-design.md).

## The goal of a scenario

The name of a scenario says what happens; the `Goal:` line under it says why it matters, the risk it closes, in one or two sentences:

```gherkin
Scenario: A closed customer is refused
  Goal: a customer the company no longer serves gets a 404, before any call
  to the bank or any visit counted.
  When "dennis" asks for a greeting
  Then the storefront answers 404
```

It is a plain Gherkin description, which pytest-bdd ignores and the console shows. The goals are to the scenarios what **What this card teaches a tester** is to a storefront product: the reason before the steps. The two sides link to each other, so a tester can go from what they tried by hand to the scenario that proves it, and back.

## What drives a feature: the tool badge

A `@tool-<name>` tag above `Feature:` says what drives its scenarios; the console shows it as a badge beside the feature's name: `pytest` (steps calling the stack over HTTP or the bucket), `playwright` (steps clicking the storefront page in a real Chromium), `schemathesis` (requests generated from a contract), `k6` (a load). `tests/acceptance/conftest.py` keeps these tags out of the pytest markers. They all run through pytest-bdd, so the console runs and files them alike.

The **Driven by** filter, at the top of the page, keeps the features of one tool (`/tools/gherkin?tool=playwright`), each with its number of features; a feature naming no tool counts under `other`. A run started from a filtered page comes back to it.

## The storefront page: Playwright inside a scenario

Three features click the products of the storefront the way a customer does, each written from a recorded journey in the template of [Recorded scenarios](recorded-scenarios.md) (`@recorded`): `customer-welcome/welcome-page.feature`, `checkout/checkout-page.feature`, `account-access/sign-in-page.feature`. Their steps take the `page` fixture of `tests/acceptance/conftest.py` (a fresh browser context per scenario) and find elements by role and label, the way the Live experimentation cards name them. The runner image carries Chromium (`playwright install --with-deps --only-shell chromium`); locally, `mise run install` installs it. The runner plays them headless: nothing shows, the browser runs all the same (the verdict, the run in Test results). To watch it click: `mise run test:acceptance:headed` opens a visible Chromium, slowed down, on the three of them.

## Load: k6 inside a scenario

`customer-welcome/load-baseline.feature` (`@tool-k6`) plays `perf/customer-welcome-baseline.js`: ten customers greeted for half a minute through the storefront. The `When` step runs k6, the `Then` steps read the summary k6 writes (`summary.json`, parsed by `test_results/k6.py`): under 1% of failed calls, a p95 under 500 ms. k6 comes from mise locally (`k6` in `.mise.toml`) and from the k6 image in the runner; without it, the scenario skips and says `mise install`.

The same script is a load test job of its own: `mise run test:perf` runs it and files the run in Test results as `perf-customer-welcome-baseline` (kind `performance`): the k6 summary in **Details**, and one JUnit test case per threshold carrying the test metadata, so the run is filtered like any other.

## Partner contracts: schemathesis inside a scenario

`partner-contracts/bank-partner.feature` checks the real Bank Partner (the `partner` service of the stack, `PARTNER_URL`) against our copy of its contract, `contracts/bank-partner-openapi.yaml`. Every other test meets the bank through Microcks replaying that copy: if the bank changes what it answers, they all stay green while the real greeting breaks. This feature is the one that turns red.

- **Any username generated from the contract gets a documented answer**: schemathesis generates 50 requests the contract allows (positive mode: empty, accented, very long usernames) and three of its checks run on every answer, one Gherkin step each: `not_a_server_error`, `status_code_conformance`, `response_schema_conformance`.
- **A customer of the bank gets a balance shaped as the contract says**: an outline over the captured customers (`ada`, `grace`), each one request built by schemathesis from the contract, answered `200` with a body matching the `Balance` schema.

The generation runs inside a `When` step through Hypothesis (`operation.as_strategy()`), so the scenario stays the unit the console runs and files. A failing step quotes the first three failing requests, enough to replay them. Try it: change `balance_cents` to `type: string` in the contract and run the feature: the outline turns red with `Response violates schema`.

Negative mode (requests the contract forbids, such as no `username`) is left out on purpose: the partner answers them with a `422` its contract does not document, and that contract is the bank's to fix, not ours.

## Data the scenarios touch

The scenarios run against shared data, so they write only their own: an account is a new plus tag of the mailbox, an order takes one item of a product with a large stock (`BK-0004`, 68 items). A seeded account is only read, never given a wrong password.

Adding a scenario: the `/new-gherkin-scenario` skill follows the steps.
