"""The footprint, run for real on the stack.

Each run reads the table counters of ``performance_schema`` (what the database
side sees, whoever sent the query), lets colleagues query some tables from
their own connection, plays the test's steps (pages of a front, API calls,
SQL queries of its own), then reads the counters again. The counters are also
read around each step, so the tables are tied to the step that moved them.
Five runs, a pause of 20 seconds, five more. The trace of each traced step of
run 1 is read in Tempo, the way anyone would in Grafana, to tell the test's
fronts, APIs and tables apart for sure.

Experiments run in a thread each; the page polls their state.
"""

from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math
import random
import secrets
import threading
import time
from typing import Any

import httpx

from company_db import DatabaseSettings, connect
from quality_console.footprint import (
    COMPANY_DATABASE,
    COMPANY_TABLES,
    DEMO_PAUSE_SECONDS,
    DEMO_RUN_MS,
    PAUSE_SECONDS,
    RUNS,
    RUNS_PER_BATCH,
    WINDOW_QUERY,
    ApiCall,
    Demo,
    Experiment,
    FrontVisit,
    Run,
    SqlQuery,
    Step,
    StepSeen,
    Target,
    colleague_tables,
    demo_run,
    looping_colleague,
    merge_windows,
    narrow,
    new_traceparent,
    pick_trace,
    span_accesses,
    span_count,
    touched,
    trace_api_hits,
    trace_id_of,
    trace_message_hits,
    trace_path,
    traced_accesses,
    window_tables,
)

COUNTERS = (
    "SELECT OBJECT_NAME, COUNT_READ, COUNT_WRITE"
    " FROM performance_schema.table_io_waits_summary_by_table"
    " WHERE OBJECT_SCHEMA = %s"
)
"""Reads and writes per table since the server started, whoever sent them."""

KEPT_EXPERIMENTS = 10
"""Experiments kept in memory for the page to poll."""

AFTER_CALL_MS = 300
"""How long the database is still watched once the call is over."""

POLL_SECONDS = 0.4
"""Pause between two looks at the order workflow, or at Tempo."""

WATCH_SECONDS = 0.04
"""Pause between two reads of the counters during a run, to see the order in
which the tables are touched."""

WORKFLOW_TIMEOUT_SECONDS = 30
"""Budget for the order workflow to end."""

TRACE_TIMEOUT_SECONDS = 90
"""Budget for the trace to become searchable in Tempo."""

TRACE_BY_ID_SECONDS = 20
"""Budget for Tempo to hold the trace of a known id, before searching it."""

WINDOW_SETTLE_SECONDS = 5
"""Pause before reading the run windows: Tempo takes a few seconds to hold a span."""

WINDOW_SLACK_SECONDS = 1
"""Seconds added around each run window: span times and the lab's clock differ."""

TRACE_SETTLE_SECONDS = 1.5
"""Pause between two reads of a trace, to see it no longer grows."""

NS_PER_SECOND = 1_000_000_000
"""Nanoseconds in a second, Tempo's unit."""

CLOCK_SLACK_NS = NS_PER_SECOND
"""Tolerance between the console's clock and the services' clocks."""


@dataclass(frozen=True)
class StepCall:
    """One API call of a run: its trace id, when it ran, how to search it."""

    trace_id: str | None
    started_ns: int
    ended_ns: int
    trace_query: str


class FootprintLab:
    """Runs retro-footprint experiments against the real API and database."""

    def __init__(
        self,
        database: DatabaseSettings,
        api: httpx.Client,
        tempo: httpx.Client | None,
        trace_timeout: float = TRACE_TIMEOUT_SECONDS,
        pause_seconds: float = PAUSE_SECONDS,
        fronts: Mapping[str, httpx.Client] | None = None,
        demo_run_ms: int = DEMO_RUN_MS,
        apis: Mapping[str, httpx.Client] | None = None,
    ) -> None:
        """Wire the lab.

        Args:
            database: The console's read-only account.
            api: Client of the storefront API.
            tempo: Client of Tempo's HTTP API, ``None`` when there is none.
            trace_timeout: Budget for the trace search, in seconds.
            pause_seconds: The pause between the two batches of runs.
            fronts: Client of each front a test may open a page of, by name.
            demo_run_ms: How long a simulated run lasts.
            apis: Client of each other API a test may call, by name; the
                storefront API is ``api``.
        """
        self._database = database
        self._apis = {"storefront": api, **(apis or {})}
        self._tempo = tempo
        self._trace_timeout = trace_timeout
        self._pause_seconds = pause_seconds
        self._fronts = dict(fronts or {})
        self._demo_run_ms = demo_run_ms
        self._experiments: OrderedDict[str, Experiment] = OrderedDict()
        self._lock = threading.Lock()

    def start(self, target: Target) -> Experiment:
        """Start an experiment in the background.

        Args:
            target: What to run.

        Returns:
            The experiment, to poll with ``get``.
        """
        experiment = Experiment(secrets.token_hex(6), target)
        with self._lock:
            self._experiments[experiment.id] = experiment
            while len(self._experiments) > KEPT_EXPERIMENTS:
                self._experiments.popitem(last=False)
        threading.Thread(target=self.run, args=(experiment,), daemon=True).start()
        return experiment

    def running(self) -> Experiment | None:
        """The real experiment still running, if any.

        Two real experiments at once would each count the other's queries as
        a colleague's; a simulated one touches nothing, so it never blocks.
        """
        with self._lock:
            return next(
                (
                    e
                    for e in self._experiments.values()
                    if not e.done and e.target.demo is None
                ),
                None,
            )

    def get(self, experiment_id: str) -> Experiment | None:
        """The experiment of that id, if still kept."""
        with self._lock:
            return self._experiments.get(experiment_id)

    def run(self, experiment: Experiment, rng: random.Random | None = None) -> None:
        """Run the experiment to its end, recording any failure on it.

        Args:
            experiment: What to run, updated as it goes.
            rng: Picks the colleagues' tables; a fresh one by default, seeded
                by the target for a simulated one so the example never changes.
        """
        experiment.trace_timeout = self._trace_timeout
        demo = experiment.target.demo
        seed = experiment.target.key if demo else None
        try:
            if demo:
                self._demo(experiment, demo, rng or random.Random(seed))  # noqa: S311
            else:
                self._run(experiment, rng or random.Random())  # noqa: S311
        except (httpx.HTTPError, OSError, RuntimeError, ValueError) as error:
            experiment.error = f"{type(error).__name__}: {error}"
        finally:
            if experiment.error:
                experiment.phase = "Failed"
            elif experiment.checked:
                experiment.phase = "Done"
            else:
                experiment.phase = f"Done. {experiment.trace_phase}"
            experiment.done = True

    def _run(self, experiment: Experiment, rng: random.Random) -> None:
        """Two batches of runs a pause apart, the traces of run 1 read meanwhile."""
        target = experiment.target
        experiment.looping = looping_colleague(rng)
        experiment.pause_seconds = experiment.pause_left = self._pause_seconds
        if not target.traced_indices:
            experiment.trace_phase = (
                "Nothing traced: the test's own SQL names its tables"
            )
        candidates: list[str] | None = None
        search: threading.Thread | None = None
        for index in range(RUNS):
            if index == RUNS_PER_BATCH:
                self._pause(experiment, self._pause_seconds)
            colleagues = colleague_tables(index, rng, experiment.looping)
            experiment.phase = (
                f"Batch {index // RUNS_PER_BATCH + 1}, run {index + 1} of {RUNS}:"
                f" {target.title} while colleagues query {len(colleagues)} tables"
            )
            run, calls = self._one_run(target, index, colleagues, rng, candidates)
            candidates = run.candidates
            experiment.runs.append(run)
            if index == 0 and target.traced_indices:
                search = threading.Thread(
                    target=self._search_safely, args=(experiment, calls), daemon=True
                )
                search.start()
        if search is not None:
            while search.is_alive():
                experiment.phase = experiment.trace_phase
                search.join(POLL_SECONDS)
            experiment.phase = experiment.trace_phase
        self._read_windows(experiment)

    def _read_windows(self, experiment: Experiment) -> None:
        """Read, run window by run window, the SQL spans Tempo holds, whoever sent them.

        The third witness, matched with the database count in the final
        answer: it says who touched a table. Tempo takes a few seconds to hold
        a span, so it is read once the runs are over, after a pause.
        """
        tempo = self._tempo
        if tempo is None:
            experiment.window_state = "skipped"
            experiment.window_phase = "No Tempo configured: no run window to read"
            return
        experiment.window_state = "active"
        experiment.window_phase = (
            f"Waiting {WINDOW_SETTLE_SECONDS} s for Tempo to hold the last spans"
        )
        experiment.phase = experiment.window_phase
        time.sleep(WINDOW_SETTLE_SECONDS)
        per_run = []
        try:
            for run in experiment.runs:
                experiment.window_phase = (
                    f"Reading the SQL spans of run {run.number}'s window in Tempo"
                )
                experiment.phase = experiment.window_phase
                answer = tempo.get(
                    "/api/search",
                    params={
                        "q": WINDOW_QUERY,
                        "start": run.started_ns // NS_PER_SECOND - WINDOW_SLACK_SECONDS,
                        "end": run.ended_ns // NS_PER_SECOND + WINDOW_SLACK_SECONDS,
                        "limit": 500,
                        "spss": 100,
                    },
                )
                others = {
                    trace_id
                    for other in experiment.runs
                    if other is not run
                    for trace_id in other.trace_ids
                }
                per_run.append(window_tables(answer.raise_for_status().json(), others))
        except (httpx.HTTPError, ValueError) as error:
            experiment.window_state = "failed"
            experiment.window_phase = (
                f"Couldn't read the run windows: {type(error).__name__}"
            )
            return
        experiment.windows = merge_windows(per_run)
        experiment.window_state = "done"
        experiment.window_phase = (
            f"{len(experiment.windows)} tables named by SQL spans in the run windows"
        )

    def _demo(self, experiment: Experiment, demo: Demo, rng: random.Random) -> None:
        """Draw the runs of a simulated test at a run's pace, calling nothing."""
        pause = min(self._pause_seconds, DEMO_PAUSE_SECONDS)
        experiment.looping = list(demo.looping)
        experiment.pause_seconds = experiment.pause_left = pause
        experiment.trace_phase = "Simulated: the traces are written in the example"
        candidates: list[str] | None = None
        for index in range(RUNS):
            if index == RUNS_PER_BATCH:
                self._pause(experiment, pause)
            experiment.phase = (
                f"Demo, run {index + 1} of {RUNS}: drawn, nothing is called"
            )
            time.sleep(self._demo_run_ms / 1000)
            run = demo_run(demo, index, rng, candidates, self._demo_run_ms)
            candidates = run.candidates
            experiment.runs.append(run)
        experiment.traced_steps = {n: s.path for n, s in enumerate(demo.steps)}
        experiment.traced = demo.accesses
        experiment.spans = demo.spans
        experiment.api_hits = demo.api_hits
        experiment.trace_phase = "Simulated traces read"
        experiment.window_state = "skipped"
        experiment.window_phase = "Simulated: no Tempo to read"

    def _pause(self, experiment: Experiment, seconds: float) -> None:
        """Wait between the two batches, the time left shown on the page."""
        deadline = time.monotonic() + seconds
        while (left := deadline - time.monotonic()) > 0:
            experiment.pause_left = left
            experiment.phase = (
                f"Pause: {math.ceil(left)} s before runs {RUNS_PER_BATCH + 1} to"
                f" {RUNS}, so that a colleague busy during the whole first batch"
                " is no longer there"
            )
            time.sleep(min(POLL_SECONDS, left))
        experiment.pause_left = 0

    def _one_run(
        self,
        target: Target,
        index: int,
        colleagues: list[str],
        rng: random.Random,
        candidates: list[str] | None,
    ) -> tuple[Run, list[StepCall]]:
        """Play the test's steps once while colleagues query the database.

        Returns:
            The run, and the trace of each step calling the API.
        """
        before = self._counters()
        started = time.monotonic()
        started_ns = time.time_ns()
        noise = self._colleagues(colleagues, target.window_ms, rng)
        played = [self._step(step) for step in target.steps]
        noise.join()
        elapsed = time.monotonic() - started
        time.sleep(max(target.window_ms / 1000 - elapsed, AFTER_CALL_MS / 1000))
        hits = touched(before, self._counters())
        seen = {hit.table for hit in hits}
        order: list[str] = []
        for step, _ in played:
            order += [table for table in step.tables if table not in order]
        order += sorted(table for table in seen if table not in order)
        kept, dropped = narrow(candidates, hits)
        run = Run(
            index + 1,
            int((time.monotonic() - started) * 1000),
            hits,
            sorted(colleagues),
            kept,
            dropped,
            [table for table in order if table in seen],
            [step for step, _ in played],
            started_ns,
            time.time_ns(),
        )
        calls = [call for _, call in played if call is not None]
        run.trace_ids = [call.trace_id for call in calls if call.trace_id]
        return run, calls

    def _step(self, step: Step) -> tuple[StepSeen, StepCall | None]:
        """Play one step, noting the tables that move meanwhile, in order."""
        before = self._counters()
        order: list[str] = []
        stop = threading.Event()
        watcher = self._watch(before, order, stop)
        started_ns = time.time_ns()
        call: StepCall | None = None
        if isinstance(step, SqlQuery):
            outcome = self._query(step)
        elif isinstance(step, FrontVisit):
            status, trace_id = self._open(step)
            outcome = f"HTTP {status}"
            if step.traced:
                call = StepCall(trace_id, started_ns, time.time_ns(), step.trace_query)
        else:
            status, trace_id = self._call(step)
            outcome = f"HTTP {status}"
            call = StepCall(trace_id, started_ns, time.time_ns(), step.trace_query)
        stop.set()
        watcher.join()
        moved = [hit.table for hit in touched(before, self._counters())]
        tables = [table for table in order if table in moved]
        tables += sorted(table for table in moved if table not in tables)
        return StepSeen(step.kind, step.title, outcome, tables), call

    def _open(self, step: FrontVisit) -> tuple[int, str | None]:
        """Open a page of a front, as the browser would, its trace started here.

        Returns:
            The status of the page, and the id of its trace.
        """
        front = self._fronts.get(step.front)
        if front is None:
            raise RuntimeError(f"No front configured under the name {step.front}")
        response = front.get(step.path, headers={"traceparent": new_traceparent()})
        return response.status_code, trace_id_of(
            response.request.headers.get("traceparent")
        )

    def _query(self, step: SqlQuery) -> str:
        """Run the test's own query, as the test would from its connection."""
        with connect(self._database) as connection, connection.cursor() as cursor:
            cursor.execute(step.statement)
            rows = len(cursor.fetchall())
        return f"{rows} row" if rows == 1 else f"{rows} rows"

    def _watch(
        self,
        before: dict[str, tuple[int, int]],
        order: list[str],
        stop: threading.Event,
    ) -> threading.Thread:
        """Note each table the first time its counters move, in that order.

        The counters are read again and again during the run.
        """

        def watch() -> None:
            with connect(self._database) as connection, connection.cursor() as cursor:
                while not stop.is_set():
                    cursor.execute(COUNTERS, (COMPANY_DATABASE,))
                    now = {
                        str(name): (int(reads), int(writes))
                        for name, reads, writes in cursor.fetchall()
                    }
                    moved = [h.table for h in touched(before, now)]
                    order.extend(t for t in moved if t not in order)
                    stop.wait(WATCH_SECONDS)

        thread = threading.Thread(target=watch, daemon=True)
        thread.start()
        return thread

    def _counters(self) -> dict[str, tuple[int, int]]:
        """Read the table counters of the company database now."""
        with connect(self._database) as connection, connection.cursor() as cursor:
            cursor.execute(COUNTERS, (COMPANY_DATABASE,))
            return {
                str(name): (int(reads), int(writes))
                for name, reads, writes in cursor.fetchall()
            }

    def _colleagues(
        self, tables: list[str], window_ms: int, rng: random.Random
    ) -> threading.Thread:
        """Start colleagues reading tables at random moments of the window."""
        moments = sorted(rng.uniform(0, window_ms * 0.8) / 1000 for _ in tables)

        def query() -> None:
            started = time.monotonic()
            with connect(self._database) as connection, connection.cursor() as cursor:
                for moment, table in zip(moments, tables, strict=True):
                    time.sleep(max(0.0, moment - (time.monotonic() - started)))
                    if table in COMPANY_TABLES:
                        cursor.execute(f"SELECT 1 FROM `{table}` LIMIT 1")  # noqa: S608
                        cursor.fetchall()

        thread = threading.Thread(target=query, daemon=True)
        thread.start()
        return thread

    def _call(self, call: ApiCall) -> tuple[int, str | None]:
        """Call the endpoint, and follow the order workflow when there is one.

        The call starts a trace of its own (``traceparent``); when the
        console's instrumentation replaces the header, the one really sent is
        read back from the request.

        Returns:
            The status of the call, and the id of its trace.
        """
        api = self._apis.get(call.api)
        if api is None:
            raise RuntimeError(f"No API configured under the name {call.api}")
        response = api.request(
            call.method,
            call.path,
            json=call.body,
            headers={"traceparent": new_traceparent()},
        )
        trace_id = trace_id_of(response.request.headers.get("traceparent"))
        if call.follows_workflow and response.status_code == httpx.codes.ACCEPTED:
            self._until(
                lambda: self._workflow_over(response.json()["workflow_id"]),
                WORKFLOW_TIMEOUT_SECONDS,
            )
        return response.status_code, trace_id

    def _workflow_over(self, workflow_id: str) -> bool:
        """Whether the order workflow has ended."""
        storefront = self._apis["storefront"]
        workflow = storefront.get(f"/api/orders/workflows/{workflow_id}").json()
        return workflow.get("status") != "running"

    def _search_safely(self, experiment: Experiment, calls: list[StepCall]) -> None:
        """Read the trace of each traced step of run 1; a failure shows on the page."""
        try:
            for index, call in zip(
                experiment.target.traced_indices, calls, strict=True
            ):
                trace = None
                if call.trace_id:
                    trace = self._read_trace(experiment, call.trace_id)
                if trace is None:
                    trace = self._find_trace(experiment, call)
                if trace is not None:
                    experiment.traced = sorted(
                        set(experiment.traced) | set(traced_accesses(trace)),
                        key=lambda a: (a.service, a.table, a.operation),
                    )
                    experiment.traced_steps[index] = trace_path(trace)
                    experiment.spans += span_accesses(trace, index)
                    experiment.api_hits += trace_api_hits(trace, index)
                    experiment.message_hits += trace_message_hits(trace, index)
            if experiment.checked:
                experiment.trace_phase = "Trace read"
        except (httpx.HTTPError, ValueError) as error:
            experiment.trace_phase = f"Trace search failed: {type(error).__name__}"

    def _read_trace(
        self, experiment: Experiment, trace_id: str
    ) -> dict[str, Any] | None:
        """Ask Tempo for the trace of a known id until it stops growing.

        Tempo answers a trace by its id as soon as its spans arrive, long
        before a search finds it.

        Returns:
            The trace, or ``None`` when Tempo does not hold it in time.
        """
        tempo = self._tempo
        if tempo is None:
            return None
        started = time.monotonic()
        last = -1
        read: dict[str, Any] = {}

        def settled() -> bool:
            nonlocal last
            experiment.trace_waited = time.monotonic() - started
            experiment.trace_phase = (
                f"Reading trace {trace_id[:12]} of run 1 in Tempo"
                f" ({int(experiment.trace_waited)} s, until no new span arrives)"
            )
            answer = tempo.get(f"/api/traces/{trace_id}")
            if answer.status_code != httpx.codes.OK:
                return False
            trace = answer.json()
            count = span_count(trace)
            if count == last:
                experiment.trace_ids.append(trace_id)
                read.update(trace)
                return True
            last = count
            time.sleep(TRACE_SETTLE_SECONDS)
            return False

        return read if self._until(settled, TRACE_BY_ID_SECONDS) else None

    def _find_trace(
        self, experiment: Experiment, call: StepCall
    ) -> dict[str, Any] | None:
        """Search Tempo for the trace of one call of run 1, then read it."""
        tempo = self._tempo
        if tempo is None:
            experiment.trace_phase = "No Tempo configured: no trace to compare with"
            return None
        query: dict[str, str | int] = {
            "q": call.trace_query,
            "start": call.started_ns // NS_PER_SECOND - 1,
            "limit": 50,
        }
        started = time.monotonic()
        picked: list[str] = []

        def found() -> bool:
            experiment.trace_waited = time.monotonic() - started
            experiment.trace_phase = (
                f"Searching the trace of run 1 in Tempo"
                f" ({int(experiment.trace_waited)} s, traces take up to a minute)"
            )
            answer = tempo.get(
                "/api/search", params={**query, "end": time.time_ns() // NS_PER_SECOND}
            )
            try:
                search = answer.raise_for_status().json()
            except httpx.HTTPStatusError, ValueError:
                return False
            trace_id = pick_trace(
                search, call.started_ns - CLOCK_SLACK_NS, call.ended_ns + CLOCK_SLACK_NS
            )
            picked.extend([trace_id] if trace_id else [])
            return bool(picked)

        if not self._until(found, self._trace_timeout):
            experiment.trace_phase = "No trace found in time"
            return None
        experiment.trace_ids.append(picked[0])
        trace = tempo.get(f"/api/traces/{picked[0]}")
        trace.raise_for_status()
        result: dict[str, Any] = trace.json()
        return result

    @staticmethod
    def _until(condition: Callable[[], bool], timeout: float) -> bool:
        """Check a condition until it holds or the budget is spent."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return True
            time.sleep(POLL_SECONDS)
        return False
