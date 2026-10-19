# Databases: every table the console may read

**Databases** lists every database the console's read-only account (`console_reader`) can read, then their tables, then their rows.

> **TL;DR**
>
> - `mycompany` (the company, 30 tables), `orchestrator` (the order workflow state), `catalog` (the software catalog), `identity` (two views of the identity users).
> - Each database and table carries its label: `live` when the storefront writes it, `static` when it is loaded once and only read, `mixed` for a database holding both.
> - The account has `SELECT` only: MySQL itself refuses a write. Any name from a request is checked against what MySQL lists before reaching a statement.

## What the pages show

1. **Databases**: one card per database with its label.
2. A database: its tables split in two sections, **Live experimentation** first (in `mycompany`: `orders`, `order_items`, `stock_levels`, `invoices`, `payments`, `audit_logs`), then **Static**, each with its exact row count (one `COUNT(*)` per table, a span in Grafana).
3. A table: its first 50 rows, a search on one column, exact or contains.

Opening a database, a table or a search calls MySQL: those are the only clicks that wait behind the loader.

## Watching live tables move

Place an order on the storefront, then open `mycompany`: the counts of the live tables grow (an order, its items, an invoice, a payment, audit lines), the static ones do not. `orchestrator` holds the workflow and its steps.

## Where it lives

`src/quality_console/databases.py` (the reads), `database_pages.py` (the routes), `table_kinds.py` (the labels), `db/03-console-reader.sql` (the account and its grants).
