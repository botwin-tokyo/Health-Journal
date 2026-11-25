log_level = "warn"
log_format = "json"
vault {
  address = "https://127.0.0.1:8200"
  ca_cert = "/etc/health03/bao-server-ca.crt"
}
auto_auth {
  method "cert" {
    config = {
      name = "health03-app"
      ca_cert = "/etc/health03/bao-server-ca.crt"
      client_cert = "/etc/health03/bao-agent/client.crt"
      client_key = "/run/credentials/health03-bao-agent.service/client-key"
    }
  }
}
api_proxy {
  use_auto_auth_token = "force"
}
listener "unix" {
  address = "/run/health03-bao-agent/api.sock"
  socket_mode = "0660"
  tls_disable = true
}
