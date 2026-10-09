# KitaabOnDemand monorepo tasks. Run `make help` for the list.
#
# Tool overrides: FLUTTER, UV, NPM. Set STRICT=1 (as CI does) to fail instead
# of skipping steps whose toolchain is missing (the Android SDK).
# Set DOCKER_REGISTRY=mirror.gcr.io if Docker Hub rate-limits you, and
# BUILD_CA_FILE=./docker/.build-ca.crt (relative to infra/, inside the repo) behind
# a TLS-intercepting proxy.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

API := services/api
WEB := apps/web
MOBILE := apps/mobile
CONTRACTS := packages/contracts
COMPOSE := docker compose -f infra/docker-compose.yml
FLUTTER ?= flutter
UV ?= uv
NPM ?= npm
STRICT ?= 0
FLAVOR ?= prod

# The uv in some sandboxes warns about this deprecated variable on every call.
unexport UV_NATIVE_TLS

# Test services, reachable from the host.
export TEST_DATABASE_URL ?= postgresql+psycopg://kitaab:kitaab@localhost:5432/kitaab_test
export TEST_REDIS_URL ?= redis://localhost:6379/15
export TEST_S3_ENDPOINT_URL ?= http://localhost:9000

# Coverage gates (brief section 7).
DOMAIN_COVERAGE := 85
OVERALL_COVERAGE := 75
DOMAIN_MODULES := */kitaab/domain/*,*/kitaab/domain/**/*

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- stack

.PHONY: up down deps-up deps-down logs seed demo
up: ## Build and start the full stack (API :8000, portal :8080)
	$(COMPOSE) --profile app up -d --build --wait

down: ## Stop the stack
	$(COMPOSE) --profile app --profile clamav down --remove-orphans

deps-up: ## Start only Postgres, Redis and MinIO for host-side development and tests
	$(COMPOSE) up -d --wait postgres redis minio

deps-down: ## Stop Postgres, Redis and MinIO
	$(COMPOSE) stop postgres redis minio

logs: ## Follow logs of the app services
	$(COMPOSE) --profile app logs -f api worker beat

seed: ## Seed cities, placeholder pricing and the first admin
	$(COMPOSE) --profile app run --rm api kitaab seed

demo: up ## Start the stack and load demo data
	$(COMPOSE) --profile app run --rm api kitaab seed --demo
	@echo ""
	@echo "Portal: http://localhost:8080   API docs: http://localhost:8000/docs"
	@echo "Demo logins are printed above by the seed command."

# ---------------------------------------------------------------- quality

.PHONY: lint typecheck test verify
lint: api-lint web-lint mobile-lint ## Lint every project

typecheck: api-typecheck web-typecheck ## Type-check every project (Dart is checked by mobile-lint)

test: api-test web-test mobile-test ## Run every unit and integration test suite

verify: lint typecheck contracts-check test build ## Everything CI runs: lint, types, tests, builds
	@echo "verify: all checks passed"

# ---------------------------------------------------------------- api

.PHONY: api-install api-lint api-typecheck api-test api-audit api-dev
api-install:
	cd $(API) && $(UV) sync --frozen

api-lint: api-install ## Lint the API (ruff)
	cd $(API) && $(UV) run ruff check . && $(UV) run ruff format --check .

api-typecheck: api-install ## Type-check the API (mypy)
	cd $(API) && $(UV) run mypy

api-test: api-install deps-up ## API unit and integration tests with coverage gates
	cd $(API) && $(UV) run pytest --cov --cov-report=term --cov-report=xml
	cd $(API) && $(UV) run coverage report --fail-under=$(OVERALL_COVERAGE) > /dev/null \
		|| { echo "Overall coverage below $(OVERALL_COVERAGE)%"; exit 1; }
	cd $(API) && if $(UV) run coverage report --include='$(DOMAIN_MODULES)' > /dev/null 2>&1; then \
		$(UV) run coverage report --include='$(DOMAIN_MODULES)' --fail-under=$(DOMAIN_COVERAGE) \
		|| { echo "Domain coverage below $(DOMAIN_COVERAGE)%"; exit 1; }; fi

api-audit: api-install ## Audit Python dependencies for known vulnerabilities
	cd $(API) && $(UV) export --frozen --no-dev --no-hashes --no-emit-project > /tmp/kitaab-requirements.txt
	cd $(API) && $(UV) run pip-audit --strict -r /tmp/kitaab-requirements.txt

api-dev: deps-up ## Run the API on the host with auto-reload
	cd $(API) && DEV_TOOLS_ENABLED=true $(UV) run uvicorn kitaab.main:app --reload --port 8000

# ---------------------------------------------------------------- contracts

.PHONY: contracts contracts-check
contracts: api-install ## Regenerate openapi.json and the typed web client
	cd $(API) && $(UV) run python -m kitaab.openapi_export ../../$(CONTRACTS)/openapi.json
	cd $(WEB) && $(NPM) run gen:api

contracts-check: api-install web-install ## Fail if openapi.json or the web client is stale
	cd $(API) && $(UV) run python -m kitaab.openapi_export --check ../../$(CONTRACTS)/openapi.json
	cd $(WEB) && cp src/api/schema.d.ts /tmp/kitaab-schema.d.ts && $(NPM) run --silent gen:api > /dev/null \
		&& diff -q /tmp/kitaab-schema.d.ts src/api/schema.d.ts \
		|| { echo "src/api/schema.d.ts is stale: run 'make contracts'"; cp /tmp/kitaab-schema.d.ts src/api/schema.d.ts; exit 1; }

# ---------------------------------------------------------------- web

.PHONY: web-install web-lint web-typecheck web-test web-build web-e2e web-audit
web-install: $(WEB)/node_modules/.installed

$(WEB)/node_modules/.installed: $(WEB)/package-lock.json
	cd $(WEB) && $(NPM) ci --no-audit --no-fund
	touch $@

web-lint: web-install ## Lint the web portal (eslint, prettier)
	cd $(WEB) && $(NPM) run lint

web-typecheck: web-install ## Type-check the web portal
	cd $(WEB) && $(NPM) run typecheck

web-test: web-install ## Web unit and component tests with coverage
	cd $(WEB) && $(NPM) run test:coverage

web-build: web-install ## Production build of the web portal
	cd $(WEB) && $(NPM) run build
	@du -sh $(WEB)/dist | awk '{print "web dist size: " $$1}'

web-audit: web-install ## Audit npm dependencies
	cd $(WEB) && $(NPM) audit --omit=dev --audit-level=high

# ---------------------------------------------------------------- mobile

.PHONY: mobile-install mobile-lint mobile-test mobile-build mobile-audit
mobile-install: $(MOBILE)/.dart_tool/.installed

$(MOBILE)/.dart_tool/.installed: $(MOBILE)/pubspec.yaml $(MOBILE)/pubspec.lock
	cd $(MOBILE) && $(FLUTTER) pub get --enforce-lockfile
	touch $@

mobile-lint: mobile-install ## Analyze and format-check the Flutter app
	cd $(MOBILE) && dart format --output=none --set-exit-if-changed $$(ls -d lib test integration_test 2>/dev/null)
	cd $(MOBILE) && $(FLUTTER) analyze --fatal-infos

mobile-test: mobile-install ## Flutter unit and widget tests
	cd $(MOBILE) && $(FLUTTER) test --coverage

mobile-build: mobile-install ## Release Android App Bundle (needs the Android SDK)
	@if [ -n "$${ANDROID_HOME:-$${ANDROID_SDK_ROOT:-}}" ]; then \
		cd $(MOBILE) && $(FLUTTER) build appbundle --release --flavor $(FLAVOR) \
			--dart-define-from-file=config/$(FLAVOR).json && \
		ls -l build/app/outputs/bundle/$(FLAVOR)Release/*.aab | awk '{print "AAB size (bytes): " $$5}'; \
	elif [ "$(STRICT)" = "1" ]; then \
		echo "mobile-build: Android SDK not found (set ANDROID_HOME)"; exit 1; \
	else \
		echo "mobile-build: SKIPPED, no Android SDK on this machine (CI builds the AAB)"; \
	fi

mobile-audit: mobile-install ## Report outdated or discontinued Flutter dependencies
	cd $(MOBILE) && $(FLUTTER) pub outdated --no-dev-dependencies --show-all

# ---------------------------------------------------------------- build

.PHONY: build images
build: web-build mobile-build images ## Build every artifact

images: ## Build the Docker images (api, worker, beat, web, minio)
	$(COMPOSE) --profile app build

# ---------------------------------------------------------------- end to end

.PHONY: e2e load
e2e: ## Start the full stack with mock providers and run the end-to-end scenarios
	./tests/e2e/run.sh

load: ## Run the Locust load test against a running stack (see docs/PERF.md)
	./tests/load/run.sh
