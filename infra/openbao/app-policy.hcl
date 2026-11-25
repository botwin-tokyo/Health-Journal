path "transit/encrypt/clinical-dek" { capabilities = ["update"] }
path "transit/decrypt/clinical-dek" { capabilities = ["update"] }
path "transit/encrypt/auth-envelope" { capabilities = ["update"] }
path "transit/decrypt/auth-envelope" { capabilities = ["update"] }
path "transit/hmac/identity-lookup/sha2-256" { capabilities = ["update"] }
path "auth/token/renew-self" { capabilities = ["update"] }
path "auth/token/lookup-self" { capabilities = ["read"] }
path "auth/token/revoke-self" { capabilities = ["update"] }
