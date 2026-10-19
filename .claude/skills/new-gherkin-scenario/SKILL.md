---
name: new-gherkin-scenario
description: Add an acceptance scenario to quality-console, written in Gherkin under features/<product>/, bound with pytest-bdd in tests/acceptance/, runnable from the Quality Console. Use for "add a scenario", "new Gherkin", "acceptance test for X", "BDD test".
---

# New Gherkin scenario

Scenarios describe what a product does for its user, in the words of the product; they run against the stack `mise run up` started, never against containers of their own. `CLAUDE.md` holds the conventions.

1. Ask, in one question, which product the scenario belongs to and what it must prove. The products are the folders of `features/` and the `products` of `catalog/catalog.yaml`; a new product needs its catalog entry first (`mise run catalog:sql`).
2. Add the scenario to the matching `.feature` file, or a new file in that folder. One behaviour per scenario, the outcome in the `Then`, no technical detail in the steps (no URL, no SQL, no status code unless the code is the behaviour). Under the `Scenario:` line, a `Goal:` line says why it matters (a unit test refuses a scenario without one). Above `Feature:`, a `@tool-<name>` tag says what drives it: `pytest`, `playwright`, `schemathesis`, `k6`. A scenario written from a recording (`/record-scenario`) keeps its template: `@recorded`, one Given per actor, the data recipe, what is seen.
3. Reuse a step of `tests/acceptance/test_<product>.py` or `tests/acceptance/conftest.py` before writing one. A step that clicks the storefront takes the `page` fixture (Playwright) and finds elements by role or label, as the cleaned recording names them. A new step is a function with `@given`, `@when` or `@then` and `parsers.parse`, keeping state in the `context` fixture, calling the stack through `stack` URLs only.
4. A scenario that writes data uses its own data: a new plus tag of the QA mailbox (`plus_address`), a product with stock, never a shared seeded account it could block.
5. Run it: `mise run up`, then `mise run test:acceptance -- --only-feature=<product>/<file>.feature`, twice. Then open the Quality Console, **Tools**, **Gherkin scenarios**, and click **Run** on it: the same result, filed in Test results.
6. `mise run hooks:run`, then `mise run test:unit` (it checks the metadata of the new module against the catalog).
