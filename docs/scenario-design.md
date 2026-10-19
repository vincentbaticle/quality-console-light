# Scenario design

A scenario design draws a journey as a graph, every state and every transition, and each Gherkin scenario as a path on it. Gherkin says precisely what one scenario checks; the design shows where all of them go, and where none goes yet. **Tools**, **Scenario design** in the Quality Console.

> **TL;DR**
>
> - Designs are YAML files of `designs/`, beside `features/`: nodes, edges, and for each scenario the path it walks.
> - The console draws them with Mermaid: grey transitions are walked by a scenario, red dashed ones by none (the gaps), the selected scenario in bold blue. **Run** runs that scenario on the stack.
> - Three examples: account access (first sign-in to a blocked account), checkout (placed to paid), bucket checks (the contract of a team bucket).
> - A unit test checks that every node, transition and scenario of a design exists.

## Why design scenarios as a graph

Scenarios are written one by one, and a list of scenarios hides what it misses. Drawn on the journey, the missing ones show:

- **Account access** has 23 transitions; 6 have no scenario, among them an account migrated from a legacy login, the link given by the Management API without any email, and a weak password refused. The first one is the case a login migration study raises: the design makes it a question for the product owner rather than a forgotten test.
- **Checkout**: no scenario for a payment the provider refuses, nor for a worker that dies in the middle of a step and gets the event again.
- **Bucket checks**: every check passes on the two team buckets, but no example bucket holds a broken file, so nothing proves a misnamed, empty or stale file is caught. Adding a bucket with broken files to the examples would turn those red transitions grey.

The design comes before the scenarios or beside them: the QA team proposes it, the product owner validates the journey, then each path becomes a scenario.

## Writing a design

```yaml
title: Checkout, an order from placed to paid
product: checkout
purpose: What the journey is, and what its gaps mean.
nodes:
  - {id: order, label: "Order sent by the storefront", kind: start}
  - {id: stock, label: "Enough stock?", kind: check}
  - {id: paid, label: "Order paid", kind: outcome}
  - {id: cancelled, label: "Order cancelled", kind: failure}
edges:
  - {from: order, to: stock, label: "reserve_stock event"}
  - {from: stock, to: paid, label: "yes"}
  - {from: stock, to: cancelled, label: "no"}
scenarios:
  - scenario: An order in stock is paid step by step
    feature: checkout/place-order.feature
    path: [order, stock, paid]
```

- `kind`: `start` (a journey begins), `state`, `check` (a decision), `outcome` (a good end), `failure` (a refusal or an error).
- Quote every label: YAML reads `yes` and `no` as booleans otherwise.
- `scenario` and `feature` must name a scenario of `features/`; `tests/unit/test_console_analysis.py` fails otherwise.

## Bucket checks, generic tests on many buckets

`features/bucket-checks/file-contracts.feature` checks files that teams drop in buckets, not the results bucket of this project. The checks are generic, and each bucket brings its own contract as a row of examples: the prefix, the name pattern, the format, the freshness. The demo buckets `finance-exports` (a CSV of invoices per day) and `catalog-feeds` (JSON feeds) are loaded from `buckets/` into the storage emulator at start. Testing another bucket is one more row; a broken file is one more bucket in `buckets/`.
