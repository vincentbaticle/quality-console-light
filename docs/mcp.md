# The Quality Console MCP server

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

An MCP server that lets Claude Code (or any MCP client) do what a tester clicks in the console: run a Gherkin scenario, read the last test runs, measure which tables a test touches. It talks to the local Docker stack only, the one `mise run up` started.

> **TL;DR**
>
> - `mise run up`, then open Claude Code in the repository: `.mcp.json` declares the server `quality-console`, Claude Code asks once to enable it (`/mcp` shows it).
> - Eight tools: `list_scenarios`, `run_scenario`, `recent_runs`, `footprint_targets`, `table_footprint`, and for recorded scenarios `check_scenario`, `test_accounts`, `scrub_recording`.
> - By hand: `mise exec -- pdm run python -m quality_mcp` (stdio). The MCP SDK is a dev dependency.

## Three examples

Ask Claude Code in plain words, it picks the tools.

1. **"Does the Bank Partner still keep its contract?"**
   Claude calls `list_scenarios`, finds `partner-contracts/bank-partner.feature`, then `run_scenario` on it. The answer: `passed`, 3 of 3, and the run id in Test results. Red, it quotes the failing requests schemathesis built.
2. **"Which tables does placing an order touch?"**
   `footprint_targets` gives the key `place-order`, `table_footprint("place-order")` plays it 10 times (about a minute) and answers from the trace: the tables, who read or wrote each one (`hello-api write orders`...), and any table the database saw in every run but no trace names.
3. **"What failed in the last runs, and is it always the same job?"**
   `recent_runs(status="failed", limit=20)` rebuilds the run index and lists the failed runs, newest first: job, environment, kind, time, run id. Claude groups them by job; open one in the console with its run id.

Three more, around recorded scenarios ([Recorded scenarios](recorded-scenarios.md)):

4. **"Is this draft ready to become a test?"** `check_scenario(gherkin)` answers what the template misses: an actor without its account type and rights, no data recipe, nothing observed, a hardcoded date.
5. **"Which account should play a customer with a second factor?"** `test_accounts` lists the accounts of the identity tenant with their profile in the words of an actor line.
6. **"Clean the recording I just made."** `scrub_recording(recording, har)` writes the cleaned copies, deletes the raw ones, and lists what was removed where.

## The tools

| Tool | What it does | Reaches |
| --- | --- | --- |
| `list_scenarios` | Every feature of `features/`, its scenarios and the goal of each | the repository |
| `run_scenario(feature, scenario="")` | Runs a feature or one scenario, answers the verdict, the counts, the end of the output and the run id | the Gherkin runner, <http://localhost:8082> |
| `recent_runs(job_name="", status="", limit=10)` | The last runs of the results bucket, after a fresh index | the bucket emulator, <http://localhost:4443> |
| `footprint_targets` | The tests retro-footprint can play | the repository |
| `table_footprint(target)` | Plays a test 10 times, answers its tables from the traces, checked by the database | the console, <http://localhost:8081> |
| `check_scenario(gherkin)` | Checks a draft against the template of a recorded scenario | nothing, pure |
| `test_accounts` | The accounts of the identity tenant and what each can do | MySQL `identity`, read-only, `localhost:3307` |
| `scrub_recording(recording, har="")` | Cleans a Codegen script and its HAR, deletes the raw files | the files named |

The URLs are the ports of `docker-compose.yml`; `QC_CONSOLE_URL`, `QC_RUNNER_URL`, `STORAGE_EMULATOR_HOST` and `RESULTS_BUCKET` change them.

## Why an MCP and not the pages

The pages show a person what happened; the tools give an agent the same facts as data it can compare, sum up and chain: run a scenario, then read the run it filed; measure a footprint, then ask which scenario covers those tables. Nothing new is computed: each tool calls what a console button calls.

## Where it lives

- `src/quality_mcp/tools.py`: the tools as plain methods (`QualityTools`), and their pure helpers, unit tested in `tests/unit/test_quality_mcp.py`. The checks and the cleaning they call live in `quality_console/scenario_template.py` and `recording_scrub.py`.
- `src/quality_mcp/server.py`: registers them on a `FastMCP` server, wired to the stack's URLs; `python -m quality_mcp` serves it over stdio.
- `.mcp.json`: the project server declaration Claude Code reads.
- `tests/integration/test_console_tools_mysql.py`: the tools against the console and the runner served in process, a real bucket emulator and MySQL.
