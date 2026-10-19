# One Vault Agent for the storefront services: it logs in with its AppRole,
# writes each service's credentials into a file, renews them, and writes new
# ones before a short-lived credential runs out. The services read the files.
vault {
  address = "http://vault:8200"
}

auto_auth {
  method "approle" {
    config = {
      role_id_file_path                   = "/bootstrap/role_id"
      secret_id_file_path                 = "/bootstrap/secret_id"
      remove_secret_id_file_after_reading = false
    }
  }
}

template_config {
  static_secret_render_interval = "1m"
}

template {
  destination = "/vault/secrets/hello-api/db.env"
  perms       = "0644"
  contents    = "{{ with secret \"database/creds/hello-api\" }}DB_USER={{ .Data.username }}\nDB_PASSWORD={{ .Data.password }}\n{{ end }}"
}

template {
  destination = "/vault/secrets/hello-api/rabbitmq.env"
  perms       = "0644"
  contents    = "{{ with secret \"rabbitmq/creds/hello-api\" }}RABBITMQ_USER={{ .Data.username }}\nRABBITMQ_PASSWORD={{ .Data.password }}\n{{ end }}"
}

template {
  destination = "/vault/secrets/hello-api/bank-partner.env"
  perms       = "0644"
  contents    = "{{ with secret \"secret/data/bank-partner\" }}BANK_PARTNER_API_KEY={{ .Data.data.api_key }}\n{{ end }}"
}

template {
  destination = "/vault/secrets/order-worker/db.env"
  perms       = "0644"
  contents    = "{{ with secret \"database/creds/order-worker\" }}DB_USER={{ .Data.username }}\nDB_PASSWORD={{ .Data.password }}\n{{ end }}"
}

template {
  destination = "/vault/secrets/order-worker/rabbitmq.env"
  perms       = "0644"
  contents    = "{{ with secret \"rabbitmq/creds/order-worker\" }}RABBITMQ_USER={{ .Data.username }}\nRABBITMQ_PASSWORD={{ .Data.password }}\n{{ end }}"
}

template {
  destination = "/vault/secrets/identity-service/db.env"
  perms       = "0644"
  contents    = "{{ with secret \"database/creds/identity-service\" }}DB_USER={{ .Data.username }}\nDB_PASSWORD={{ .Data.password }}\n{{ end }}"
}
