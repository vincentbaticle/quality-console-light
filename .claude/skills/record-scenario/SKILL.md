---
name: record-scenario
description: Record a journey on the storefront with Playwright Codegen and its network capture, clean the secrets on this machine, ask who plays, from which data and what must be seen, then write a recorded scenario in the template (features/<product>/, tagged @recorded @tool-playwright) and a test request beside it. For a PO, a QA or a developer. Use for "record a scenario", "record a journey", "record-test", "turn what I click into a test".
argument-hint: "[product: customer-welcome|checkout|account-access]"
---

# Record a scenario

A recording shows clicks; it does not say who plays, from which data, nor what must be seen at the end. This skill records the journey, cleans it, asks for those three facts, and writes them as a scenario in the template of `src/quality_console/scenario_template.py`. The scenario then becomes a test with `/new-gherkin-scenario`, its Playwright steps driving the same page. Read `docs/recorded-scenarios.md` first.

The stack must run (`mise run up`). Nothing here leaves the machine.

## 1. Where the journey starts

Ask, in one question, the product (`customer-welcome`, `checkout`, `account-access`, or `$ARGUMENTS`) and what the journey must prove. The page is `http://localhost:8080/#welcome`, `#checkout` or `#account`.

## 2. Record, with the network

```bash
mkdir -p capture/recordings
mise exec -- pdm run playwright codegen --target python-pytest \
  --output capture/recordings/raw-<name>.py \
  --save-har capture/recordings/raw-<name>.har \
  "http://localhost:8080/#<anchor>"
```

Tell the person: a browser opens, play the journey, close the window to stop. `capture/` is never committed.

## 3. Clean the secrets, right away

Before any question, call the MCP tool `scrub_recording` (server `quality-console`, see `docs/mcp.md`) with both raw paths, or:

```bash
mise exec -- pdm run python -m scripts.scrub_recording \
  capture/recordings/raw-<name>.py capture/recordings/<name>.py \
  capture/recordings/raw-<name>.har capture/recordings/<name>.har
```

It removes the values typed into password or code fields, the authentication headers and cookies, the secret fields of every body (password, token, ticket, code), the credentials of URLs; it drops the token exchanges whole; it keeps every other body; it deletes the raw files. Report the locations and kinds it found, never a value. Read the cleaned script once more for a secret a pattern cannot know, and redact it with `<REDACTED>`.

## 4. Confirm the journey

Turn the cleaned script into one plain line per action ("Opened the checkout", "Typed into Customer username", "Clicked Place order") and ask: does this match the journey? `retry` records again.

## 5. Ask the three facts

In business words, never about the repository:

1. **Who plays?** For each person in the journey: the account type and exactly what it must be able to do. Call the MCP tool `test_accounts` to offer the accounts the tenant holds, with their profiles. The person recorded with their own account and will not think to say it: ask.
2. **From which data?** What must exist before the first click: a product in stock, a bank account, a new account with a password. Prefer data the scenario creates itself.
3. **What must be seen?** What the page shows at the end, as the customer reads it.

## 6. Write the scenario in the template

`features/<product>/<name>.feature`:

```gherkin
@recorded @tool-playwright
Feature: <what the journey does, for whom>
  <why it matters, two or three lines>

  Scenario: <the journey in one sentence>
    Goal: <the risk it closes>
    Given "<actor>", a <account type> who <rights>
    And <the data the journey starts from>
    When <the journey, in the customer's words>
    Then <what the page shows>
```

One scenario, no examples table, no hardcoded date. Check it with the MCP tool `check_scenario` until `ready` is true: it is the check `tests/unit/test_scenario_template.py` runs on every `@recorded` feature.

## 7. Write the test request

The stand-in of a test ticket: `capture/test-requests/<name>.md`, never committed.

- Title: `[E2E TEST] <product> | <scenario name>`.
- Labels: `record-test`, and `needs-scenario-review` when a fact could not be answered (data the stack cannot create, an action Codegen missed).
- Status: `created`, then `generation started`, `closed` when the test is merged, or `abandoned`.
- Body: the scenario, the cleaned recording, the product page, the number of HAR entries kept (the HAR itself stays in `capture/recordings/`).

With a real Jira, this is a Task in the project of the team that owns the product (its `jira_project` in `catalog/catalog.yaml`), created only after the person says yes, linked to the product ticket.

## 8. Hand over

Tell the person where the scenario and the request are, and the next step: `/new-gherkin-scenario` writes its Playwright steps from the cleaned recording (`get_by_role`, `get_by_label`, `expect`, never a sleep), then **Run** in the console.

## Never

- Read or print a secret, or a value the cleaning removed.
- Leave a raw file: the cleaning deletes them, run it before any question.
- Generate the steps, run tests or commit: that is `/new-gherkin-scenario` and the person's call.
