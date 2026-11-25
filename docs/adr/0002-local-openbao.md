# Local OpenBao deployment

Run OpenBao under a separate non-login service identity with loopback TLS, restricted persistent state and limited app authentication. PostgreSQL, Gunicorn and workers also run on this Pi. The parser has no OpenBao access. No OpenBao endpoint is published through Cloudflare. The app may wrap/unwrap permitted keys but may not administer, export or delete them.

This isolates processes and credentials; it does not protect against compromise of root or theft of a complete unlocked host. Do not claim physical key separation. Recovery shares and backup recovery material are kept outside application source/database and need an owner-controlled offline recovery copy before real-data release. Off-device backup configuration is a later gate, not a reason to require a paid provider or delay synthetic implementation.

Development may initialize a locally persisted synthetic OpenBao instance with its recovery material in restricted operator-only storage. Clearly distinguish that evidence from final production recovery custody. No real health records are admitted before the existing security gates pass.
