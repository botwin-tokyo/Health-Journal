ui = false
api_addr = "https://127.0.0.1:8200"
cluster_addr = "https://127.0.0.1:8201"
log_level = "warn"
log_format = "json"
storage "raft" {
  path = "/var/lib/health03-openbao"
  node_id = "health03-pi"
}
listener "tcp" {
  address = "127.0.0.1:8200"
  cluster_address = "127.0.0.1:8201"
  tls_cert_file = "/etc/health03/openbao/server.crt"
  tls_key_file = "/etc/health03/openbao/server.key"
  tls_min_version = "tls12"
}
audit "file" "health03" {
  description = "Local metadata audit; sensitive string fields are HMAC protected."
  options {
    file_path = "/var/log/health03-openbao/audit.jsonl"
    log_raw = "false"
  }
}
