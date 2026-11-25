"""Generate static Pages headers from an exact HTTPS API origin."""

import argparse
from pathlib import Path
from urllib.parse import urlsplit

parser = argparse.ArgumentParser()
parser.add_argument("--api-origin", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
url = urlsplit(args.api_origin)
if (
    url.scheme != "https"
    or not url.hostname
    or url.path
    or url.query
    or url.fragment
    or url.username
):
    raise SystemExit("Exact HTTPS API origin required")
csp = (
    "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; connect-src 'self' "
    + args.api_origin
    + "; font-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)
Path(args.output).write_text(
    "/*\n  Cache-Control: no-store\n  Content-Security-Policy: "
    + csp
    + "\n  Referrer-Policy: no-referrer\n  X-Content-Type-Options: nosniff\n  Permissions-Policy: camera=(), microphone=(), geolocation=()\n/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n"
)
