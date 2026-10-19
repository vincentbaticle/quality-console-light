---
name: quality-gate
description: Check a branch of quality-console before pushing it, the way CI will: hooks, unit and integration tests with coverage, then the coverage the branch leaves. Use for "is my branch ready", "run the quality gate", "check before push".
---

# Quality gate before a push

1. `mise run hooks:run`: ruff, ruff format, mypy, YAML and TOML checks on the whole tree. New files are only checked once staged (`git add`), say so if some are not.
2. `mise run down` if the stack runs (Docker memory), then `mise run test`: unit, then integration, each writing its coverage report (`coverage.unit.xml`, `coverage.integration.xml`).
3. Read the coverage reports for the files the branch touched (`git diff --name-only main...`): a new line of `src/` no test runs is the gap to close. The method of a full gate on new lines, without a SonarQube server, is in `docs/sonar-decom.md`.
4. Report each step with its verdict. A red step is fixed in the files the branch touched only; a finding outside the diff is not this branch's to fix.
