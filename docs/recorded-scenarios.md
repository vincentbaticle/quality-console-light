# Recorded scenarios: from a journey clicked to a Playwright test

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

A person who knows the product (a PO, a QA) clicks a journey on the storefront; it becomes a Gherkin scenario a developer turns into a Playwright test, run from the console. The chain comes from a team's `record-test` skill and the decisions around it (the scenario template, the cleaning of the recording, the test ticket, the target workflow), taken here on the storefront of MyCompany to see what each one is worth.

> **TL;DR**
>
> - `/record-scenario` (a skill of this repository): Codegen records the journey and its network, the secrets are cleaned on the machine, three questions are asked, a scenario is written in the template, a test request beside it.
> - The template: one `Given` per actor (`"<actor>", a <account type> who <rights>`), a `Given` for the data, a `Then` for what is seen. One scenario, no examples table, no hardcoded date. `@recorded` features are checked by a unit test, a draft by the MCP tool `check_scenario`.
> - Three worked examples, run from **Tools**, **Gherkin scenarios**: `customer-welcome/welcome-page.feature`, `checkout/checkout-page.feature`, `account-access/sign-in-page.feature` (`@tool-playwright`).

## The chain

1. **Record** (`/record-scenario`, steps 1 to 4): Playwright Codegen on `http://localhost:8080/#<product>`, with `--save-har`. The person plays the journey and closes the window.
2. **Clean, at once**: `scrub_recording` (MCP tool, or `python -m scripts.scrub_recording`) writes the cleaned script and HAR and deletes the raw ones, before any question, so nothing uncleaned survives even if the person stops there.
3. **Ask the three facts**: who plays, from which data, what is seen. The MCP tool `test_accounts` offers the accounts of the tenant with their profile in the words of an actor line.
4. **Write the scenario** in the template, checked by `check_scenario` until it is ready.
5. **File a test request** in `capture/test-requests/` (the stand-in of a test ticket, see below).
6. **Generate the steps** (`/new-gherkin-scenario`): Playwright steps written from the cleaned recording, by role and label.
7. **Run** in the console: the verdict, and the run filed in Test results.

Steps 1 to 5 need no knowledge of the repository; 6 and 7 are a developer's.

## The template, and why each fact

| Fact | In the scenario | Why |
| --- | --- | --- |
| Who plays | `Given "ada", a customer of the company who can order` | The person recorded with their own account and would not think to say so: a test generated from the clicks alone fails for anyone else. The account and its rights are test data. |
| From which data | `And the stock of "BK-0004" holds at least 1 item` | A journey starts from a state: written down, it can be checked or created before the first click. |
| What is seen | `Then the page shows every step done and the order paid` | The clicks say what was done, not what had to happen. |

The checks (`src/quality_console/scenario_template.py`): at least one actor with an account type and rights, an actor line without them refused, at least one data `Given`, at least one `Then`, no date written in a step, one scenario, no examples table.

The sign-in example shows the point of the account fact: its actor is "a new customer", and its data step creates that account with a password through the tenant and the QA mailbox, so it never depends on whose account recorded it.

## Cleaning a recording

What `src/quality_console/recording_scrub.py` removes, deterministically:

- **The HAR**: authentication headers (`Authorization`, `Cookie`, `Set-Cookie`, any header naming a token, a key, a secret or a session), cookies, secret query parameters, and the secret fields of JSON and form bodies (password, token, secret, API key, session, one-time code, and the `ticket` of a password link). Every other body content is kept: a test needs it. A token exchange (a body naming `client_secret`, `access_token`, `refresh_token` or `id_token`) is dropped whole.
- **The script**: the values typed into a password, code or authenticator field, and the credentials carried by URLs.

The report says where and what, never a value. A HAR that cannot be read is deleted without a copy, since nobody could check it.

## The test request

The stand-in of a test ticket, one per recording, in `capture/test-requests/<name>.md`: title `[E2E TEST] <product> | <scenario>`, label `record-test`, and `needs-scenario-review` when a fact could not be answered. Its statuses: created, generation started, closed when the test is merged, abandoned. With a real Jira it is a Task in the project of the team owning the product (`jira_project` of the catalog), linked to the product ticket, created only after a yes.

## Three more examples with the MCP server

1. **"Is this draft ready to become a test?"** Paste the Gherkin; Claude calls `check_scenario` and answers what is missing ("No data recipe: add a Given saying what data the journey needs").
2. **"Which account should play a customer with a second factor?"** `test_accounts` lists the tenant's accounts and their profiles; `qa-mailbox+lin@mycompany.test` is "a customer account who signs in with a password and a second factor".
3. **"Clean the recording I just made before I share it."** `scrub_recording("capture/recordings/raw-checkout.py", "capture/recordings/raw-checkout.har")`: the cleaned copies, the raw files deleted, and the list of what was removed where.

## What it is worth here

- The template catches the missing account at writing time, not when the test fails in someone else's hands: the unit test runs it on every `@recorded` feature.
- The cleaning is what makes it safe to hand a recording to someone else: the account access journey types a password, the identity API answers a ticket.
- The test request keeps the scenario's owner and status outside the code, until the test is merged.

## Where it lives

- `.claude/skills/record-scenario/SKILL.md`: the skill.
- `src/quality_console/scenario_template.py` and `recording_scrub.py`: the checks and the cleaning, unit tested (`tests/unit/test_scenario_template.py`, `test_recording_scrub.py`).
- `scripts/scrub_recording.py`: the cleaning from a terminal.
- `features/*/<...>-page.feature` + the Playwright steps of `tests/acceptance/`: the three worked examples; `tests/acceptance/conftest.py` holds the actor step and the `page` fixture.
- `src/quality_mcp/tools.py`: `check_scenario`, `test_accounts`, `scrub_recording`.
