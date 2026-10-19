#!/bin/sh
# Configures the dev Vault of the stack: who may get which credential, for how long.
# Runs again on every docker compose up: each step leaves what is already there.
set -eu

until vault status >/dev/null 2>&1; do sleep 1; done

mkdir -p /secrets/hello-api /secrets/order-worker /secrets/identity-service
chown -R vault:vault /secrets

enabled() { vault "$1" list -format=json | grep -q "\"$2/\""; }

enabled secrets database || vault secrets enable database
vault write database/config/mycompany \
  plugin_name=mysql-database-plugin \
  connection_url="{{username}}:{{password}}@tcp(mysql:3306)/" \
  allowed_roles="hello-api,order-worker,identity-service" \
  username=root password=root

for role in hello-api order-worker; do
  vault write "database/roles/$role" db_name=mycompany \
    creation_statements="CREATE USER '{{name}}'@'%' IDENTIFIED BY '{{password}}'; GRANT SELECT, INSERT, UPDATE, DELETE ON mycompany.* TO '{{name}}'@'%'; GRANT SELECT, INSERT, UPDATE, DELETE ON orchestrator.* TO '{{name}}'@'%';" \
    revocation_statements="DROP USER IF EXISTS '{{name}}'@'%';" \
    default_ttl="$SHORT_TTL" max_ttl="$SHORT_MAX_TTL"
done
vault write database/roles/identity-service db_name=mycompany \
  creation_statements="CREATE USER '{{name}}'@'%' IDENTIFIED BY '{{password}}'; GRANT SELECT, INSERT, UPDATE, DELETE ON identity.* TO '{{name}}'@'%';" \
  revocation_statements="DROP USER IF EXISTS '{{name}}'@'%';" \
  default_ttl="$SHORT_TTL" max_ttl="$SHORT_MAX_TTL"

enabled secrets rabbitmq || vault secrets enable rabbitmq
vault write rabbitmq/config/connection \
  connection_uri=http://rabbitmq:15672 username=guest password=guest
vault write rabbitmq/config/lease ttl="$SHORT_TTL" max_ttl="$SHORT_MAX_TTL"
for role in hello-api order-worker; do
  vault write "rabbitmq/roles/$role" \
    vhosts='{"/":{"configure":"^order-workflow$","write":"^(order-workflow|amq\\.default)$","read":"^order-workflow$"}}'
done

vault kv get secret/bank-partner >/dev/null 2>&1 ||
  vault kv put secret/bank-partner \
    api_key="$BANK_PARTNER_API_KEY" issued_by="Bank Partner" rotation="by the bank, once a year"

vault policy write storefront-agent /policies/storefront-agent.hcl
vault policy write console /policies/console.hcl
vault policy write tests /policies/tests.hcl

enabled auth approle || vault auth enable approle
vault write auth/approle/role/storefront-agent \
  token_policies=storefront-agent token_ttl=1h token_max_ttl=24h
vault read -field=role_id auth/approle/role/storefront-agent/role-id > /bootstrap/role_id
vault write -f -field=secret_id auth/approle/role/storefront-agent/secret-id > /bootstrap/secret_id
chmod 0644 /bootstrap/role_id /bootstrap/secret_id

for name in console tests; do
  vault token lookup "$name-token" >/dev/null 2>&1 ||
    vault token create -id="$name-token" -policy="$name" -period=24h >/dev/null
done
echo "vault configured: database and rabbitmq roles ($SHORT_TTL, at most $SHORT_MAX_TTL), secret/bank-partner, approle storefront-agent"
