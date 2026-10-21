# The software catalog and the test metadata

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

The company's systems, components, APIs, databases and teams are declared once, as code, in `catalog/catalog.yaml`. Every test says which of them it covers, and a unit test refuses a value the catalog does not hold.

> **TL;DR**
>
> - `catalog/catalog.yaml`: domains, business capabilities, teams (with their Jira project), systems, products, components, APIs, resources.
> - `mise run catalog:sql` turns it into `db/05-catalog.sql`, the `catalog` database of MySQL: the console and its tools read it like any tool would read a real catalog.
> - Every test module declares `metadata_test(system=..., product=..., business_capability=..., component=..., group=..., testing_scope=..., tags=...)`, the fields of the team's test runner. The values must be catalog entries.
> - Result: a failed run in the console points to a component, its owner and its Jira project; the catalog page links each component to its runs.
> - The catalog page opens on a **map**: systems, products and components joined by arrows, each coloured by the test runs that name it (green, red, partly, grey).

## Why a catalog in a demo

Tools that talk about the same things must use the same names. Without a catalog, the test results say `hello`, the Jira board says `STORE` and the dashboard says `storefront`. Here one file names everything, and the tools are wired to it:

- the **test results** filter on the metadata, whose values are catalog names;
- the **Gherkin scenarios** are grouped by catalog product, titled and described by the catalog;
- the **API docs** list the APIs of the catalog and open their contract;
- the **catalog page** links databases to the database browser and components to their test runs;
- the **data exchange** system declares the team buckets (`finance-exports`, `catalog-feeds`) the bucket checks test.

Plugging a real catalog later (a developer portal, a CMDB) means filling the `catalog` database from it instead of from the YAML file: the tools read the database, not the file.

## The model

| Entity | What it is | Example |
| --- | --- | --- |
| domain | a business area | `retail` |
| business capability | what the business does, `business_capability` of a test | `sell` |
| team | owns entities, tracks its work in one Jira project | `checkout-squad`, `CHK` |
| system | components delivering one business function | `orders` |
| product | what a user sees of a system, `product` of a test | `checkout` |
| component | a service, website, worker or library | `order-worker` |
| API | an interface, with its contract in `contracts/` | `order-workflow-events` |
| resource | a database, queue, bucket, cache or mailbox | `orchestrator-db` |

Components say which APIs they provide, consume, publish or subscribe to, and which resources they depend on.

## Declaring the metadata of a test

```python
pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="orders",
        product="checkout",
        business_capability="sell",
        component="order-worker",
        group="checkout-squad",
        testing_scope="integration",
        tags="rabbitmq, mysql",
    ),
]
```

- On a module (`pytestmark`), a class or one test (`@metadata_test(...)`): the closest one wins, see the browser test, whose order test overrides the module's product.
- `tests/conftest.py` writes the fields as JUnit properties, the uploader aggregates them into the run's `test_meta`, the console offers them as filters.
- `tests/unit/test_metadata_catalog.py` reads every test module and checks each value: system, product, capability, component and group must be catalog entries, the scope one of `unit`, `integration`, `contract`, `e2e`, `acceptance`, `regression`, `performance`. It also checks that `db/05-catalog.sql` is the one the catalog generates.

## The map of the catalog

The top of the catalog page draws three columns, one band per system: the system, its products, its components, an arrow from the system to each of them, and a dashed blue arrow from a component to the one whose API it calls or whose events it consumes. Each item is coloured by the runs whose test metadata names it (`system`, `product`, `component`), the last run of each job and environment deciding:

- **green**: every job known for it ran in the last 7 days, and its last run passed;
- **red**: the last run of one of its jobs failed; the card says how many tests of its last runs passed (`24/28 tests passed · 2 jobs failed`), the tooltip which jobs failed and how (`8/10 passed, 2 errors`);
- **between grey and green**, with a bar under the card: only part of its known jobs ran in the last 7 days;
- **grey, dashed**: no run ever named it.

A click opens its runs in Test results. An item is "known" from the runs, not from the code: a test written but never run leaves it grey. The rules live in `src/quality_console/catalog_map.py`, unit tested in `tests/unit/test_catalog_map.py`.

## Changing the catalog

1. Edit `catalog/catalog.yaml`.
2. `mise run catalog:sql`: refuses a reference to an entity the file does not declare, then writes `db/05-catalog.sql`.
3. `mise run down && mise run up` to reload MySQL.
4. Commit both files; the unit test fails if they drift.
