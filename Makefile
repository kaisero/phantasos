# Local SDK generation pipeline — OpenAPI Generator (python / Pydantic v2).
# No Docker, no global installs: Java (JRE 11+) + uv are the only prerequisites.
#
#   make build      # preprocess -> generate -> patch -> smoke  (the full pipeline)
#   make generate   # just (re)run the generator
#   make smoke      # compile + import the generated package
#   make ops        # report generated operation count (parity check: expect 95)
#   make clean      # remove generated SDK
#   make help       # list targets
#
# Migration branch: the OAG output lives in $(OUT) alongside the prototype's
# prisma-browser-sdk/ until cutover (see MIGRATION_PLAN.md).

OAG_VERSION := 7.7.0
JAR         := .tools/openapi-generator-cli-$(OAG_VERSION).jar
JAR_URL     := https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/$(OAG_VERSION)/openapi-generator-cli-$(OAG_VERSION).jar

SPEC_SRC := prismaBrowserAPIspecWithSecurityPolicy.yaml
SPEC_PP  := prismaBrowserAPIspec.preprocessed.yaml
OUT      := prisma-browser-sdk
PKG      := prisma_browser
PYV      := 3.12

UV  := uv run --no-project --python $(PYV)
export PATH := $(HOME)/.local/bin:$(PATH)

.PHONY: all build help check-java jar preprocess generate patch overlay smoke ops test clean clobber

help:
	@grep -E '^[a-z][a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

all: build

build: preprocess generate patch overlay smoke ## Full pipeline: preprocess -> generate -> patch -> overlay -> smoke

check-java:
	@command -v java >/dev/null 2>&1 || { echo "ERROR: java (JRE 11+) not found on PATH"; exit 1; }

jar: $(JAR) ## Ensure the pinned OpenAPI Generator jar is present
$(JAR):
	@mkdir -p .tools
	@echo ">> fetching openapi-generator-cli $(OAG_VERSION)"
	curl -fsSL -o $@ $(JAR_URL)

preprocess: $(SPEC_PP) ## Clean the OpenAPI spec (generator-agnostic)
$(SPEC_PP): $(SPEC_SRC) preprocess_spec.py
	$(UV) --with ruamel.yaml python preprocess_spec.py

generate: check-java $(JAR) $(SPEC_PP) ## Run the generator (python/Pydantic, sync)
	@echo ">> generating $(PKG) into $(OUT)/"
	java -jar $(JAR) generate \
	  -g python \
	  -i $(SPEC_PP) \
	  -o $(OUT) \
	  --package-name $(PKG) \
	  --additional-properties=library=urllib3,disallowAdditionalPropertiesIfNotPresent=false \
	  --global-property=modelDocs=false,apiDocs=false,modelTests=false,apiTests=false \
	  --inline-schema-options RESOLVE_INLINE_ENUMS=true \
	  >/dev/null

patch: ## Apply idempotent post-generation fixups (codegen-bug patches)
	$(UV) python apply_patches.py $(OUT)/$(PKG)

overlay: ## Copy the hand-written overlay into the generated package (extras/)
	rm -rf $(OUT)/$(PKG)/extras
	cp -r overlay $(OUT)/$(PKG)/extras
	find $(OUT)/$(PKG)/extras -name __pycache__ -type d -prune -exec rm -rf {} +

smoke ops: ## Compile + import every module and report operation count (expect 95)
	@$(UV) --with pydantic --with urllib3 --with python-dateutil --with typing_extensions \
	  python tools_smoke.py $(OUT) $(PKG)

test: ## Run the offline pytest suite (no live calls)
	$(UV) --with pytest --with pydantic --with urllib3 --with python-dateutil --with typing_extensions \
	  python -m pytest tests/ -q

clean: ## Remove the generated SDK
	rm -rf $(OUT)

clobber: clean ## Remove generated SDK + preprocessed spec + jar
	rm -f $(SPEC_PP)
	rm -rf .tools
