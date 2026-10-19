# Vault: short-lived credentials for the services, a long-lived key for the bank

The storefront services get their database and broker credentials from HashiCorp Vault, each a user Vault creates for one service and drops a few minutes later; the Bank Partner's key, a secret the bank issued once, lives in Vault too. **DevX**, **Vault** shows which credentials are out and how long they have left.

> **TL;DR**
>
> - `mise run up` starts Vault (dev mode, <http://localhost:8200>, token `root`), configures it (`vault/init.sh`) and starts a **Vault Agent** that writes each service's credentials into a file.
> - Short-lived: a MySQL user per service (`hello-api`, `order-worker`, `identity-service`) and a RabbitMQ user per service that sends or reads the order events. Each lives 2 minutes, is renewed up to 6, then replaced.
> - Long-lived: `secret/bank-partner`, the key the bank issued us, sent as `X-Api-Key`; the bank answers `401` without it.
> - Tests read what they need from Vault (`hvac`, a token allowed one path), never from the repository.

## Who talks to Vault

Nobody among the services. The pattern is the one of a platform that syncs Vault into a service's environment and rotates it outside the code:

1. `vault-init` configures Vault once: the `database` engine on MySQL, the `rabbitmq` engine on the broker, one role per service with what it may do, the static secret of the bank, the policies, an AppRole for the agent, a token for the console and one for the tests.
2. `vault-agent` logs in with its AppRole and renders one file per credential into the `vault-secrets` volume: `/vault/secrets/<service>/db.env`, `rabbitmq.env`, `bank-partner.env`.
3. A service reads its file each time it opens a connection (`company_secrets.read_env_file`, through `DatabaseSettings.credentials()`, the broker's `url_from_environment()` and the Bank Partner client): when the agent writes new credentials, the next connection uses them, no restart. The order worker, connected for good to RabbitMQ, reconnects when the broker drops its revoked user.

Without the files (the integration tests, a laptop without Vault), the `DB_*` and `RABBITMQ_URL` variables still say everything: the code is the same.

## Short-lived and long-lived

| | Short-lived | Long-lived |
| --- | --- | --- |
| What | A MySQL user, a RabbitMQ user | The Bank Partner's API key |
| Who creates it | Vault, on demand, one per service | The bank, once, for us its client |
| Life | 2 minutes, renewed up to 6, then a new user; Vault drops the old one | Until the bank rotates it |
| Where | `database/creds/<service>`, `rabbitmq/creds/<service>` | `secret/bank-partner` (KV v2) |
| A leak is worth | Minutes, on one service's rights | Everything the key opens, until the bank rotates it |

The short lives are short on purpose, to watch them turn on the console page; a real setup would choose hours.

The rights are each service's own: `hello-api` and `order-worker` may read and write `mycompany` and `orchestrator`, `identity-service` only `identity`; the RabbitMQ users may only declare, write and read the `order-workflow` queue. The console keeps its `console_reader` account (`SELECT` only) and never holds a short-lived credential.

## The Vault page

**DevX**, **Vault**: for each role, the credentials alive now, when each was issued, whether it was renewed, the seconds it has left (a bar running down, the page reloads every 10 seconds); then the static secret's metadata (path, version, age), never its value. The console reads Vault with `console-token`, whose policy lists leases and reads metadata only (`vault/policies/console.hcl`). The full UI is in **Running beside the console**, **Vault**.

Watch a rotation: keep the page open six minutes. A `hello-api` user is renewed twice, then a new one appears and the old one goes; MySQL shows the same (`SELECT user FROM mysql.user WHERE user LIKE 'v-%'`), and a greeting in between never fails.

## Tests and Vault

The acceptance tests call the Bank Partner directly (schemathesis, the welcome page's data step): they read its key from Vault with `hvac` and `tests-token`, whose policy reads `secret/data/bank-partner` and nothing else (`tests/acceptance/conftest.py`, `partner_api_key`). The capture of the partner does the same (`scripts/capture_partner.py`). `partner-contracts/bank-partner.feature` checks the bank refuses a caller without the key, with the `401` its contract documents.

## Where it lives

- `vault/init.sh`, `vault/policies/*.hcl`, `vault/agent.hcl`: the configuration, the policies, the agent's templates.
- `docker-compose.yml`: `vault`, `vault-init`, `vault-agent`, the `vault-secrets` volume mounted read-only by `api`, `worker` and `identity`.
- `src/company_secrets/`: reading a file the agent writes.
- `src/quality_console/vault_view.py`, `tools/vault.py`, `templates/vault.html`: the console page.
- `tests/unit/test_vault_credentials.py`: the files read again on each connection, the broker URL, the page reading leases and never a value.
