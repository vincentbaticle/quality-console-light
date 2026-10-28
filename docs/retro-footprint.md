# retro-footprint: which fronts, APIs and tables does a test touch?

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

The question: a test opens pages of some fronts, calls some APIs, maybe reads the database itself, and those APIs read and write some tables; colleagues use the same database at the same minute. Which fronts, APIs and tables are my test's? The name says how: the footprint is found after the fact, from what the test left behind (counters, traces), not from its code. **DevX**, **retro-footprint** answers it on the real stack, with one click.

> **TL;DR**
>
> - **The answer comes from the traces** when the services are instrumented (OpenTelemetry): every span carries the trace id of the request, so one trace gives the exact list of fronts and APIs the test went through, including the ones called behind its own calls, and of the tables each one touched, in order, whatever colleagues do.
> - **The database checks the coverage**: its counters (`performance_schema`) see every table touched, traced or not, but not by whom. Repeated runs rule the colleagues out (a table of the test is seen in every run, a colleague's only in some); a table still seen in every run that no trace names means something untraced touched the database during the test.
> - **Without traces, the database is the answer**: tables only, the APIs behind a call stay unknown.
> - Run in **two batches with a pause between**, not one: a colleague busy during your whole first batch looks exactly like your test; after the pause they are gone.

## What to run

A test is a few steps: pages of a front opened, API calls, SQL queries of its own. The list offers one test per case:

| Test | Steps | What it should find |
|---|---|---|
| API only: `GET /api/health` | one API call | one API, no table (the API pings Redis only) |
| SQL only: the backpack's stock | one query of the test | no API, `products` and `stock_levels` |
| API using tables: `GET /api/hello?username=ada` | one API call | `hello-api`, then the bank partner behind it; `customers`, `bank_accounts` |
| API using tables: `POST /api/orders, until paid` | one API call, followed until the workflow ends | `hello-api`, then the worker's steps; 9 tables |
| API using tables, then SQL: `GET /api/hello`, then ada's profile | one API call, then one query of the test | the hello path, then `customers`, `customer_addresses`, `customer_preferences` read by the test |
| Front, then API using tables: the storefront greets ada | a page of the storefront, then one API call | the storefront, then the hello path |
| Front, API, then a redirect to another front | a page of the storefront, one API call, then a page of the Quality Console reached by a redirect | the storefront, the hello path, then the Quality Console reading `customers` itself |
| Resource optimization: the same greeting twice | the hello call, twice | every endpoint and table of the hello path used twice: **2 calls and 4 queries to spare** |
| Ownership: a service whose team forgot to declare it | one API call, then one call of the newsletter service (`NEWSLETTER_URL`) | the hello path, owned by its teams; `customer_preferences`, `newsletter_subscriptions`, `newsletters`, read by the newsletter service only: **3 orphan tables** |

Two more tests, under *Simulated examples*, call nothing: their runs are drawn from a fixed seed (`demo_run` in `quality_console/footprint.py`, a run every 2 seconds, a pause of 4), so they look the same every time. They show how the page holds what the real tests are too small to show:

| Example | Steps | What it shows |
|---|---|---|
| Demo, too many items | 12 steps through 5 fronts and a dozen APIs, some played in only some runs (a coupon check, a help-center ticket, a return) | 5 fronts, 11 APIs, the 30 tables: too many to read at once: the grid keeps the most seen and folds the rest into a *+N* tile |
| Demo, hard to tell for 7 runs | 4 steps, while a nightly job reads 8 tables during runs 1 to 7, 3 of them the test's own | until run 8, the job's tables are seen as often as the test's; runs 8 to 10 rule them out |
| Demo, many of a kind | 10 fronts in a row, then one export reading 29 tables, while a database trigger nobody traces writes `audit_logs` | a stack of 10 fronts, a stack of 29 tables, and `audit_logs` *counted only, no trace* in the final answer |

Two fronts play the parts of a company's intranet and of its developer portal (a Backstage, say): the **storefront** (nginx, `FRONT_URL`), a static front calling the API from the browser, sending no trace; and the **Quality Console** (`CONSOLE_URL`), a server-rendered front reading the database itself, instrumented like the API. The lab opens a page the way a browser asks for it (one `GET`, no JavaScript run); the API call the page would make is the next step of the test. The redirect is told by the test (`redirect=True` on the step), the way a test following a link or a `302` knows it; the path draws it on the dotted line.

## Three answers

The page puts its three answers first, each in its own numbered card, linked from a strip under the progress bar:

1. **Path of the test**: every front, API and table the test goes through, in order, the traces and the database's count merged.
2. **Ownership**: which team owns each table, API and message broker in Grafana, and the orphans.
3. **Resource optimization**: the endpoints called, the messages published or consumed and the tables read more than once, with the team owning each, where once would do.

## What one click on Run does

While an analysis runs, its page locks the test list and **Run** (*Running…*) until the last run and the traces are done; the display buttons (the tabs, the stacks, the *+N* tiles, the witnesses) stay free, they only redraw. The console also refuses a second real analysis while one runs, from another tab, another person or the MCP server: two at once would count each other's queries as a colleague's. **Run** then opens the running one with a red banner saying so, and the MCP tool answers that an analysis is running. The simulated examples touch nothing, so they neither block nor wait.

**Run** plays the test 10 times, in two batches: 5 runs in a row, a pause of 20 seconds, 5 more runs. About a minute in all (a bit more for the order).

For each run, in a background thread of the console:

1. Read the table counters of `mycompany` in `performance_schema.table_io_waits_summary_by_table` (reads and writes per table, whoever sent them).
2. Start colleagues: a second connection reads some tables at random moments (`SELECT 1 FROM <table> LIMIT 1`). Loud at first, quieter later: 16 tables in run 1, then 9, 5, 2, 1; in the second batch 6, 3, 2, 1, 1.
3. Play the test's steps, one after the other: open a page of a front (`GET` on the front, as a browser would), call the storefront API for real (`API_URL`; for an order, follow the workflow until it ends), or run the test's own query from its own connection. The counters are read before and after each step, and every 40 ms during it: each table is tied to the step that moved it, in the order it moved.
4. Read the counters again: the difference is every table touched during the run, by the test or by anyone else.
5. Keep, among the candidates, the tables this run saw again.

### Why a pause, and how long

The intersection rules out a colleague's table as soon as one run does not see it. It fails when a colleague touches the same table in every run, which happens when their activity lasts longer than your runs: a test of theirs looping, a batch job, a dashboard refreshing every few seconds. Five runs in a row take about ten seconds; anything busy for those ten seconds survives all five.

The tool plays such a colleague: during the whole first batch, one colleague loops their own test on 2 tables, so these tables are seen in all 5 runs and the first batch keeps them. The pause outlasts that activity: in the second batch the colleague is gone, and the first run of it rules their tables out.

The pause only has to be longer than the colleague activity you want to rule out. Here the looping colleague stops with the first batch, so 20 seconds is plenty. On a shared environment, pick it from what runs there: a few seconds beat a dashboard refreshing, a minute or more beats another team's test loop or a job.

Five more runs right away would not do it: they would still fall inside the colleague's loop. What matters is that the two batches are far enough apart in time; the count of runs only beats random noise.

## A third witness: the SQL spans of each run window

The traces of run 1 name what the test's own services did. Once the runs are over, Tempo is also asked, run window by run window (`WINDOW_QUERY`, `{ span.db.system = "mysql" && span.db.name = "mycompany" } | select(span.db.statement)`, between the run's start and end with a second of slack), for every SQL span on the company database, whoever sent it: the colleagues' queries included, since the console that plays them is instrumented too. Each table it names comes with the services of those spans and the number of windows it showed up in. The runs follow each other closer than that second of slack, so a window also catches the calls of the runs on either side: the trace of every call the test starts is kept with its run, and a window leaves out the traces of the other runs' calls. Each window then holds its own run of the test exactly, plus whoever else queried meanwhile; time alone can't tell runs a fraction of a second apart, the trace id can.

Matched with the database count, it says **who** touched each table: the final answer writes it under each table (`SQL from hello-api in 10/10 windows`, or `no SQL span in the run windows` for a table touched by something that sends none). Tempo takes a few seconds to hold a span, so the lab waits 5 seconds after the last run before reading the windows; the page says so, and the final answer waits for them.

It also decides between the two readings of a table the database counted in every run but no trace names. The intersection cannot rule out a colleague busy through every run; the spans can:

- spans on it in every run window, only from services off the test's path (its fronts, its APIs, its workers, and the console when the test runs SQL of its own, since the lab sends that SQL): **likely a colleague**, kept in the answer but left out of the coverage warning;
- spans from the test's path, or no span at all: **counted only, no trace**, something of the test that sends no trace (a trigger, an untraced service).

The spans are a help, never a requirement: when Tempo is unreachable or not configured, the final answer comes without them, each such table stays *counted only, no trace*. They are also the witness that needs no database account: on a stack where the test has no right on `performance_schema`, they still say which tables were touched and by whom, for the services that send SQL spans.

The lab card shows four stages under the progress bar (Tempo is the trace store of the observability service): **Runs** (n of 10), **Traces** (reading, read, none found, nothing traced), **SQL per run window** (waiting, reading run n, n tables, no Tempo) and **Final answer**, ready only once every witness spoke.

## Reading the traces

The trace of each API call of run 1, and of each page of a front sending traces, is read in Tempo (`TEMPO_URL`) while the next runs go on. The call starts its own trace (a `traceparent` header; when the console's own instrumentation replaces it, the header really sent is read back from the request), so Tempo is asked for that trace id directly (`/api/traces/<id>`), until it stops growing: a second or two. A TraceQL search, `{ resource.service.name = "hello-api" && name = "GET /api/hello" }` over the call's window, is the fallback when the id is unknown; Tempo only finds a trace that way about half a minute after its last span.

The trace's spans, in the order they started, give:

- the APIs: each server span opens an API (`GET /api/hello` of `hello-api`, then `GET /accounts/{username}` of `bank-partner`); each consumer span a worker taking a message (the order workflow's steps);
- the tables: each SQL span (`db.statement`) names its tables, the service that ran it, read or write (`INSERT INTO payments ... SELECT ... FROM payment_methods` writes the first and reads the second).

A query of the test itself needs no trace: its statement, in the test's code, names its tables. A static front sends none: the test knows it opened it, and the API calls of its page are steps of their own.

## What the page shows

- A progress bar that follows time: each run weighs what the runs lasted so far, the pause its 20 seconds, the last 4% wait for the traces once the runs are over. For the hello test (10 runs of 10 to 15 s in all), the first batch fills about a fifth of the bar, the pause's countdown the next half, the second batch the rest. Each run of the order lasts about 5 s, so there the runs weigh more.
- **Path of the test**: each stop joined by a dotted line, in the order it happened. A front has a browser window icon, an API a globe, a worker an envelope, a query of the test a terminal, a table a database cylinder; a dotted line marked *redirect* leads to a front the previous one sent the user to. Every stop has the same look; only the icon tells its kind, each kind in its own colour: fronts violet, APIs and workers blue, tables amber, queries of the test grey (the legend uses the same). Two paths, one under the other:
    - **The final answer: the traces and the database's count, merged**, once the runs are over and the traces read (`Experiment.final`): the path of the traces, each table marked `named + counted` (both witnesses agree), `named, not every run` (the traces name it, some run did not see it move: a cache, a branch), `counted only, no trace` (counted in every run, named by nothing: a trigger, an untraced service) or `likely a colleague` (counted in every run, but the SQL spans of the run windows show only services off the test's path on it), placed after the step it moved during in the last run. It comes once the runs are over, the traces and the run windows read, whether that reading worked or not. The witnesses below it are always folded, the runs going on or not; a click opens one.
    - Two witnesses that do not see the same thing: the services write down what they do (the traces), so they know who touched which table but miss whatever writes no notes; the database counts every table touched, by anyone, but cannot say who. The first gives the answer, the second checks it.
    - **The answer: what the services say they did (their traces)** (once read): the database is not asked here, run 1 followed from inside the services, so the fronts, the APIs behind each call (the bank partner) and the tables each one touched, then the test's own queries and their tables. Exact in one run. When nothing in the test is traced (the SQL-only test), it is *named by the test itself*. A table touched by two stops shows twice; a service touching a table after another API answered comes back on the path.
    - **Coverage check: did the traces miss a table? (the database's own count)**: one line per step, *While <step> ran, the database saw <tables>*. The step is a time marker in grey, the database does not see it; only the tables come from the database: the ones that moved while the step ran and that every run so far saw too (from the last run), each with its access (`read`, `write`) and `seen in 4 of 4 runs`, with the check's result once the runs are over: *covered* when the database saw exactly the tables the answer names; a warning naming the tables the database saw in every run but no trace names (something untraced touched them, or a colleague exactly as busy as the test); a note for a table of the answer that some run did not see (used only on some calls).
    - When no trace is found, there is one path only, **The answer: what the database saw**: tables only.
- **Stacks**: on a path, items of one kind in a row (3 or more) fold into one stop drawn as a stack: `29 tables, 29 read, 0 written`, `10 fronts, 9 reached by a redirect`; click it to unfold, *fold* to fold it back.
- **When the grid gets crowded**: it keeps, per kind, the items seen in the most runs (4 fronts, 6 APIs, 10 tables) and folds the others into a dashed *+N* tile saying how often they were seen at most. Clicking a *+N* tile shows the rest, *Show fewer* folds it back. To keep the page fast whatever the test: at most 150 tiles drawn, hidden items never built, and the paths and the grid drawn again only when a run ends or the traces move, not at each poll.
- **Fronts, APIs and tables used so far**: the fronts ("opened by the test" or "after a redirect"), the APIs ("called by the test" or "in the trace"), each with the number of runs its step was played in (`7/10 runs`: a step skipped in some runs, a branch), then only the tables some run saw, not the 30. Black, still candidate, numbered in the order the last run touched them; light grey, ruled out; outlined, confirmed by the trace. Each table says it under its name, with how the runs used it (`read`, `write` or `read + write`) and in how many runs the database saw it (`4/5 runs`): one run missing is enough to rule a table out. Each table tagged `live` (the storefront writes it) or `static`.
- **Run details**, folded by default: one tab per run, the pause between the two batches: the steps with their outcome (`HTTP 200`, `2 rows`) and the tables each moved, the colleagues' tables (the looping colleague in blue), every table seen with its reads and writes, what the run ruled out. The **Coverage check** tab opens when the runs end: the answer's accesses (service, table, read or write) beside the tables the database saw in every run, and the check's result.

## Ownership: orphan tables, APIs and destinations, invisible in Grafana by team

An observability platform files telemetry under a team when the service says which one: here a `team` resource attribute, set with the standard `OTEL_RESOURCE_ATTRIBUTES` variable of the [OpenTelemetry SDK configuration](https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/) (`team=storefront-squad`). Every span of the service carries it, so each SQL span says which team touched which table. A team that forgets the line still sends spans, but nobody owns them: searching by team never finds its tables.

`docker-compose.yml` declares the team of each service from `catalog/catalog.yaml` (`hello-api`, `order-worker`, `identity-service`, `bank-partner`, `quality-console`), except one: the **newsletter service** (`src/newsletter/`, service `newsletter`), owned by the storefront squad in the catalog, deployed without its `team`, a forgotten declaration.

Once the final answer is ready, the **Ownership** card shows three groups, tables, APIs and message brokers, each counting how many are owned. An owned tile is green, with its team in a green badge. A table is in one of these states:

- **owned**: a span of the test's traces naming the table comes from a service declaring a team; the team is shown, and so is the TraceQL query a team runs in Grafana to find what it owns (`{ resource.team = "storefront-squad" }`);
- **orphan**, in red with a banner: the database counted it in every run, but no span of a declared team names it. Either its spans come from services declaring no team (`spans of newsletter-service, no team declared`), or there is no span at all (`counted by the database, no span names it`: a trigger, an untraced service);
- **the test's own SQL**: named only by a query of the test, no service to own it.

An **API** is owned when the service answering it declares a team, so its server spans are filed under it; the tile lists the routes the test called (`service_ownership`). A **message destination** (a queue, a topic, an exchange) is owned when the services publishing to it or consuming from it declare one; the tile says who published and who consumed. Neither has a database count behind it: both come from the spans of the traces only.

Likely colleagues are left out. The final path marks each orphan table too. Without a trace (Tempo unreachable, a test of SQL only), ownership stays unknown: the teams are only in the spans.

The test *Ownership: GET /api/hello, then a service whose team forgot to declare it* shows it for real: `customers` (the storefront API and the bank partner) and `bank_accounts` are owned, the 3 tables only the newsletter service reads are orphans. In Grafana, `{ resource.service.name = "newsletter-service" && resource.team != nil }` finds nothing. The simulated *many of a kind* shows the other cause: `audit_logs`, written by a trigger nobody traces.

## Resource optimization: endpoints, messages and tables used more than once

Each server span is one call to an endpoint, each producer or consumer span one message, each SQL span reading a table one query on the database. Once the traces are read, all three are counted one by one: endpoints, then messages, then tables. Each item shows the team of the services using it in a green badge, or *no team*, so the card says who to ask.

**Endpoints.** `trace_api_hits` lists every server span with the service that called it (the service of its parent span; a call from the console's lab, or from outside the trace, is the test's). `api_hints` lists each endpoint called more than once:

- **same call again**: one caller calls it twice or more during one step: a loop or a missing cache;
- **called by several services**: the first caller could pass the answer along;
- **called again later**: one caller calls it again in a later step: keep the first answer, or cache it.

The test *Resource optimization: GET /api/hello, then the same greeting again* shows it for real: `GET /api/hello` called twice by the test, `GET /balance` of the bank partner twice by the storefront API, `customers` read 4 times and `bank_accounts` twice: 2 calls and 4 queries to spare.

**Messages.** `trace_message_hits` lists every producer span (a message published) and consumer span (a message taken), with its destination: the `messaging.destination.name` attribute of the [OpenTelemetry messaging conventions](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/), the span's name when it has none. `message_hints` lists each destination one service publishes to, or consumes from, more than once: **published again** (one message carrying everything would do) or **consumed again** (one message, or a batch).

**Tables.** Each SQL span reading a table is one query on the database. Once the traces are read, every SQL span of the test is kept one by one (`span_accesses`, nothing merged), with the step it ran during; the test's own SQL counts as spans of `the test`. `optimization_hints` lists each table read more than once, with what to change, the strongest case first:

- **same query again**: one service runs the same statement twice or more during one step: a loop of queries (an N+1) or a missing cache;
- **read by several services**: the first service could pass what it read along with its call, so one read would do;
- **read again by one service**: one service reads the table in another query or a later step: one read, or keeping what the first returned, would do.

Writes are left out: writing twice may be what the test is about. The card says how many queries one read per table would spare, and draws each table's reads in order, each with the step it ran during.

The ownership test shows it for real: `customers` is read three times for one customer, by the storefront API and the bank partner during the hello call, then again by the newsletter service: 2 queries to spare.

## Limits of the intersection

- It never proves a table used only on some calls (a cache miss, a branch): such a table drops out like a colleague's.
- Colleagues who touch the same tables as the test at the same moment cannot be told apart; anybody using the stack meanwhile is a real colleague. A colleague busy for longer than the pause survives it too.
- It sees tables, not fronts nor APIs: the test knows which it opened and called; the APIs behind a call (the bank partner) only show in the trace.
- More runs narrow the list but never make it certain: the trace does. That is why the database is the coverage check, and the answer only when there is no trace.

Each order run places a real order for ada (a backpack, 249 in stock): it is live experimentation, `mise run down && mise run up` resets the data.

## Where it lives

- `src/quality_console/footprint.py`: the pure rules (tests and their steps, colleagues per run, counter difference, narrowing, SQL parsing, picking and reading a Tempo trace, drawing it as a path), unit tested.
- `src/quality_console/footprint_lab.py`: the runs, one thread per experiment, kept in memory for the page to poll (`/devx/retro-footprint/experiments/<id>`).
- `src/newsletter/`: the newsletter service, the one service deployed without its `team`.
- `db/03-console-reader.sql`: the read-only account may read the table counters, nothing else of `performance_schema`.
- `tests/integration/test_console_footprint_mysql.py`: real runs of the API in process and of the test's own SQL against a real MySQL (the pause cut to zero): the hello-then-SQL test narrows to its three tables, the SQL-only test to its two, the health check to none; the redirect test, the in-process console standing for both fronts, ties `customers` to the console's page.
