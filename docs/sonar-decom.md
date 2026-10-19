# Leaving SonarQube: a quality gate on new code without a server

SonarQube blocks a merge request on a handful of conditions, and every one of them is scoped to the code the merge request adds. Switching it off without losing that gate is less about picking new analysers than about rebuilding the thin layer SonarQube sells on top of them: the new-code scope, the decision of what blocks, and one verdict. This page is the method, as it was applied to retire SonarQube from a real set of repositories in Python, JS/TS, PHP and Java.

> **TL;DR**
>
> - A linter alone replaces no quality gate: it reports on whole files and has no idea what a merge request changed. What you build is the scope, not the detection.
> - Keep the analysers each language already runs (ruff, ESLint with `eslint-plugin-sonarjs`, PHPStan, PMD, SpotBugs) and a duplication tool that covers every language (jscpd). Write no analysis of your own.
> - The gate is one job: diff against the merge base, keep the findings on added lines, intersect the coverage report and the duplicated spans with the same lines, fail when a condition is crossed, write GitLab's Code Quality report.
> - Two gates, one condition apart: **Standard** (no blocking finding, duplication under 3%, coverage of new lines at 80%) and **Starter** (the same without coverage, for a project with no test harness yet). No gate named means Standard.
> - A condition the gate could not measure fails, it never passes silently.
> - Security stays with the security scanner already in place (SAST, secrets, dependencies): scoring it twice is the double blocking this exercise removes.

## What SonarQube actually blocks on

Before replacing anything, read the instance rather than its marketing:

- List the quality gates and which projects use each (`api/qualitygates/list`, `api/qualitygates/search`). Years of "one more gate for this team" usually collapse into two: one with a coverage condition, one without. The others are a missing project setting (a duplication exclusion, an extra condition one project wants) dressed up as a tier.
- Count the open issues by type and language (`api/issues/search`). Expect the vast majority to be code smells, and most of those to be formatting: trailing whitespace, braces, naming, final newlines. A formatter fixes them at commit time; they need no gate at all.
- Keep only the rules typed **bug** as the blocking surface, and measure each candidate tool against that list, rule by rule, on a fixture that reproduces each rule. Reading a tool's documentation is not a measurement.

## Which analyser per language

| Language | Findings | What to know |
| --- | --- | --- |
| Python | ruff | Already the formatter and linter of most projects. Configure rules per path: `tests/` is not `src/`. |
| JS / TS | ESLint, `eslint-plugin-sonarjs`, `typescript-eslint` | `sonarjs` is SonarSource's own port of its JS rules: parity with the tool you retire is exact, not approximate. Faster linters (Biome, Oxlint) carry no such port yet. |
| PHP | PHPStan, a few custom rules | Most bug rules map to PHPStan identifiers; the rest are small custom rules, one class per rule, each with its reproduction. Regular expression analysis has no open source equivalent: accept that loss and say it. |
| Java | PMD, SpotBugs | SpotBugs finds most bug patterns but reads bytecode, so it needs the build first; PMD alone finds few. Check defaults: PMD's empty catch rule exempts variables named `ignored` unless configured. |
| All | jscpd | One duplication tool for every language. Older per-language tools (PHPCPD, PHPMD) are archived or unmaintained: check the last release before recommending one. |

## The gate itself

```text
merge base --(git diff)--> added lines of each file
                               |
analysers on changed files ----+--> findings on added lines --> severity table --> blocking?
coverage report (Cobertura) ---+--> covered / coverable added lines ------------> >= 80%?
jscpd on the repository -------+--> duplicated added lines --------------------> < 3%?
                                                                                  |
                                          one verdict + gl-code-quality-report.json
```

- **Scope**: `git diff --unified=0` against the merge base with the target branch, parsed into the added line numbers of each file. In CI, clone in full (`GIT_DEPTH: 0`): a shallow clone has no merge base, and the diff comes back wrong without any error.
- **Findings**: run the analysers on the changed files only, then drop every finding whose line is not an added one. What is left goes through a severity table, the part SonarQube calls a quality profile and no open source tool provides: which rules block, which are reported only.
- **Coverage**: reuse the Cobertura or JaCoCo report the test jobs already write, intersected with the added lines. Count lines and branches together, the way SonarQube scores it, so 80% means the same thing on both sides.
- **Duplication**: jscpd indexes the repository, its duplicated spans are intersected with the added lines.
- **Output**: GitLab's Code Quality JSON (the merge request widget shows it natively, whatever the language), plus an optional merge request comment with one line per condition, like the SonarQube comment it replaces.

Off-the-shelf pieces exist for parts of this (`diff-cover` and `diff-quality` for coverage and findings on a diff, reviewdog to post findings): use them when they cover your languages, write the glue when they do not.

## Rules learnt on real merge requests

- **A condition that cannot be measured fails.** A repository that forgets to publish its coverage report would otherwise trade the 80% condition for no opinion, silently. Same for an analyser that crashed: name the tool and the reason, never report a clean pass.
- **But "nothing to measure" is not a failure.** A merge request touching only CI YAML, a lockfile or docstrings has no coverable line. Distinguish four cases: nothing measurable in the change (not applicable), coverable files and no report (fail), reports that name none of the changed files (fail, almost always a wrong path prefix), no executable added line (not applicable).
- **Calibrate the severity table on real merge requests before blocking.** Run the gate beside SonarQube, non-blocking, for a few weeks. A naive table blocks on legitimate test idioms (private access in tests, magic numbers in assertions).
- **A rule that is shipped but never loaded is the worst failure.** A custom analyser rule copied into the image but not registered reports nothing and says nothing. Keep one fixture per rule and check every rule identifier fires on it.
- **Name gates, not thresholds.** Thresholds copied into each repository drift apart within a quarter; a repository picks a gate by name (`GATE_NAME: starter`) and the gate definitions live in one place.
- **Do not reproduce what you cannot measure honestly.** SonarQube's maintainability rating comes from a remediation cost per rule that no open source analyser publishes. Inventing one would look like a measure without being one; say "not rated" instead.

## Rolling it out

1. Audit the gates and the issues (above), agree on the two target gates.
2. Package the gate as one image per toolchain and one reusable CI job, so a repository adopts it with an `include:` and a variable, nothing to install.
3. Run it beside SonarQube, non-blocking, on a few volunteer repositories; fix the gate, not the repositories, when it is wrong.
4. Make it blocking, repository by repository, then switch SonarQube's analysis off and keep its data read-only until nobody asks for it.

What it costs beyond building the tooling, and is easy to forget in an estimate: the licence's notice period, developer communication, the cleanup of SonarQube jobs and tokens in every pipeline, and each repository's own adoption.

## In this repository

The `sonarqube` job of `gitlab-ci/mocks.yml` is a stand-in: it checks that both coverage reports exist and prints what it would send, calling no server. The reports themselves are real: `mise run test:unit` and `mise run test:integration` write `coverage.unit.xml` and `coverage.integration.xml` (Cobertura, from pytest-cov), uploaded beside each run's JUnit report in the results bucket, which is exactly what a gate on new code reads.
