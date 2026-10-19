---
name: new-api-test
description: Add an API endpoint to quality-console with its tests, or add a test to an existing endpoint, against Redis, the MySQL company database, the partner replayed by Microcks, the full stack, or a new neighbour started by testcontainers. Use for "add an endpoint", "new route", "add an API test", "test X against a real Y", "new testcontainers test".
---

# New API endpoint or test

The worked example in `README.md`, section "Adding an API endpoint and its tests", is the reference shape; `CLAUDE.md` holds the conventions. This skill only orders the steps.

1. Ask, in one question, what the endpoint or test must prove and which neighbour it needs. Read `src/hello_api/main.py` (or `src/quality_console/main.py` for the Quality Console) and `tests/integration/conftest.py` to see what already exists.
2. Endpoint: a response model and a route inside `create_app`, reusing `Username` and the helpers of `greeting.py`. Any pure rule goes in `greeting.py` (or a sibling pure module) with a unit test.
3. API test: `tests/integration/test_<feature>_<neighbour>.py`, `pytestmark = [pytest.mark.integration, metadata_test(...)]` with values of `catalog/catalog.yaml`, using the `api`, `redis_client` and `database` fixtures. A new column or table goes in `db/01-schema.sql` with its 10 rows in `db/02-seed.sql`. Cover the happy path, one refusal (422), and what lands in the neighbour.
4. Partner data needed: a captured username goes in `tests/story.py` then `mise run partner:up`, `mise run capture:examples`, `mise run capture:merge`, and the diff of `contracts/` is shown to the user; an error case is a hand-written example. A new partner API is a new contract in Microcks, see the README.
5. New neighbour only: apply the four steps of "A new neighbour gets" in `CLAUDE.md`.
6. Front change only: a browser test with `stack_url` and `page`, roles and labels, `expect`, no sleep.
7. Run `mise run test:integration -- -k <feature>` twice, then `mise run test` and `mise run hooks:run`. Fix only what you touched.
8. Update `README.md` (and the matching script of `docs/demos/` when a demo step or command changes) if the list of endpoints, levels or neighbours changed, and report the commands run with their result.
