"""retro-footprint: which fronts, APIs and tables does one test touch?

A test is a few steps: pages of a front opened, API calls, SQL queries of its
own. The "run
it N times and intersect" method, on the real stack. Each run plays the steps
for real while colleagues query the same database, and the database side
(``performance_schema`` counters) says which tables were read or written
during the run, without knowing by whom. A table of the test is seen in every
run; a colleague's table only in some. Keeping the tables seen in every run so
far narrows the candidates run after run.

The runs come in two batches of five, 20 seconds apart. Colleagues are loud at
first and quieter later (``COLLEAGUE_TABLES``), and one of them loops their
own test during the whole first batch (``LOOPING_TABLES``): their tables are
seen in all five runs, so one batch keeps them. After the pause the loop is
over, and the second batch rules them out.

The exact answer comes from a trace: every span carries the trace id of the
request that sent it, so one trace found in Tempo names the APIs the call went
through and the tables each one touched, in order, whatever colleagues did.
The test's own SQL names its tables itself. This module holds the pure rules;
the calls live in ``footprint_lab``.
"""

from collections import Counter
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
import random
import re
import secrets
from typing import Any

COMPANY_TABLES = (
    "currencies",
    "countries",
    "customers",
    "customer_addresses",
    "customer_preferences",
    "bank_accounts",
    "bank_transactions",
    "product_categories",
    "suppliers",
    "products",
    "warehouses",
    "stock_levels",
    "payment_methods",
    "orders",
    "order_items",
    "invoices",
    "payments",
    "carriers",
    "shipments",
    "returns",
    "promotions",
    "coupons",
    "reviews",
    "departments",
    "employees",
    "support_tickets",
    "ticket_messages",
    "newsletters",
    "newsletter_subscriptions",
    "audit_logs",
)
"""The 30 tables of the company database, in the order of ``db/01-schema.sql``."""

COMPANY_DATABASE = "mycompany"
"""The database watched."""

RUNS_PER_BATCH = 5
"""How many times the test is run in a row."""

BATCHES = 2
"""How many batches of runs, a pause between two."""

RUNS = RUNS_PER_BATCH * BATCHES
"""How many times the test is run in all."""

PAUSE_SECONDS = 20
"""The pause between two batches."""

COLLEAGUE_TABLES = ((16, 9, 5, 2, 1), (6, 3, 2, 1, 1))
"""How many tables colleagues query during each run of each batch: many
first, then fewer."""

LOOPING_TABLES = 2
"""Tables of the colleague whose test loops during the whole first batch."""

STATEMENT_TABLE = re.compile(
    r"\b(DELETE\s+FROM|FROM|JOIN|INTO|UPDATE)\s+`?(\w+)`?", re.IGNORECASE
)
"""A table named by a SQL statement, after the keyword that introduces it."""

TRACEPARENT_PARTS = 4
"""Version, trace id, parent span id and flags."""

TRACE_ID_LENGTH = 32
"""Hexadecimal digits of a trace id."""

WRITE_KEYWORDS = ("DELETE FROM", "INTO", "UPDATE")
"""Keywords naming a table the statement writes; the others name tables read."""


TRACE_QUERY = '{{ resource.service.name = "{service}" && name = "{name}" }}'
"""TraceQL finding the traces holding one route of an API."""

WINDOW_QUERY = (
    '{ span.db.system = "mysql" && span.db.name = "mycompany" }'
    " | select(span.db.statement, resource.service.name)"
)
"""TraceQL finding every SQL span on the company database, whoever sent it:
read run window by run window, the third witness."""

FRONT_TRACE_QUERY = '{{ resource.service.name = "{service}" && name = "{name}" }}'
"""TraceQL finding the traces of one page of a front sending traces."""

THE_TEST = "the test"
"""Who runs a step: the test itself, as the path names it."""

TEAM_ATTRIBUTE = "team"
"""Resource attribute a team adds to its service's telemetry to own it: the
observability platform files every span of the service under that team. A
service deployed without it sends spans nobody owns."""

OWNED = "owned"
"""Ownership of a table some span of a declared team names."""

ORPHAN = "orphan"
"""Ownership of a table the test touched that no declared team's span names."""

TEST_OWN = "test"
"""Ownership of a table only the test's own SQL names: no service to own it."""

SAME_QUERY = "same-query"
"""Optimization hint: one service runs the same query again during one step."""

SEVERAL_SERVICES = "several-services"
"""Optimization hint: several services read the same table, one after the other."""

SEVERAL_QUERIES = "several-queries"
"""Optimization hint: one service reads a table again, in another query or step."""

SAME_CALL = "same-call"
"""Optimization hint: one caller calls the same endpoint again during one step."""

SEVERAL_CALLERS = "several-callers"
"""Optimization hint: several callers call the same endpoint."""

CALLED_AGAIN = "called-again"
"""Optimization hint: one caller calls the same endpoint again in a later step."""

PUBLISHED_AGAIN = "published-again"
"""Optimization hint: one service publishes to the same destination again."""

CONSUMED_AGAIN = "consumed-again"
"""Optimization hint: one service consumes from the same destination again."""

MESSAGE_KINDS = {
    "SPAN_KIND_PRODUCER": "publish",
    4: "publish",
    "SPAN_KIND_CONSUMER": "consume",
    5: "consume",
}
"""Span kinds of a message: a producer publishes it, a consumer takes it."""


ENTRY_KINDS = {
    "SPAN_KIND_SERVER": "api",
    2: "api",
    "SPAN_KIND_CONSUMER": "event",
    5: "event",
}
"""Span kinds where a service starts working, and how the path draws them: an
API answering a request, or a worker taking a message."""


@dataclass(frozen=True)
class ApiCall:
    """A step of the test calling the storefront API.

    Attributes:
        title: The call, as the page shows it.
        method: HTTP method.
        path: Path on the storefront API.
        body: JSON body, if any.
        follows_workflow: Whether the step lasts until the order workflow ends.
        api: Which API: a key of the APIs the lab is given.
        service: The service answering it, as its spans name it.
    """

    title: str
    method: str
    path: str
    body: Mapping[str, object] | None = None
    follows_workflow: bool = False
    api: str = "storefront"
    service: str = "hello-api"
    kind: str = "api"

    @property
    def trace_query(self) -> str:
        """TraceQL query finding the call's trace in Tempo."""
        route = self.path.split("?", 1)[0]
        return TRACE_QUERY.format(service=self.service, name=f"{self.method} {route}")


@dataclass(frozen=True)
class SqlQuery:
    """A step of the test reading the company database itself.

    Attributes:
        title: What the query checks, as the page shows it.
        statement: The query, fixed: it holds no input.
    """

    title: str
    statement: str
    kind: str = "sql"

    @property
    def accesses(self) -> list[TracedAccess]:
        """The tables the query names: the test's code says it, no trace needed."""
        return [
            TracedAccess(THE_TEST, table, operation)
            for table, operation in tables_in_statement(self.statement)
        ]


@dataclass(frozen=True)
class FrontVisit:
    """A step of the test opening a page of a front, as a browser would.

    Attributes:
        title: The page, as the page shows it.
        front: Which front: a key of the fronts the lab is given.
        path: Path of the page on that front.
        redirect: Whether the previous front sent the user here.
        traced: Whether the front is a service sending traces; a static front
            (nginx) sends none, so none is waited for.
    """

    title: str
    front: str
    path: str
    redirect: bool = False
    traced: bool = False
    kind: str = "front"

    @property
    def trace_query(self) -> str:
        """TraceQL query finding the page's trace in Tempo."""
        route = self.path.split("?", 1)[0]
        return FRONT_TRACE_QUERY.format(service=self.front, name=f"GET {route}")


Step = ApiCall | SqlQuery | FrontVisit
"""One step of a test."""

SKIPPED = "skipped"
"""Outcome of a step a run did not play: a branch the test takes only sometimes."""

DEMO_SERVICE = "hello-api"
"""The service a simulated API call answers from."""

DEMO_TEAM = "demo-squad"
"""The team every simulated service declares."""

DEMO_RUN_MS = 2000
"""How long a simulated run lasts."""

DEMO_PAUSE_SECONDS = 4
"""The pause between the two batches of a simulated experiment."""


@dataclass(frozen=True)
class DemoStep:
    """One step of a simulated test, and what its trace says.

    Attributes:
        step: The page or the call, as a real test would hold it.
        behind: The APIs the step goes through, as ``(service, route)``.
        tables: The tables it touches, as ``(table, operation)``.
        presence: Share of the runs the step is played in; below 1, a branch
            or a cache the test only sometimes goes through.
        untraced: Tables the step writes through something sending no trace
            (a trigger, an old service): the database counts them, no trace
            names them.
    """

    step: FrontVisit | ApiCall
    behind: tuple[tuple[str, str], ...] = ()
    tables: tuple[tuple[str, str], ...] = ()
    presence: float = 1.0
    untraced: tuple[str, ...] = ()

    @property
    def service(self) -> str:
        """Who touches the step's tables: the front, or the storefront API."""
        return self.step.front if isinstance(self.step, FrontVisit) else DEMO_SERVICE

    @property
    def path(self) -> list[PathNode]:
        """The step as its trace draws it: the call, the APIs behind, the tables."""
        own = [] if isinstance(self.step, FrontVisit) else [self.step.title]
        nodes = [PathNode("api", title, self.service) for title in own]
        nodes += [PathNode("api", route, service) for service, route in self.behind]
        nodes += [
            PathNode("table", table, self.service, operation)
            for table, operation in self.tables
        ]
        return nodes


@dataclass(frozen=True)
class Demo:
    """A simulated experiment: nothing is called, the runs are drawn.

    Attributes:
        steps: The test's steps and what each one touches.
        noise: How many tables colleagues query during each run.
        looping: Tables of a colleague's job, queried in each of the first
            ``looping_runs`` runs.
        looping_runs: How many runs the job lasts.
    """

    steps: tuple[DemoStep, ...]
    noise: tuple[int, ...]
    looping: tuple[str, ...] = ()
    looping_runs: int = RUNS_PER_BATCH

    @property
    def api_hits(self) -> list[ApiHit]:
        """Every endpoint each simulated step calls: its own, then the ones behind."""
        hits = []
        for index, step in enumerate(self.steps):
            if isinstance(step.step, ApiCall):
                hits.append(ApiHit(index, DEMO_SERVICE, step.step.title, THE_TEST))
            hits += [
                ApiHit(index, service, route, step.service, DEMO_TEAM)
                for service, route in step.behind
            ]
        return hits

    @property
    def spans(self) -> list[SpanAccess]:
        """Every table each simulated step reads or writes, one span each."""
        return [
            SpanAccess(index, step.service, table, operation)
            for index, step in enumerate(self.steps)
            for table, operation in step.tables
        ]

    @property
    def accesses(self) -> list[TracedAccess]:
        """Every table the simulated traces name, by service."""
        found = {
            TracedAccess(step.service, table, operation, DEMO_TEAM)
            for step in self.steps
            for table, operation in step.tables
        }
        return sorted(found, key=lambda a: (a.service, a.table, a.operation))


@dataclass(frozen=True)
class Target:
    """What is run: a test, its steps played with the same input each time.

    Attributes:
        key: Identifier in the page's URL.
        title: The test, as the page shows it.
        detail: What the test does, in one sentence.
        steps: Its API calls and SQL queries, in order.
        window_ms: How long colleagues may query during one run.
        demo: The simulated runs, for an example that calls nothing.
    """

    key: str
    title: str
    detail: str
    steps: tuple[Step, ...]
    window_ms: int
    demo: Demo | None = None

    @property
    def traced_indices(self) -> list[int]:
        """Index of each step leaving a trace: API calls, pages of a traced front."""
        return [
            index
            for index, step in enumerate(self.steps)
            if isinstance(step, ApiCall)
            or (isinstance(step, FrontVisit) and step.traced)
        ]

    @property
    def sql_accesses(self) -> list[TracedAccess]:
        """The tables the test's own SQL names."""
        return [
            access
            for step in self.steps
            if isinstance(step, SqlQuery)
            for access in step.accesses
        ]


HELLO = ApiCall("GET /api/hello?username=ada", "GET", "/api/hello?username=ada")
"""Greets ada: her name in the database, her balance from the bank partner."""

NEWSLETTERS = ApiCall(
    "GET /newsletters/ada",
    "GET",
    "/newsletters/ada",
    api="newsletter",
    service="newsletter-service",
)
"""ada's newsletters, from a service deployed without its team declared."""

STOREFRONT = FrontVisit("Storefront: the welcome page", "storefront", "/")
"""The storefront's page, served by nginx: a static front, no trace."""

STOCK_SQL = (
    "SELECT p.sku, s.quantity FROM products p"
    " JOIN stock_levels s ON s.product_id = p.id WHERE p.sku = 'GN-0012'"
)
"""A test checking the backpack's stock in the database itself."""

PROFILE_SQL = (
    "SELECT a.city, p.language FROM customers c"
    " JOIN customer_addresses a ON a.customer_id = c.id"
    " JOIN customer_preferences p ON p.customer_id = c.id"
    " WHERE c.username = 'ada'"
)
"""A test checking ada's address and preferences in the database itself."""


def demo_target(key: str, title: str, detail: str, demo: Demo) -> Target:
    """A target whose runs are drawn, not played: an example for the page."""
    return Target(
        key, title, detail, tuple(s.step for s in demo.steps), DEMO_RUN_MS, demo
    )


def _page(title: str, front: str, path: str, redirect: bool = False) -> FrontVisit:
    """A page of a simulated front, traced like the Quality Console."""
    return FrontVisit(title, front, path, redirect=redirect, traced=True)


def _call(route: str) -> ApiCall:
    """A simulated call to the storefront API, ``"POST /api/orders"``."""
    method, path = route.split(" ", 1)
    return ApiCall(route, method, path)


CROWDED = Demo(
    (
        DemoStep(
            _page(STOREFRONT.title, "storefront", "/"),
            tables=(("promotions", "read"), ("product_categories", "read")),
        ),
        DemoStep(
            _page("Storefront: the sign-up page", "storefront", "/#account"),
            tables=(("countries", "read"),),
            presence=0.8,
        ),
        DemoStep(
            _call("POST /api/identity/signup"),
            behind=(("identity", "POST /dbconnections/signup"),),
            tables=(
                ("customers", "write"),
                ("customer_preferences", "write"),
                ("newsletter_subscriptions", "write"),
                ("audit_logs", "write"),
            ),
        ),
        DemoStep(
            _call("GET /api/products?category=bags"),
            tables=(
                ("products", "read"),
                ("product_categories", "read"),
                ("stock_levels", "read"),
                ("reviews", "read"),
                ("suppliers", "read"),
            ),
        ),
        DemoStep(
            _page("Storefront: the checkout page", "storefront", "/#checkout"),
            tables=(("coupons", "read"),),
        ),
        DemoStep(
            _call("POST /api/coupons/check"),
            tables=(("coupons", "read"), ("promotions", "read")),
            presence=0.6,
        ),
        DemoStep(
            _call("POST /api/orders"),
            behind=(("order-worker", "order.created"),),
            tables=(
                ("orders", "write"),
                ("order_items", "write"),
                ("stock_levels", "write"),
                ("warehouses", "read"),
                ("invoices", "write"),
                ("audit_logs", "write"),
            ),
        ),
        DemoStep(
            _call("POST /api/payments"),
            behind=(("bank-partner", "POST /payments"),),
            tables=(
                ("payments", "write"),
                ("payment_methods", "read"),
                ("bank_accounts", "read"),
                ("bank_transactions", "write"),
                ("currencies", "read"),
            ),
        ),
        DemoStep(
            _page("Back office: the order", "quality-console", "/orders", True),
            tables=(("orders", "read"),),
        ),
        DemoStep(
            _call("GET /api/shipments"),
            behind=(("carrier-hub", "GET /tracking"),),
            tables=(("shipments", "read"), ("carriers", "read")),
            presence=0.7,
        ),
        DemoStep(
            _page("Help center: a new ticket", "help-center", "/tickets/new", True),
            tables=(("support_tickets", "write"), ("departments", "read")),
            presence=0.5,
        ),
        DemoStep(
            _call("POST /api/returns"),
            tables=(
                ("returns", "write"),
                ("ticket_messages", "write"),
                ("employees", "read"),
            ),
            presence=0.4,
        ),
    ),
    noise=(8, 6, 5, 4, 3, 4, 3, 2, 2, 1),
    looping=("newsletters", "customer_addresses"),
)
"""A long journey through five fronts and a dozen APIs: too much to show at once."""

AMBIGUOUS = Demo(
    (
        DemoStep(
            _page(STOREFRONT.title, "storefront", "/"),
            tables=(("promotions", "read"),),
        ),
        DemoStep(
            _call("GET /api/hello?username=ada"),
            behind=(("bank-partner", "GET /accounts/{username}"),),
            tables=(("customers", "read"), ("bank_accounts", "read")),
        ),
        DemoStep(
            _call("GET /api/recommendations?username=ada"),
            tables=(
                ("products", "read"),
                ("reviews", "read"),
                ("order_items", "read"),
            ),
            presence=0.75,
        ),
        DemoStep(
            _call("POST /api/newsletter"),
            tables=(("newsletter_subscriptions", "write"),),
        ),
    ),
    noise=(6, 6, 5, 5, 5, 5, 5, 2, 1, 1),
    looping=(
        "customers",
        "invoices",
        "order_items",
        "orders",
        "payments",
        "products",
        "shipments",
        "stock_levels",
    ),
    looping_runs=7,
)
"""A short test sharing its minute with a nightly job that reads eight tables,
three of them the test's own, for seven runs: until run 8, the test's tables
and the job's look alike."""

WIDE_FRONTS = (
    ("Intranet: home", "intranet", "/"),
    ("HR portal: my leave", "hr-portal", "/leave"),
    ("Wiki: the release page", "wiki", "/releases"),
    ("Ticketing: my queue", "ticketing", "/queue"),
    ("CRM: the customer", "crm", "/customers/ada"),
    ("Billing: the invoices", "billing", "/invoices"),
    ("Catalog admin: the products", "catalog-admin", "/products"),
    ("Status page", "status-page", "/"),
    ("Reporting: the dashboards", "reporting", "/dashboards"),
    ("Back office: the export page", "back-office", "/exports"),
)
"""Ten fronts the wide test goes through, each sending the user to the next."""

WIDE = Demo(
    (
        *(
            DemoStep(_page(title, front, path, redirect=index > 0))
            for index, (title, front, path) in enumerate(WIDE_FRONTS)
        ),
        DemoStep(
            _call("GET /api/exports/everything"),
            behind=(("reporting", "GET /reports/full"),),
            tables=tuple((t, "read") for t in COMPANY_TABLES if t != "audit_logs"),
            untraced=("audit_logs",),
        ),
    ),
    noise=(5, 4, 3, 2, 1, 2, 1, 1, 0, 0),
)
"""Ten fronts in a row, then one export reading 29 tables, while a database
trigger writes ``audit_logs`` on every export, a write no trace names."""

DEMO_TARGETS = {
    "demo-crowded": demo_target(
        "demo-crowded",
        "Demo, too many items: sign up, order, pay, follow, return",
        "Simulated, nothing is called: 12 steps through 5 fronts, a dozen APIs and"
        " almost every table, some steps played only in some runs.",
        CROWDED,
    ),
    "demo-ambiguous": demo_target(
        "demo-ambiguous",
        "Demo, hard to tell for 7 runs: a nightly job shares the minute",
        "Simulated, nothing is called: a 4-step test while a job reads 8 tables"
        " during the first 7 runs, 3 of them the test's own.",
        AMBIGUOUS,
    ),
    "demo-wide": demo_target(
        "demo-wide",
        "Demo, many of a kind: 10 fronts, then one API reading 29 tables",
        "Simulated, nothing is called: the user is sent through 10 fronts, then"
        " one export reads 29 tables, and a trigger nobody traces writes the 30th.",
        WIDE,
    ),
}
"""Examples drawn from a fixed seed, to see how the page holds a crowd."""

TARGETS = {
    "api-only": Target(
        "api-only",
        "API only: GET /api/health",
        "A health check: the API pings Redis and reads no table.",
        (ApiCall("GET /api/health", "GET", "/api/health"),),
        window_ms=1000,
    ),
    "sql-only": Target(
        "sql-only",
        "SQL only: the backpack's stock, read by the test itself",
        "No API: the test queries products and stock_levels from its own connection.",
        (SqlQuery("SQL: the backpack's stock", STOCK_SQL),),
        window_ms=1000,
    ),
    "hello": Target(
        "hello",
        "API using tables: GET /api/hello?username=ada",
        "Greets ada: her name in the database, her balance from the bank partner,"
        " another API reading its own table.",
        (HELLO,),
        window_ms=1000,
    ),
    "place-order": Target(
        "place-order",
        "API using tables: POST /api/orders, until paid",
        "ada orders a backpack (249 in stock): the endpoint, then the worker's"
        " three steps through RabbitMQ.",
        (
            ApiCall(
                "POST /api/orders, until paid",
                "POST",
                "/api/orders",
                {"username": "ada", "sku": "GN-0012", "quantity": 1},
                follows_workflow=True,
            ),
        ),
        window_ms=4500,
    ),
    "front-api": Target(
        "front-api",
        "Front, then API using tables: the storefront greets ada",
        "The test opens the storefront, then the page calls the API, which reads"
        " its tables and asks the bank partner.",
        (STOREFRONT, HELLO),
        window_ms=1000,
    ),
    "front-api-redirect": Target(
        "front-api-redirect",
        "Front, API, then a redirect to another front: storefront, then the"
        " Quality Console",
        "The test opens the storefront, greets ada through the API, then is sent"
        " to the Quality Console, a front reading the customers table itself.",
        (
            STOREFRONT,
            HELLO,
            FrontVisit(
                "Quality Console: the customers table",
                "quality-console",
                "/databases/mycompany/tables/customers",
                redirect=True,
                traced=True,
            ),
        ),
        window_ms=1500,
    ),
    "orphan-tables": Target(
        "orphan-tables",
        "Ownership: GET /api/hello, then a service whose team forgot to declare it",
        "The test greets ada through the API, whose team declared it, then asks"
        " the newsletter service, deployed without its team: its tables reach"
        " Grafana owned by nobody.",
        (HELLO, NEWSLETTERS),
        window_ms=1500,
    ),
    "repeat-hello": Target(
        "repeat-hello",
        "Resource optimization: GET /api/hello, then the same greeting again",
        "The test greets ada twice in a row: every endpoint and every table"
        " behind the call is used twice, where one call would do.",
        (HELLO, HELLO),
        window_ms=1500,
    ),
    "hello-then-sql": Target(
        "hello-then-sql",
        "API using tables, then SQL: GET /api/hello, then ada's profile",
        "The test greets ada through the API, then checks her address and"
        " preferences in the database itself.",
        (HELLO, SqlQuery("SQL: ada's address and preferences", PROFILE_SQL)),
        window_ms=1500,
    ),
    **DEMO_TARGETS,
}
"""What the page can run: API only, SQL only, API using tables, then both, the
same seen from a front, a service whose team forgot to declare it, the same
call twice, and the simulated examples."""


@dataclass(frozen=True)
class TableHits:
    """Reads and writes the database counted on one table during a run."""

    table: str
    reads: int
    writes: int


@dataclass(frozen=True)
class TracedAccess:
    """One SQL statement of the trace: which service ran it, on which table.

    Attributes:
        service: The service whose span it is.
        table: The table.
        operation: ``read`` or ``write``.
        team: The team the service declares in its telemetry, empty when none.
    """

    service: str
    table: str
    operation: str
    team: str = ""


@dataclass(frozen=True)
class SpanAccess:
    """One SQL span on a company table, kept with the step it ran during.

    Unlike ``TracedAccess``, nothing is merged: two spans reading the same
    table stay two, which is what the optimization hints count.

    Attributes:
        step: Index of the test's step the span ran during.
        service: The service whose span it is, or ``the test`` for its own SQL.
        table: The table.
        operation: ``read`` or ``write``.
        statement: The SQL statement, empty when unknown (simulated).
        team: The team the service declares in its telemetry, empty when none.
    """

    step: int
    service: str
    table: str
    operation: str
    statement: str = ""
    team: str = ""


@dataclass(frozen=True)
class Hint:
    """A table, an endpoint or a message destination used more than once.

    Each hint also says how doing it once could do.

    Attributes:
        item: The table, or the endpoint's route.
        kind: ``same-query``, ``several-services`` or ``several-queries`` for
            a table; ``same-call``, ``several-callers`` or ``called-again`` for
            an endpoint; ``published-again`` or ``consumed-again`` for a message
            destination.
        reads: How many times it was read or called during the test.
        services: Who read or called it, in the order they first did.
        steps: The steps it was used during, in order.
        advice: What to change, in one sentence.
        by: Each use in order, as ``(step, service)``.
        of: ``table``, ``api`` or ``broker``.
        owner: For an endpoint, the service answering it; for a destination,
            the one publishing or consuming.
        teams: The teams the services using it declare, empty when none does.
    """

    item: str
    kind: str
    reads: int
    services: list[str]
    steps: list[int]
    advice: str
    by: list[tuple[int, str]] = field(default_factory=list)
    of: str = "table"
    owner: str = ""
    teams: list[str] = field(default_factory=list)

    @property
    def saved(self) -> int:
        """The reads or calls doing it once would spare."""
        return self.reads - 1


@dataclass(frozen=True)
class ApiHit:
    """One endpoint answering during the test, and who called it.

    Attributes:
        step: Index of the test's step the call ran during.
        service: The service answering.
        route: The endpoint, as its server span names it.
        caller: The service whose call it answers, or ``the test``.
        team: The team the answering service declares, empty when none.
    """

    step: int
    service: str
    route: str
    caller: str
    team: str = ""


@dataclass(frozen=True)
class MessageHit:
    """One message a service published or consumed during the test.

    Attributes:
        step: Index of the test's step the message went by during.
        service: The service publishing or consuming it.
        destination: The queue, topic or exchange; the span's name when the
            span names none.
        operation: ``publish`` or ``consume``.
        team: The team the service declares, empty when none.
    """

    step: int
    service: str
    destination: str
    operation: str
    team: str = ""


def _teams(teams: Iterable[str]) -> list[str]:
    """The declared teams, each once, sorted."""
    return sorted({team for team in teams if team})


def api_hints(hits: list[ApiHit]) -> list[Hint]:
    """Find the endpoints a test calls more than once, the strongest case first.

    The same call again during one step is a loop or a missing cache; several
    callers of one endpoint could share its answer; one caller calling it again
    in a later step could keep the first answer.

    Args:
        hits: Every endpoint answering during the test, in the order they did.

    Returns:
        One hint per endpoint called more than once, the most calls first.
    """
    hints = []
    for service, route in dict.fromkeys((h.service, h.route) for h in hits):
        calls = [h for h in hits if (h.service, h.route) == (service, route)]
        if len(calls) <= 1:
            continue
        callers = list(dict.fromkeys(h.caller for h in calls))
        steps = list(dict.fromkeys(h.step for h in calls))
        counted = Counter((h.caller, h.step) for h in calls)
        repeated = sorted(key for key, count in counted.items() if count > 1)
        if repeated:
            kind = SAME_CALL
            advice = (
                f"{repeated[0][0]} calls {route} again during one step: call it"
                " once, or ask for everything in one call."
            )
        elif len(callers) > 1:
            kind = SEVERAL_CALLERS
            advice = (
                f"{', '.join(callers)} each call {route}: the first could pass"
                " the answer along, so one call would do."
            )
        else:
            kind = CALLED_AGAIN
            advice = (
                f"{callers[0]} calls {route} again in a later step: keeping the"
                " first answer (or caching it) would spare the call."
            )
        by = [(h.step, h.caller) for h in calls]
        teams = _teams(h.team for h in calls)
        hints.append(
            Hint(
                route,
                kind,
                len(calls),
                callers,
                steps,
                advice,
                by,
                "api",
                service,
                teams,
            )
        )
    return sorted(hints, key=lambda hint: -hint.reads)


def message_hints(hits: list[MessageHit]) -> list[Hint]:
    """Find the destinations one service publishes to or consumes from more than once.

    Several messages to the same destination for one test could be one
    message carrying everything; several taken from it, one batch.

    Args:
        hits: Every message published or consumed during the test, in order.

    Returns:
        One hint per service, direction and destination used more than once,
        the most messages first.
    """
    hints = []
    keys = dict.fromkeys((h.service, h.operation, h.destination) for h in hits)
    for service, operation, destination in keys:
        sent = [
            h
            for h in hits
            if (h.service, h.operation, h.destination)
            == (service, operation, destination)
        ]
        if len(sent) <= 1:
            continue
        if operation == "publish":
            kind = PUBLISHED_AGAIN
            advice = (
                f"{service} publishes {len(sent)} messages to {destination}: one"
                " message carrying everything would do."
            )
        else:
            kind = CONSUMED_AGAIN
            advice = (
                f"{service} consumes {len(sent)} messages from {destination}: one"
                " message, or a consumer taking them as a batch, would do."
            )
        steps = list(dict.fromkeys(h.step for h in sent))
        hints.append(
            Hint(
                destination,
                kind,
                len(sent),
                [service],
                steps,
                advice,
                [(h.step, service) for h in sent],
                "broker",
                service,
                _teams(h.team for h in sent),
            )
        )
    return sorted(hints, key=lambda hint: -hint.reads)


def optimization_hints(spans: list[SpanAccess]) -> list[Hint]:
    """Find the tables a test reads more than once, the strongest case first.

    A service running the same query again during one step is the clearest
    waste (a loop of queries, a missing cache); several services reading the
    same table means the first could pass what it read along; one service
    reading it with several queries could fetch it all at once. Writes are
    left out: writing twice may be what the test is about.

    Args:
        spans: Every SQL span of the test, in the order they ran.

    Returns:
        One hint per table read more than once, the most reads first.
    """
    hints = []
    for table in COMPANY_TABLES:
        reads = [s for s in spans if s.table == table and s.operation == "read"]
        if len(reads) <= 1:
            continue
        services = list(dict.fromkeys(s.service for s in reads))
        steps = list(dict.fromkeys(s.step for s in reads))
        counted = Counter(
            (s.service, s.step, s.statement) for s in reads if s.statement
        )
        repeated = sorted(key for key, count in counted.items() if count > 1)
        if repeated:
            service = repeated[0][0]
            kind = SAME_QUERY
            advice = (
                f"{service} runs the same query on {table} again during one step:"
                " run it once, or fetch every row in one query (an N+1 loop)."
            )
        elif len(services) > 1:
            kind = SEVERAL_SERVICES
            advice = (
                f"{', '.join(services)} each read {table}: the first one could"
                " pass what it read along with its call, so one read would do."
            )
        else:
            kind = SEVERAL_QUERIES
            advice = (
                f"{services[0]} reads {table} {len(reads)} times: one query, or"
                " keeping what the first one returned, would do."
            )
        by = [(s.step, s.service) for s in reads]
        teams = _teams(s.team for s in reads)
        hints.append(
            Hint(table, kind, len(reads), services, steps, advice, by, teams=teams)
        )
    return sorted(hints, key=lambda hint: -hint.reads)


_VERBS = {"publish": "published", "consume": "consumed"}
"""How an ownership entry tells a destination's use."""


def _owned(
    of: str, item: str, hits: list[ApiHit] | list[MessageHit], details: list[str]
) -> dict[str, Any]:
    """One API or destination, owned by the teams its services declare."""
    teams = _teams(hit.team for hit in hits)
    why = ", ".join(details)
    return {
        "of": of,
        "item": item,
        "status": OWNED if teams else ORPHAN,
        "teams": teams,
        "why": why if teams else f"{why}, no team declared",
    }


@dataclass(frozen=True)
class PathNode:
    """One stop of the path: an API, a worker, a query of the test, a table.

    Attributes:
        kind: ``api``, ``event``, ``sql`` or ``table``.
        label: The route, the query or the table.
        service: Who is there: the service, or ``the test``.
        operation: For a table, ``read`` or ``write``.
    """

    kind: str
    label: str
    service: str = ""
    operation: str = ""


@dataclass(frozen=True)
class StepSeen:
    """What one step of a run did, and the tables that moved meanwhile.

    Attributes:
        kind: ``api`` or ``sql``.
        title: The step.
        outcome: ``HTTP 200`` or ``1 row``.
        tables: The tables that moved during the step, in the order they did.
    """

    kind: str
    title: str
    outcome: str
    tables: list[str]


@dataclass
class Run:
    """One run: what the database saw, and the candidates left after it."""

    number: int
    duration_ms: int
    hits: list[TableHits]
    colleagues: list[str]
    candidates: list[str]
    dropped: list[str]
    order: list[str] = field(default_factory=list)
    steps: list[StepSeen] = field(default_factory=list)
    started_ns: int = 0
    ended_ns: int = 0
    trace_ids: list[str] = field(default_factory=list)

    @property
    def batch(self) -> int:
        """Which batch the run belongs to, from 1."""
        return (self.number - 1) // RUNS_PER_BATCH + 1


@dataclass(frozen=True)
class WindowTable:
    """A table the SQL spans named during the run windows, and who sent them.

    Attributes:
        table: The table.
        runs: In how many run windows a SQL span named it.
        services: The services the spans came from, the root of their trace.
    """

    table: str
    runs: int
    services: list[str]


def window_tables(
    search: Mapping[str, Any], others: Collection[str] = ()
) -> dict[str, set[str]]:
    """Read one run window's search in Tempo: the tables, each with its services.

    Args:
        search: The JSON of ``/api/search`` with ``WINDOW_QUERY``, whose spans
            carry ``db.statement`` and the ``service.name`` that sent them; the
            root service of the trace stands in when a span has none.
        others: The traces the test's calls started in the other runs. Runs
            follow each other closer than the window's slack, so a window
            also catches the neighbouring runs' calls: those traces are left
            out, and each window holds its own run of the test, plus whoever
            else queried meanwhile.

    Returns:
        By table, the services whose traces held a SQL span on it.
    """
    seen: dict[str, set[str]] = {}
    for trace in search.get("traces", []):
        if trace.get("traceID") in others:
            continue
        root = trace.get("rootServiceName") or "unknown"
        for span_set in trace.get("spanSets", []) or [trace.get("spanSet", {})]:
            for span in span_set.get("spans", []):
                attributes = span.get("attributes", [])
                statement = _attribute(attributes, "db.statement")
                service = _attribute(attributes, "service.name") or root
                for table, _ in tables_in_statement(statement or ""):
                    seen.setdefault(table, set()).add(service)
    return seen


def merge_windows(per_run: list[dict[str, set[str]]]) -> list[WindowTable]:
    """Count in how many run windows each table was named, and by whom."""
    runs: dict[str, int] = {}
    services: dict[str, set[str]] = {}
    for seen in per_run:
        for table, senders in seen.items():
            runs[table] = runs.get(table, 0) + 1
            services.setdefault(table, set()).update(senders)
    return sorted(
        (WindowTable(t, runs[t], sorted(services[t])) for t in runs),
        key=lambda w: (-w.runs, COMPANY_TABLES.index(w.table)),
    )


WINDOW_SPOKE = frozenset({"done", "failed", "skipped"})
"""States of the run windows' reading once it is over, whatever came of it."""

LAB_SERVICE = "quality-console"
"""The service the lab's own SQL comes from: the console runs the test's queries."""


RUN_OVERHEAD_SECONDS = 0.5
"""Time a run takes beyond its window, guessed before the first one ends."""

RUNS_PART = 0.96
"""Part of the progress bar the runs and the pause fill; the traces the rest."""


@dataclass
class Experiment:
    """The runs of one target, then the traces that check them."""

    id: str
    target: Target
    runs: list[Run] = field(default_factory=list)
    phase: str = "Starting"
    trace_phase: str = "Searching the trace of run 1 in Tempo"
    trace_ids: list[str] = field(default_factory=list)
    traced: list[TracedAccess] = field(default_factory=list)
    traced_steps: dict[int, list[PathNode]] = field(default_factory=dict)
    spans: list[SpanAccess] = field(default_factory=list)
    api_hits: list[ApiHit] = field(default_factory=list)
    message_hits: list[MessageHit] = field(default_factory=list)
    looping: list[str] = field(default_factory=list)
    trace_waited: float = 0.0
    trace_timeout: float = 1.0
    pause_seconds: float = PAUSE_SECONDS
    pause_left: float = PAUSE_SECONDS
    windows: list[WindowTable] = field(default_factory=list)
    window_phase: str = "Read once the runs are over"
    window_state: str = "waiting"
    done: bool = False
    error: str | None = None

    @property
    def progress(self) -> int:
        """Percent done, by time: the runs and the pause as long as they last.

        A run lasts what the runs done so far lasted, guessed from the window
        before the first one ends; the pause weighs its seconds. The last
        percents wait for the traces once the runs are over.
        """
        if self.done:
            return 100
        spent = [run.duration_ms / 1000 for run in self.runs]
        per_run = (
            sum(spent) / len(spent)
            if spent
            else self.target.window_ms / 1000 + RUN_OVERHEAD_SECONDS
        )
        paused = 0.0
        if len(self.runs) >= RUNS_PER_BATCH:
            paused = self.pause_seconds - self.pause_left
        total = per_run * RUNS + self.pause_seconds
        part = RUNS_PART * min((sum(spent) + paused) / total, 1.0)
        if len(self.runs) == RUNS:
            searching = min(self.trace_waited / self.trace_timeout, 0.95)
            part += (1 - RUNS_PART) * searching
        return int(part * 100)

    @property
    def windows_read(self) -> bool:
        """Whether the third witness spoke: read, failed or not configured."""
        return self.window_state in WINDOW_SPOKE

    @property
    def path_services(self) -> set[str]:
        """The services on the test's own path: its fronts, APIs and workers.

        The lab sends the test's own SQL, so the console counts as one of them
        when the test has a query of its own.
        """
        services = {
            node.service
            for index, step in enumerate(self.target.steps)
            for node in self._step_path(index, step)
            if node.service and node.service != THE_TEST
        }
        if self.target.sql_accesses:
            services.add(LAB_SERVICE)
        return services

    def colleague_only(self, table: str) -> bool:
        """Whether only colleagues' SQL spans named a table, in every run window.

        Spans from services off the test's path, in every run: someone busy
        through every run, whom the intersection alone cannot rule out.
        """
        seen = next((w for w in self.windows if w.table == table), None)
        return (
            seen is not None
            and seen.runs == len(self.runs)
            and not set(seen.services) & self.path_services
        )

    @property
    def checked(self) -> bool:
        """Whether every traced step of the test has its trace read."""
        return all(index in self.traced_steps for index in self.target.traced_indices)

    def _step_path(self, index: int, step: Step) -> list[PathNode]:
        """One step of the path: its trace, or the test's own SQL."""
        traced = self.traced_steps.get(index)
        if isinstance(step, SqlQuery):
            return [PathNode("sql", step.title, THE_TEST)] + [
                PathNode("table", a.table, a.service, a.operation)
                for a in step.accesses
            ]
        if isinstance(step, FrontVisit):
            return [front_node(step)] + [
                node
                for node in traced or []
                if not (node.kind in {"api", "event"} and node.service == step.front)
            ]
        return traced or [PathNode("api", step.title)]

    @property
    def path(self) -> list[PathNode]:
        """The test's path, step by step: the traces, and the test's own SQL."""
        return [
            node
            for index, step in enumerate(self.target.steps)
            for node in self._step_path(index, step)
        ]

    def step_runs(self, index: int) -> int:
        """In how many runs so far the step of that index was played."""
        return sum(
            1
            for run in self.runs
            if index < len(run.steps) and run.steps[index].outcome != SKIPPED
        )

    def _fronts_by_step(self) -> list[tuple[PathNode, int]]:
        """Each front the test opened a page of, with the index of its step."""
        return [
            (front_node(step), index)
            for index, step in enumerate(self.target.steps)
            if isinstance(step, FrontVisit)
        ]

    def _apis_by_step(self) -> list[tuple[PathNode, int]]:
        """Each API the test went through, with the index of its step.

        The test's own calls first, then the ones its traces name.
        """
        found = [
            (PathNode("api", step.title, THE_TEST), index)
            for index, step in enumerate(self.target.steps)
            if isinstance(step, ApiCall)
        ]
        for index, step in enumerate(self.target.steps):
            for node in self._step_path(index, step):
                if node.kind not in {"api", "event"} or node.service == THE_TEST:
                    continue
                if all(known.label != node.label for known, _ in found):
                    found.append((node, index))
        return found

    @property
    def fronts(self) -> list[PathNode]:
        """Each front the test opened a page of, in order."""
        return [node for node, _ in self._fronts_by_step()]

    @property
    def apis(self) -> list[PathNode]:
        """Each API the test went through: its own calls, then the traces'."""
        return [node for node, _ in self._apis_by_step()]

    @property
    def used(self) -> list[str]:
        """Every table seen in at least one run, in the schema's order."""
        seen = {hit.table for run in self.runs for hit in run.hits}
        return [table for table in COMPANY_TABLES if table in seen]

    @property
    def found(self) -> list[str]:
        """The tables seen in every run so far, the answer of the intersection."""
        return self.runs[-1].candidates if self.runs else []

    @property
    def exact(self) -> list[str]:
        """The tables the traces and the test's own SQL name, the exact answer."""
        accesses = self.traced + self.target.sql_accesses
        return sorted({access.table for access in accesses})

    def access(self, table: str) -> str:
        """How the runs used a table: ``read``, ``write`` or ``read + write``."""
        hits = [hit for run in self.runs for hit in run.hits if hit.table == table]
        reads = any(hit.reads for hit in hits)
        writes = any(hit.writes for hit in hits)
        if reads and writes:
            return "read + write"
        return "write" if writes else "read"

    @property
    def final(self) -> list[dict[str, str]]:
        """The witnesses merged, step by step, once every one has spoken.

        The path the traces (and the test's own SQL) name, each table marked
        ``both`` when the database also counted it in every run, ``named``
        when some run did not see it move (a cache, a branch); then, after
        the step it moved during in the last run, each table the database
        counted in every run but nothing names. The SQL spans of the run
        windows decide between the two readings of such a table: spans only
        from services off the test's path make it ``colleague``, someone busy
        through every run; otherwise ``counted``, touched by something sending
        no trace. Without the spans (Tempo unreachable or not configured), a
        table counted only stays ``counted``.

        Returns:
            The stops, empty until the runs are over, the traces and the run
            windows read.
        """
        if len(self.runs) < RUNS or not self.checked or not self.windows_read:
            return []
        found, exact = set(self.found), set(self.exact)
        last = self.runs[-1]
        nodes: list[dict[str, str]] = []
        placed: set[str] = set()

        def counted(tables: list[str]) -> None:
            for table in tables:
                if table in found and table not in exact and table not in placed:
                    placed.add(table)
                    nodes.append(
                        {
                            **vars(PathNode("table", table, "", self.access(table))),
                            "source": "colleague"
                            if self.colleague_only(table)
                            else "counted",
                            "detail": self.window_detail(table),
                        }
                    )

        for index, step in enumerate(self.target.steps):
            for node in self._step_path(index, step):
                entry = {**vars(node), "source": "", "detail": ""}
                if node.kind == "table":
                    placed.add(node.label)
                    entry["source"] = "both" if node.label in found else "named"
                    entry["detail"] = self.window_detail(node.label)
                nodes.append(entry)
            counted(last.steps[index].tables if index < len(last.steps) else [])
        counted(self.found)
        return nodes

    @property
    def ownership(self) -> list[dict[str, Any]]:
        """Which team owns each table of the final answer, as the spans declare it.

        A team owns a table when a span of its service names the table: the
        observability platform files the span, so the table, under that team.
        A table the test touched with no such span is an orphan: its spans
        come from services declaring no team, or there is no span at all (the
        database counted it, nothing traced). A table only the test's own SQL
        names has no service to own it. Likely colleagues are left out.

        Returns:
            One entry per table, orphans first, empty until the final answer
            is ready or when no trace was read.
        """
        if not self.final or not self.traced:
            return []
        own_sql = {access.table for access in self.target.sql_accesses}
        tables = [
            n["label"]
            for n in self.final
            if n["kind"] == "table" and n["source"] != "colleague"
        ]
        entries = []
        for table in dict.fromkeys(tables):
            spans = [access for access in self.traced if access.table == table]
            teams = sorted({access.team for access in spans if access.team})
            services = sorted({access.service for access in spans})
            declared = sorted({access.service for access in spans if access.team})
            if teams:
                status, why = OWNED, f"spans of {', '.join(declared)}"
            elif spans:
                status = ORPHAN
                why = f"spans of {', '.join(services)}, no team declared"
            elif table in own_sql:
                status, why = TEST_OWN, "named by the test's own SQL only"
            else:
                status = ORPHAN
                why = "counted by the database, no span names it"
            entries.append(
                {"table": table, "status": status, "teams": teams, "why": why}
            )
        return sorted(entries, key=lambda entry: entry["status"] != ORPHAN)

    @property
    def service_ownership(self) -> list[dict[str, Any]]:
        """Which team owns each API and each message destination of the traces.

        An API is owned when its service declares a team, so the platform
        files its server spans under it; a destination when the services
        publishing to it or consuming from it do. Otherwise an orphan:
        searching by team never finds it.

        Returns:
            The APIs then the destinations, each with ``of``, ``item``,
            ``status``, ``teams`` and ``why``, orphans first within each;
            empty until the final answer is ready or when no trace was read.
        """
        if not self.final or not self.traced:
            return []
        apis: dict[str, list[ApiHit]] = {}
        for hit in self.api_hits:
            apis.setdefault(hit.service, []).append(hit)
        brokers: dict[str, list[MessageHit]] = {}
        for message in self.message_hits:
            brokers.setdefault(message.destination, []).append(message)
        entries = [
            _owned("api", service, hits, sorted({h.route for h in hits}))
            for service, hits in apis.items()
        ] + [
            _owned(
                "broker",
                destination,
                hits,
                sorted({f"{_VERBS[h.operation]} by {h.service}" for h in hits}),
            )
            for destination, hits in brokers.items()
        ]
        return sorted(
            entries,
            key=lambda e: (e["of"] != "api", e["status"] != ORPHAN, e["item"]),
        )

    @property
    def hints(self) -> list[Hint]:
        """Where the test calls, sends or reads something more than once.

        The endpoints first, then the messages, then the tables: the server,
        producer, consumer and SQL spans of the traces, and the test's own SQL
        as spans of ``the test``, in the order of the steps. Empty until the
        runs are over and the traces read.
        """
        if len(self.runs) < RUNS or not self.checked:
            return []
        apis = api_hints(sorted(self.api_hits, key=lambda hit: hit.step))
        own = [
            SpanAccess(index, THE_TEST, table, operation, step.statement)
            for index, step in enumerate(self.target.steps)
            if isinstance(step, SqlQuery)
            for table, operation in tables_in_statement(step.statement)
        ]
        messages = message_hints(sorted(self.message_hits, key=lambda h: h.step))
        return (
            apis
            + messages
            + optimization_hints(sorted(self.spans + own, key=lambda span: span.step))
        )

    def window_detail(self, table: str) -> str:
        """What the run windows say of a table: who sent its SQL, how often."""
        seen = next((w for w in self.windows if w.table == table), None)
        if seen is None:
            return "no SQL span in the run windows" if self.windows else ""
        senders = ", ".join(seen.services)
        return f"SQL from {senders} in {seen.runs}/{len(self.runs)} windows"

    def to_json(self) -> dict[str, Any]:
        """Everything the page draws, as JSON."""
        return {
            "id": self.id,
            "target": self.target.title,
            "steps": [
                {
                    "kind": s.kind,
                    "title": s.title,
                    "redirect": isinstance(s, FrontVisit) and s.redirect,
                }
                for s in self.target.steps
            ],
            "traced_steps": len(self.target.traced_indices),
            "phase": self.phase,
            "progress": self.progress,
            "done": self.done,
            "error": self.error,
            "used": self.used,
            "found": self.found,
            "fronts": [
                {**vars(node), "runs": self.step_runs(index)}
                for node, index in self._fronts_by_step()
            ],
            "apis": [
                {**vars(node), "runs": self.step_runs(index)}
                for node, index in self._apis_by_step()
            ],
            "demo": self.target.demo is not None,
            "looping": self.looping,
            "looping_runs": (
                self.target.demo.looping_runs if self.target.demo else RUNS_PER_BATCH
            ),
            "runs": [
                {
                    "number": run.number,
                    "batch": run.batch,
                    "duration_ms": run.duration_ms,
                    "hits": [vars(hit) for hit in run.hits],
                    "colleagues": run.colleagues,
                    "candidates": run.candidates,
                    "dropped": run.dropped,
                    "order": run.order,
                    "steps": [vars(step) for step in run.steps],
                }
                for run in self.runs
            ],
            "runs_over": len(self.runs) == RUNS,
            "runs_total": RUNS,
            "pause_left": int(self.pause_left),
            "trace_phase": self.trace_phase,
            "trace_ids": self.trace_ids,
            "traced": [vars(access) for access in self.traced],
            "sql": [vars(access) for access in self.target.sql_accesses],
            "checked": self.checked,
            "path": [vars(node) for node in self.path],
            "final": self.final,
            "ownership": self.ownership,
            "service_ownership": self.service_ownership,
            "hints": [{**vars(hint), "saved": hint.saved} for hint in self.hints],
            "window": {
                "state": self.window_state,
                "phase": self.window_phase,
                "tables": [vars(w) for w in self.windows],
            },
            "exact": self.exact,
        }


def front_node(step: FrontVisit) -> PathNode:
    """A page of a front on the path, marked when the user was sent there."""
    return PathNode(
        "front", step.title, step.front, "redirect" if step.redirect else ""
    )


def looping_colleague(rng: random.Random) -> list[str]:
    """Pick the tables of the colleague looping during the whole first batch."""
    return sorted(rng.sample(COMPANY_TABLES, LOOPING_TABLES))


def colleague_tables(
    run_index: int, rng: random.Random, looping: list[str] | None = None
) -> list[str]:
    """Pick the tables colleagues query during one run.

    Args:
        run_index: Which run, from 0.
        rng: Where the choice comes from.
        looping: The looping colleague's tables, queried in every run of the
            first batch.

    Returns:
        Fewer tables with each run of a batch, any table of the company
        database, plus the looping colleague's during the first batch.
    """
    batch, index = divmod(run_index, RUNS_PER_BATCH)
    picked = rng.sample(COMPANY_TABLES, COLLEAGUE_TABLES[batch][index])
    if batch == 0:
        picked += [table for table in looping or [] if table not in picked]
    return picked


def demo_run(
    demo: Demo,
    index: int,
    rng: random.Random,
    candidates: list[str] | None,
    duration_ms: int = DEMO_RUN_MS,
) -> Run:
    """Draw one run of a simulated experiment, as the database would see it.

    Each step is played or skipped by its ``presence``; colleagues and the
    looping job query their tables meanwhile, each one landing in a step
    played, as the counters would tie it.

    Args:
        demo: The simulated test.
        index: Which run, from 0.
        rng: Where the draws come from.
        candidates: The candidates so far, ``None`` before the first run.
        duration_ms: How long the run is said to last.

    Returns:
        The run, its candidates narrowed.
    """
    looping = list(demo.looping) if index < demo.looping_runs else []
    noise = rng.sample(COMPANY_TABLES, demo.noise[index])
    colleagues = sorted(set(noise) | set(looping))
    played = [rng.random() < step.presence for step in demo.steps]
    moved = [
        [table for table, _ in step.tables] + list(step.untraced) if on else []
        for step, on in zip(demo.steps, played, strict=True)
    ]
    landing = [n for n, on in enumerate(played) if on] or [0]
    for table in colleagues:
        step = moved[rng.choice(landing)]
        step.extend([table] if table not in step else [])
    order: list[str] = []
    for tables in moved:
        order += [table for table in tables if table not in order]
    written = {
        table
        for step, on in zip(demo.steps, played, strict=True)
        if on
        for table, operation in [*step.tables, *((t, "write") for t in step.untraced)]
        if operation == "write"
    }
    hits = [
        TableHits(table, rng.randint(1, 3), int(table in written))
        for table in COMPANY_TABLES
        if table in order
    ]
    kept, dropped = narrow(candidates, hits)
    steps = [
        StepSeen(s.step.kind, s.step.title, "HTTP 200" if on else SKIPPED, tables)
        for s, on, tables in zip(demo.steps, played, moved, strict=True)
    ]
    return Run(index + 1, duration_ms, hits, colleagues, kept, dropped, order, steps)


def touched(
    before: Mapping[str, tuple[int, int]], after: Mapping[str, tuple[int, int]]
) -> list[TableHits]:
    """Compare two snapshots of the table counters.

    Args:
        before: Reads and writes per table at the start of the run.
        after: The same at its end.

    Returns:
        The tables read or written in between, in the schema's order.
    """
    hits = []
    for table in COMPANY_TABLES:
        reads_before, writes_before = before.get(table, (0, 0))
        reads_after, writes_after = after.get(table, (0, 0))
        reads, writes = reads_after - reads_before, writes_after - writes_before
        if reads or writes:
            hits.append(TableHits(table, reads, writes))
    return hits


def narrow(
    candidates: list[str] | None, hits: list[TableHits]
) -> tuple[list[str], list[str]]:
    """Keep the candidates seen again by this run.

    Args:
        candidates: The candidates so far, ``None`` before the first run.
        hits: What this run saw.

    Returns:
        The candidates kept, and the ones this run ruled out.
    """
    seen = [hit.table for hit in hits]
    if candidates is None:
        return seen, []
    return (
        [table for table in candidates if table in seen],
        [table for table in candidates if table not in seen],
    )


def tables_in_statement(statement: str) -> list[tuple[str, str]]:
    """Find the company tables a SQL statement names, and what it does to each.

    Args:
        statement: The statement, as the span records it.

    Returns:
        Each table once with ``read`` or ``write``, in the order they appear:
        ``INSERT INTO orders ... SELECT ... FROM products`` writes ``orders``
        and reads ``products``.
    """
    found: dict[str, str] = {}
    for keyword, name in STATEMENT_TABLE.findall(statement):
        table = name.lower()
        if table not in COMPANY_TABLES:
            continue
        written = " ".join(keyword.upper().split()) in WRITE_KEYWORDS
        if written or table not in found:
            found[table] = "write" if written else "read"
    return list(found.items())


def pick_trace(search: Mapping[str, Any], start_ns: int, end_ns: int) -> str | None:
    """Pick, in a Tempo search answer, the trace that started during a run.

    Args:
        search: The JSON of ``/api/search``.
        start_ns: Start of the run, in nanoseconds since the epoch.
        end_ns: End of the run.

    Returns:
        The id of the earliest such trace, or ``None``.
    """
    inside = [
        trace
        for trace in search.get("traces", [])
        if start_ns <= int(trace.get("startTimeUnixNano", 0)) <= end_ns
    ]
    inside.sort(key=lambda trace: int(trace["startTimeUnixNano"]))
    return inside[0]["traceID"] if inside else None


def new_traceparent() -> str:
    """A W3C ``traceparent`` header starting a new sampled trace."""
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"


def trace_id_of(traceparent: str | None) -> str | None:
    """The trace id a ``traceparent`` header carries, if it is well formed."""
    parts = (traceparent or "").split("-")
    if len(parts) != TRACEPARENT_PARTS or len(parts[1]) != TRACE_ID_LENGTH:
        return None
    return parts[1]


def span_count(trace: Mapping[str, Any]) -> int:
    """How many spans a trace of Tempo holds, to see it is still filling."""
    return sum(
        len(scope.get("spans", []))
        for batch in trace.get("batches", [])
        for scope in batch.get("scopeSpans", [])
    )


def _attribute(attributes: list[dict[str, Any]], key: str) -> str | None:
    """Read one string attribute of an OTLP span or resource."""
    for attribute in attributes:
        if attribute.get("key") == key:
            return attribute.get("value", {}).get("stringValue")
    return None


def _spans(trace: Mapping[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Every span of a trace with its service and team, in the order they started.

    The team is the ``team`` resource attribute, empty when the service
    declares none.
    """
    spans = [
        (
            _attribute(batch.get("resource", {}).get("attributes", []), "service.name"),
            _attribute(batch.get("resource", {}).get("attributes", []), TEAM_ATTRIBUTE),
            span,
        )
        for batch in trace.get("batches", [])
        for scope in batch.get("scopeSpans", [])
        for span in scope.get("spans", [])
    ]
    spans.sort(key=lambda spanned: int(spanned[2].get("startTimeUnixNano", 0)))
    return [(service or "unknown", team or "", span) for service, team, span in spans]


def _span_tables(span: Mapping[str, Any]) -> list[tuple[str, str]]:
    """The company tables one SQL span touches, none for any other span."""
    attributes = span.get("attributes", [])
    statement = _attribute(attributes, "db.statement")
    if _attribute(attributes, "db.system") != "mysql" or not statement:
        return []
    if _attribute(attributes, "db.name") != COMPANY_DATABASE:
        return []
    return tables_in_statement(statement)


def span_accesses(trace: Mapping[str, Any], step: int) -> list[SpanAccess]:
    """List every SQL span of a trace on a company table, one by one, in order.

    Args:
        trace: The JSON of Tempo's ``/api/traces/<id>``, OTLP batches.
        step: Index of the test's step the trace belongs to.

    Returns:
        One access per span and table, nothing merged.
    """
    return [
        SpanAccess(
            step,
            service,
            table,
            operation,
            _attribute(span.get("attributes", []), "db.statement") or "",
            team,
        )
        for service, team, span in _spans(trace)
        for table, operation in _span_tables(span)
    ]


def trace_api_hits(trace: Mapping[str, Any], step: int) -> list[ApiHit]:
    """List every endpoint answering in a trace, with who called it, in order.

    A server span answers a call; the service of its parent span made it. The
    lab plays the test, so a call from the console's lab, or from outside the
    trace, is the test's.

    Args:
        trace: The JSON of Tempo's ``/api/traces/<id>``, OTLP batches.
        step: Index of the test's step the trace belongs to.

    Returns:
        One hit per server span.
    """
    spans = _spans(trace)
    owners = {span.get("spanId"): service for service, _, span in spans}
    hits = []
    for service, team, span in spans:
        if ENTRY_KINDS.get(span.get("kind", "")) != "api":
            continue
        caller = owners.get(span.get("parentSpanId"), THE_TEST)
        if caller == LAB_SERVICE:
            caller = THE_TEST
        hits.append(ApiHit(step, service, span.get("name", ""), caller, team))
    return hits


def trace_message_hits(trace: Mapping[str, Any], step: int) -> list[MessageHit]:
    """List every message a trace's services published or consumed, in order.

    A producer span publishes a message, a consumer span takes one. The
    destination is the ``messaging.destination.name`` attribute (or the older
    ``messaging.destination``), the span's name when it has neither.

    Args:
        trace: The JSON of Tempo's ``/api/traces/<id>``, OTLP batches.
        step: Index of the test's step the trace belongs to.

    Returns:
        One hit per producer or consumer span.
    """
    hits = []
    for service, team, span in _spans(trace):
        operation = MESSAGE_KINDS.get(span.get("kind", ""))
        if operation is None:
            continue
        attributes = span.get("attributes", [])
        destination = (
            _attribute(attributes, "messaging.destination.name")
            or _attribute(attributes, "messaging.destination")
            or span.get("name", "")
        )
        hits.append(MessageHit(step, service, destination, operation, team))
    return hits


def traced_accesses(trace: Mapping[str, Any]) -> list[TracedAccess]:
    """List the company tables a trace's SQL spans touch.

    Args:
        trace: The JSON of Tempo's ``/api/traces/<id>``, OTLP batches.

    Returns:
        One access per service, table and operation, with the service's team,
        sorted.
    """
    accesses = {
        TracedAccess(service, table, operation, team)
        for service, team, span in _spans(trace)
        for table, operation in _span_tables(span)
    }
    return sorted(accesses, key=lambda a: (a.service, a.table, a.operation))


def trace_path(trace: Mapping[str, Any]) -> list[PathNode]:
    """Draw a trace as a path: each API or worker, then the tables it touches.

    Spans are read in the order they started. A server span opens an API, a
    consumer span a worker; the tables that follow belong to it, each once.
    When a service touches a table after another one answered (hello-api
    after the bank partner), its API comes back on the path.

    Args:
        trace: The JSON of Tempo's ``/api/traces/<id>``, OTLP batches.

    Returns:
        The stops, in order.
    """
    path: list[PathNode] = []
    entries: dict[str, PathNode] = {}
    current: str | None = None
    seen: set[str] = set()
    for service, _, span in _spans(trace):
        kind = ENTRY_KINDS.get(span.get("kind", ""))
        if kind:
            entries[service] = PathNode(kind, span.get("name", ""), service)
            path.append(entries[service])
            current, seen = service, set()
            continue
        for table, operation in _span_tables(span):
            if service != current:
                path.append(entries.get(service, PathNode("api", service, service)))
                current, seen = service, set()
            if table not in seen:
                seen.add(table)
                path.append(PathNode("table", table, service, operation))
    return path
