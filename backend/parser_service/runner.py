"""Fixed-operation child of the preprovisioned parser service."""

import os
import sys

from .operations import parse_csv, parse_pdf, render_report
from .protocol import MAX_INPUT, MAX_OUTPUT

operation = {"parse_pdf": parse_pdf, "parse_csv": parse_csv, "render_report": render_report}[
    sys.argv[1]
]
with os.fdopen(int(sys.argv[2]), "rb") as stream:
    payload = stream.read(MAX_INPUT + 1)
if len(payload) > MAX_INPUT:
    raise SystemExit(2)
result = operation(payload)
if len(result) > MAX_OUTPUT:
    raise SystemExit(2)
sys.stdout.buffer.write(result)
