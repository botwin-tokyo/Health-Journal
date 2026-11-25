.PHONY: backend-check contract-check domain-tests authorization-tests import-tests recovery-rehearsal release-evidence
backend-check:
	uv run python backend/manage.py check
	uv run python backend/manage.py makemigrations --check --dry-run
	uv run ruff check backend tests scripts
contract-check:
	uv run python scripts/check_security_contracts.py
	uv run python -c "import json; from openapi_spec_validator import validate; validate(json.load(open('contracts/openapi.yaml')))"
domain-tests:
	uv run pytest -q tests/backend
authorization-tests:
	uv run pytest -q tests/integration/test_access_policy.py tests/integration/test_identity.py tests/integration/test_uploader.py
import-tests:
	uv run pytest -q tests/test_security_operations.py tests/backend/test_calculations.py
recovery-rehearsal:
	uv run python backend/manage.py health03_restore_verify --environment=restore --backup-set=$(BACKUP_SET)
release-evidence:
	python3 scripts/build_release_evidence.py --release-id=$(RELEASE_ID) --results=$(RESULTS) --output=$(OUTPUT)

client-check:
	tsc --noEmit --strict --target ES2020 --lib ES2020,DOM frontend/generated/backend.ts frontend/generated/client.ts
local-parser-acceptance:
	sudo bash scripts/run_parser_acceptance.sh
local-recovery-rehearsal:
	uv run python scripts/local_recovery_rehearsal.py
capacity-check:
	uv run python backend/manage.py benchmark_backend --measure-only --output $(OUTPUT)

.PHONY: pi-acceptance
pi-acceptance:
	HEALTH03_ENV=test uv run --frozen python backend/manage.py check
	HEALTH03_ENV=test uv run --frozen python backend/manage.py makemigrations --check --dry-run
	uv run --frozen python scripts/check_local_kms.py
	HEALTH03_ENV=test HEALTH03_REAL_KMS_TESTS=1 uv run --frozen pytest -q
