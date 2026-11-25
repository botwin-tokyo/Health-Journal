# Shared synthetic frontend fixture

The source is `backend/records/synthetic.py`, persisted through real encryption by `seed_synthetic`. The frontend integration capture script records authenticated read models from that isolated fixture into this directory. MSW uses the same captured DTOs; it does not calculate replacement summaries. Production excludes `src/mocks` and this directory.

Clock: 2026-11-08; selected clinical date: 2026-11-07. All captured accounts use `example.invalid`.
