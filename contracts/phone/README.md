# Phone ingestion contract: health03-phone-2026-11-09

The mobile exporter submits versioned records over authenticated HTTPS.

## Files and deployment identification

- `batch.schema.json`: JSON Schema Draft 2020-12 for the exact `pb-health-export-1` envelope, immutable item fields, typed session/scalar/context payloads and tombstones. The same payload schema is executed by the backend; it is not documentation-only.
- `metrics.json`: authoritative metric IDs, unit mappings, body aliases, accepted source vocabulary and value rules.
- `fixtures.json`: small synthetic accepted-clinical, accepted-evidence and explicitly rejected cases with expected receipt outcomes. They contain no owner data.
- `tests/backend/test_phone_contract.py`: real local-encryption/database integration test for upload, receipts, display, assets, repeat/revision/delete behavior. `tests/integration/test_phone_wire_contract.py` executes every fixture against the mapper.
- Query the configured ingestion service for its schema hash, revision and capabilities.

## Phone wire format

Each registered device uses a persistent source namespace and idempotent batch identifiers.

Configure the base URL for your own ingestion host; POST `/api/v1/ingestion/batches`, GET `/api/v1/ingestion/batches/{id}`, GET `/api/v1/ingestion/config`, POST `/api/v1/ingestion/assets`, POST `/api/v1/ingestion/commands/{id}/ack`. Existing `X-API-Key` authenticates intake.

The backend translates the shipped payload itself:

- `direct_scale`, all 14 lower-case body metric names, and empty BMI unit are accepted.
- Sleep `direct_ring`, `samsung_export`, and `synthetic` retain their actual provenance. Sleep is indexed by wake date. `Etc/UTC` with `offset_only` does not invent a historical zone.
- `pulmonary_session.status` accepts `SAVED`, `INTERRUPTED`, and `DRAFT`. All trials, curves, notes and context are read from `native_record`; native epoch milliseconds are converted on the server. The selected complete trial follows the exporter's maximum FVC + FEV1 rule.
- `body_profile`, `body_goals`, and `body_circumference` read their fields from `native_record`. Internal display names do not change phone identity or tombstone names.
- Workout sets, route, snapshot and intervals are read from `native_record.details`. Recorded duration remains usable with offset-only timestamps.
- `native_record_assets` uses the phone's `concatenated-utf8-json-v1` descriptor. The server reads IDs in order, verifies byte count and SHA-256, and extracts summary fields. Chunked originals remain downloadable attachments instead of being duplicated into large encrypted display records. Expansion is bounded to 100 MiB; larger originals remain downloadable with an explicit expansion status.

The following sections describe **server display projections** and compatible explicit fields. They are not instructions to rename the phone's existing wire fields. The complete original native record remains retained inline or as its ordered attachments.

## Types, time and extension fields

Use decimal **strings** for clinical values and curve axes to avoid precision loss; numeric JSON is also accepted for scalar values, sleep_seconds and duration_seconds for compatibility. Decimal strings allow a leading minus, up to 18 fractional places and 36 significant digits (no exponent). NaN/Infinity are invalid JSON. IDs/source/device/version labels are strings. Exact required keys, nullability, collection bounds and formats are in the schema. Fields outside typed properties are retained as source extensions; don't use them instead of the typed fields needed for summaries.

Use ISO-8601 offset-aware strings for measured_start/end and stage/interval/trial timestamps. Native epoch milliseconds inside `native_record` are accepted as sent and converted by the server for display. Durations are decimal **seconds**, including sleep_seconds and duration_seconds. Date-only scalars use clinical_date `YYYY-MM-DD`, time_precision `day`, and no measured_start/end. Other readings can supply measured_start; the server derives their clinical_date and original_offset_minutes if absent. A supplied offset must agree with the instant. Unknown IANA zone: omit timezone or send null, set timezone_provenance `offset_only`; UTC `Z` is acceptable for an actual epoch instant, not evidence of a historical local zone. Do not fabricate an IANA zone from the current phone timezone.

Processing receipts are optional metadata, never an approval gate. Recognized optional fields: decoder_version, algorithm_version, raw_digest, source_record_id, qualification; extra source receipt fields are preserved. Native decoder/digest/statistic/coverage/qualification, estimated flags and profile revisions are retained. No placeholder receipt is required.

## 1. Sleep (`sleep_session`)

Required: source_type, measured_start, measured_end, complete. At least a clinical_date or measured_start is required generally; measured_start suffices here. End must follow start. Optional sleep_seconds (null means unavailable), stages, stage_algorithm, firmware, decoder_version, native_source, device_id, acquisition, received_at, main_session, raw_evidence and asset_ids. The shipped source_type values samsung_export/direct_ring/synthetic are accepted unchanged; native source is extracted from native_record. Preserve acquisition independently (DIRECT_RING_DOWNLOAD, LOCAL_MODEL_ANALYSIS, IMPORTED_ARCHIVE); locally processed output can use native_derived where truthful.

Stage DTO: `{start: ISO timestamp, end: ISO timestamp, stage: "awake"|"light"|"deep"|"rem"|"unknown", raw_stage?: string}`. Up to 5,760 intervals. Preserve unknown intervals; gaps count as unknown, never sleep. Overlapping/out-of-session intervals are retained as evidence and not calculated as clinical sleep. Optional reported duration is retained separately from stage-derived duration; **full session span is never substituted for sleep time**.

Index and display on **wake/end date in the end timestamp's original offset**. The server stores the actual onset separately. A complete, non-synthetic, not-future, source-qualified session can populate sleep summaries; partial, synthetic or invalid-stage sessions are accepted as evidence, visible in Received phone records. Future means later than server time +5 minutes; such timestamps are preserved with a future_timestamp reason. A subsequent corrected source revision can become clinical. It is not silently promoted later without a revision. Explicit main_session wins; otherwise the dashboard selects a recorded eligible session with the longest known sleep duration. All sessions remain inspectable.

## 2. Scale/body and context

Send each persisted body value as `scalar_observation` with exact metric_id/unit from metrics.json. Native DIRECT_SCALE uses **direct_scale**, accepted unchanged; MANUAL uses manual; IMPORTED uses imported_file. Weight kg maps to actual Body records, not generic observations; lb is accepted for compatibility and converted exactly using 0.45359237. The original value/unit remain available. A stable, eligible imported weight automatically becomes that day's representative; among automatically selected weights, the earliest recorded measurement wins. Explicit user selections are preserved.

Mappings: WEIGHT→weight/kg, BMI→bmi/**null**, BODY_FAT→body_fat/%, FAT_FREE_MASS→fat_free_mass/kg, SUBCUTANEOUS_FAT→subcutaneous_fat/%, VISCERAL_FAT→visceral_fat/index, WATER→water/%, SKELETAL_MUSCLE→skeletal_muscle/%, MUSCLE_MASS→muscle_mass/kg, BONE_MASS→bone_mass/kg, PROTEIN→protein/%, BMR→bmr/kcal/day, METABOLIC_AGE→metabolic_age/years, FAT_MASS→fat_mass/kg. Native empty BMI unit is accepted as compatibility input and normalized to null. Existing long backend aliases are listed in metrics.json. No missing composition value is invented.

Preserve algorithm_version, estimated, qualification, stable, decoder_version, device_id, profile_revision and optional profile_context/evidence. Estimated values remain marked as calculated. Unstable/negative mass or out-of-range percentages are accepted as evidence, not selected as clinical weight. Weight/BMI/body composition are visible on Body under Received phone records; weight also populates the daily card/trend.

Circumference: kind `circumference`, site waist/hip/chest/arm/thigh, decimal value, unit cm, time/source, optional profile_id/notes. It maps to `circumference_{site}` body observations. `body_profile` requires profile_id/revision/source/time; fields name, height_cm, birth_date, sex, athlete are preserved. `body_goal` requires profile_id/source/time; optional weight_kg/body_fat_percent are nullable decimal strings. Goals and profile context are **accepted evidence**, not measured observations, visible on Body. Source context/evidence is owner-only. Impedance/raw scale packets are source evidence or linked assets, never invented measurements.

## 3. Breathing (`pulmonary_session`)

Required: measured_start, source_type, status (`saved`, `interrupted`, `draft`), trials (0–100). MIR_BLE uses direct_device with native_source MIR_BLE; MANUAL manual; CSV/imported imported_file. Retain title, native source, device_id, firmware, updated_at, notes (up to 20,000 chars), tags, context_history (up to 50), optional selected_trial_id and optional slot morning/noon/evening. Preserve all trials, including incomplete/invalid ones.

Trial DTO: `trial_id`, measured_at ISO instant, values (metric→decimal-string-or-null), complete boolean; optional units, quality, validity, warnings, notes, flow_volume, volume_time, raw_packets, asset_ids. Trial IDs must be distinct within a session. Scalar metric units: fvc/fev1/fev6/vext/fivc=L, pef=L/min, fef2575/fef25/fef50/fef75/pif=L/s, fev1_fvc=%, fet=s. No additional trial metric is declared clinical by this contract: unknown trial metrics are retained and explicitly mark that trial evidence. Never relabel sources or discard those fields.

Curves: `flow_volume: {x_unit:"L", y_unit:"L/s", points:[{x:"0.5",y:"5.2"}]}`; `volume_time: {x_unit:"s",y_unit:"L",points:[{x:"1",y:"2.9"}]}`. Up to 100,000 points per curve; negative inspiratory flow is preserved. These units match native BreathExport and MIR decoder source, so no guessed conversion is necessary. Larger curves/raw packets go into assets as JSON bytes and are linked to the **parent pulmonary session's kind/source_record_id**, including trial-level asset_ids; never mix trial metrics to manufacture a best trial.

Selected trial: explicit selected_trial_id if clinically eligible, otherwise the first eligible source trial when no explicit selection was supplied. Invalid/partial trials remain present with their own clinical_eligible/evidence_reasons. If the session is interrupted/draft or has no eligible trial, the entire session is accepted evidence. An explicit selected ID not in the trials is rejected unknown_selected_trial. For a real known zone, the server can choose morning/noon/evening by recorded local time; offset-only sessions retain no fabricated local slot unless the phone supplies one. An eligible selected trial populates the breathing card; full trials, curves and context are accessible in Received phone records and evidence downloads.

## 4. Workout (`workout`)

Required: measured_start, source_type, activity, state (`active`, `paused`, `completed`, `interrupted`). Optional measured_end and duration_seconds are nullable; never invent an end/duration for active or interrupted work. Preserve notes, version, clock_discontinuity, routine_snapshot, sets, route_points, calories, health_context and details. These structured native objects are retained unchanged; their native nested epoch-millisecond fields retain their original units. Top-level canonical time/duration/interval fields drive dashboard summaries. The existing exporter already supplies joined WorkoutDatabase details; the server reads those fields.

Canonical interval DTO: `{start: ISO, end: ISO|null, kind:"work"|"rest"|"pause"}`. Retain unfinished intervals with null end as source evidence; only complete intervals contribute to clinical duration. Limits: 20,000 intervals, 20,000 sets, 30,000 route points, plus the 5 MiB item-containing batch limit. Larger native detail can be an asset. Native details.zone is acceptable only when recorded with that session; otherwise truthful UTC/offset-only instants are accepted. A completed clock-stable session with recorded duration can display that duration without inventing historical timezone. Clock discontinuity, active/paused/interrupted states, missing end or invalid intervals yield accepted evidence with reasons; no fabricated completed exercise/calories. Calorie method/inputs and health context remain available as reported source data.

## 5. Scalars, quality and units

metrics.json contains **every exact ID and unit**, including bpm, heart_rate/min/max, hr_sample_min/max/mean/count, rmssd, sdnn, respiration_rate, oxygen_saturation/interval_min/interval_max, stress_score/min/max, skin_temperature_processed/nightly_median/baseline/deviation, steps/walking_steps/running_steps/ring_step_subtotal/phone_steps, observed_awakenings, sleep_score and sleep_efficiency. `bpm` unit is accepted as a legacy alias for beats/min with original_unit retained. New body IDs are added to the dashboard registry as reported source values, not newly implemented measurement algorithms.

Accepted source vocabulary: direct_device, direct_scale, manual, imported_file, native_derived, phone_recording, synthetic, unknown. A nonempty unrecognized source string is retained as evidence; a non-string/empty source is malformed and explicitly rejected. Unknown metrics with a valid value/unit are retained as evidence, not silently dropped. Known metric wrong unit is rejected invalid_metric_unit; the encrypted original batch remains delivery evidence. Negative temperatures/deviations and zero counts are supported. Negative non-temperature quantities, zero weight/lung-volume values, and percentages/stress outside 0–100 are preserved as evidence with out_of_range, not removed. qualified=false or validity invalid/unqualified/incomplete/unknown preserves the record as source_unqualified evidence. Processing receipt fields are not required to pass authorization.

## Receipts and evidence access

Receipt item fields: ordinal, outcome, reason, record_id, revision_id, **disposition**. Outcomes remain accepted/duplicate/superseded/conflict/blocked_deleted/rejected/retryable; there is no quarantine outcome. Dispositions: clinical (eligible reported reading/session), evidence (stored and owner-readable source data excluded from clinical summaries), deleted (accepted tombstone), none (no record committed). Evidence has outcome **accepted**, record/revision IDs, and no rejection reason; its payload contains record_status, clinical_eligible=false and evidence_reasons. Do not endlessly resend accepted evidence. An explicit corrected revision can change disposition. rejected gives an actual machine-readable reason; pending/retryable retains the immutable outbox entry. `clinical_acceptance` is at least one newly accepted clinical item, not “all items valid.”

The dashboard's Body, Breathing and Sleep & Activity pages each include **Received phone records** with source status, all preserved fields, pagination and linked downloads. Owner session APIs: GET `/api/v1/phone/records?domain=body|breathing|sleep&from=YYYY-MM-DD&to=YYYY-MM-DD[&cursor=...]`; GET `/api/v1/phone/records/{record_id}/assets/{asset_id}` downloads original bytes. These are private owner/dashboard routes, deliberately excluded from the public phone hostname. The phone API key does not grant clinical reads.

Assets: POST raw bytes to `/api/v1/ingestion/assets` (not multipart), max 25 MiB. Headers X-API-Key, X-Source-Namespace, X-Source-Record-ID, X-Source-Kind identify the **parent item**. Provision a namespace for each device. Use response id in top-level or nested asset_ids; maximum 100 unique assets per item. Upload assets first, then parent batch. Cross-source/identity references fail asset_not_ready. Every supported kind can have associated assets. Repeated identical identity+bytes returns the same asset. Asset bytes stay opaque; store a content description/axis units/format in the parent or trial. Download is attachment/application/octet-stream, not executable HTML.

Retention: encrypted clinical/source records, batch evidence and opaque assets remain on the Pi until deletion/account cleanup. No cloud data store or off-device backup is introduced. Record tombstone hides the record and linked assets immediately and schedules encrypted record/asset files for purge within 24 hours under existing retention. Parent association is enforced and asset downloads check current parent access. Unattached assets are not clinical sync and remain retained until account cleanup. Immutable batch evidence may contain the original submitted payload and is retained as ingestion evidence until account cleanup; batch receipts never return those values. Existing account deletion clears the associated encrypted data. There is no new recurring credential maintenance.
