#!/usr/bin/env python3
"""Install on the owner-controlled backup boundary as an SSH forced command.
The app key can append bounded revocations only; no shell/forwarding/read API.
"""

import datetime
import hashlib
import json
import os
import sqlite3
import sys
import uuid


def main():
    if os.environ.get("SSH_ORIGINAL_COMMAND") != "append":
        raise SystemExit(1)
    payload = sys.stdin.buffer.read(65537)
    if len(payload) > 65536:
        raise SystemExit(1)
    events = json.loads(payload)
    if not isinstance(events, list) or not 1 <= len(events) <= 100:
        raise SystemExit(1)
    database = os.environ.get("HEALTH03_LEDGER_DB", "/var/lib/health03-ledger/ledger.sqlite3")
    os.umask(0o077)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL)"
        )
        connection.execute("BEGIN IMMEDIATE")
        acknowledgements = []
        for event in events:
            if not isinstance(event, dict) or set(event) != {
                "event_id",
                "owner_id",
                "target_id",
                "action",
                "occurred_at",
            }:
                raise ValueError("Invalid event")
            for field in ("event_id", "owner_id", "target_id"):
                if str(uuid.UUID(event[field])) != event[field]:
                    raise ValueError("Invalid identifier")
            if event["action"] not in {
                "record_deleted",
                "record_private",
                "grant_revoked",
                "device_revoked",
                "account_closed",
            }:
                raise ValueError("Permission expansion denied")
            if (
                len(event["occurred_at"]) > 40
                or datetime.datetime.fromisoformat(event["occurred_at"]).tzinfo is None
            ):
                raise ValueError("Invalid timestamp")
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
            existing = connection.execute(
                "SELECT sequence, payload, hash FROM events WHERE event_id=?", (event["event_id"],)
            ).fetchone()
            if existing:
                if existing[1] != canonical:
                    raise ValueError("Event identity conflict")
                sequence, digest = existing[0], existing[2]
            else:
                previous = connection.execute(
                    "SELECT hash FROM events ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                previous = previous[0] if previous else "0" * 64
                digest = hashlib.sha256((previous + canonical).encode()).hexdigest()
                cursor = connection.execute(
                    "INSERT INTO events(event_id,payload,previous_hash,hash) VALUES(?,?,?,?)",
                    (event["event_id"], canonical, previous, digest),
                )
                sequence = cursor.lastrowid
            acknowledgements.append(
                {"event_id": event["event_id"], "sequence": sequence, "hash": digest}
            )
        connection.commit()
    sys.stdout.write(json.dumps(acknowledgements))


if __name__ == "__main__":
    main()
