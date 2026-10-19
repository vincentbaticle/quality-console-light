# The Vault Agent of the storefront services: their credentials, nothing else.
path "database/creds/hello-api" { capabilities = ["read"] }
path "database/creds/order-worker" { capabilities = ["read"] }
path "database/creds/identity-service" { capabilities = ["read"] }
path "rabbitmq/creds/hello-api" { capabilities = ["read"] }
path "rabbitmq/creds/order-worker" { capabilities = ["read"] }
path "secret/data/bank-partner" { capabilities = ["read"] }
