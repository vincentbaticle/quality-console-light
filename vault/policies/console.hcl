# The Quality Console: which credentials are out and for how long, never a value.
path "sys/leases/lookup" { capabilities = ["update"] }
path "sys/leases/lookup/*" { capabilities = ["list", "sudo"] }
path "database/roles/*" { capabilities = ["read"] }
path "rabbitmq/config/lease" { capabilities = ["read"] }
path "secret/metadata/*" { capabilities = ["read", "list"] }
