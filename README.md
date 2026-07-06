# AI-Agentic Metadata-Driven ETL Platform for Semiconductor Operations

A JSON-native, metadata-driven ETL platform that ingests equipment/MES/SPC/APC
telemetry from Amazon S3, dynamically interprets pipeline behavior from an
Aurora PostgreSQL metadata repository, and loads curated data into analytical
target tables — with an AI-agentic layer handling schema-drift detection,
error classification, self-healing, documentation, and observability.

This repository implements the design in
`HLD_AI_Agentic_Platform_for_SemiConductor_Operations_Metadata_based_design_-_V2.docx`.

## Architecture

```
Equipment / MES / SPC / APC / ERP
        │  JSON Documents
        ▼
   Amazon S3 ──▶ EventBridge Trigger ──▶ AWS Step Functions
        │                                     │
        │                                     ▼
        │                      Metadata Repository (Aurora PostgreSQL)
        │                                     │
        │                                     ▼
        └────────────────────────────▶  AWS Glue (PySpark)
                                              │
                              ┌───────────────┴───────────────┐
                              ▼                                ▼
                     Transformation Engine              AI Agent Layer
                              │
                              ▼
                       Validation Engine
                              │
                              ▼
                         Load Engine
                              │
                              ▼
                     Aurora PostgreSQL
                              │
                              ▼
                     Audit & Monitoring
```

Business transformations remain **deterministic and metadata-driven**. AI
agents are strictly advisory/operational (Section 5 of the HLD) — they never
replace the transformation, validation, or load engines.

## Repository layout

```
sql/                          Metadata repository + target schema DDL, seed data
etl_platform/
  config.py                   Environment-driven configuration
  db/
    connection.py              SQLAlchemy engine/session management
    metadata_repository.py      Reads metadata.* tables into a PipelineDefinition
  core/
    schema_validator.py         JSON Schema validation + drift detection
    jsonpath_extractor.py       JSONPath extraction & nested-array flattening
    transformation_engine.py    Metadata-driven transformation rule registry
    lookup_engine.py             Reference-data lookups with TTL cache
    validation_engine.py        NOT_NULL / RANGE / ENUM / etc. rule engine
    load_engine.py               APPEND / MERGE / UPSERT / SCD1 / SCD2 loader
    audit.py                    Batch-level audit logging
    error_handler.py            Error repository + self-healing enqueue
  agents/                      AI-Agentic Framework (Section 5)
    input_validation_agent.py
    schema_drift_agent.py
    transformation_advisor_agent.py
    error_classification_agent.py
    self_healing_agent.py
    documentation_agent.py
    observability_agent.py
  pipeline/
    orchestrator.py             End-to-end ETL Processing Flow (Section 4)
  aws/
    s3_client.py                 S3 read/archive helpers
    glue_job_entrypoint.py        AWS Glue job entrypoint
infra/
  step_functions/etl_state_machine.asl.json   Step Functions state machine
  eventbridge_rule.json                        S3 -> EventBridge -> Step Functions
docker/docker-compose.yml       Local Aurora-compatible Postgres for dev/test
sample_data/sample_lot_wafer.json   Example plasma-etch Lot/Wafer JSON payload
tests/                          Unit tests for the deterministic engine modules
```

## Getting started (local development)

1. **Start a local metadata + target database:**

   ```bash
   make db-up
   ```

   This spins up Postgres and automatically runs every script in `sql/` in
   order (schema DDL, then the sample `plasma_etch_wafer_ingest` pipeline
   seed data).

2. **Install dependencies (pip):**

  Create and activate a virtual environment, then install packages.

  ```bash
  python -m venv .venv
  .venv\Scripts\activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  ```

  Installed packages (`requirements.txt`):

  ```bash
  pip install SQLAlchemy==2.0.35 psycopg2-binary==2.9.9 jsonschema==4.23.0 jsonpath-ng==1.6.1 boto3==1.35.36 anthropic==0.36.2 python-dotenv==1.0.1 pytest==8.3.3 pytest-cov==5.0.0 ruff==0.6.9 moto==5.0.14
  ```

3. **Copy `.env.example` to `.env`** and adjust as needed (defaults match the
   docker-compose service).

4. **Run the sample pipeline against the seeded S3-shaped sample data:**

   The Glue entrypoint (`etl_platform/aws/glue_job_entrypoint.py`) expects a
   real S3 bucket in AWS; for a fully local dry run, drive the orchestrator
   directly:

   ```python
   from etl_platform.pipeline.orchestrator import PipelineOrchestrator
   import json

   orchestrator = PipelineOrchestrator("plasma_etch_wafer_ingest")
   payload = json.load(open("sample_data/sample_lot_wafer.json"))
   result = orchestrator.run_batch([("sample_lot_wafer.json", payload)])
   print(result)
   ```

5. **Run the test suite** (pure-logic modules; no DB required):

   ```bash
   make test
   ```

## Onboarding a new JSON source (zero-code)

Per the HLD's core objective, adding a new source requires **only metadata
inserts** — no code changes:

1. Insert a row into `metadata.pipeline_master` and `metadata.source_config`.
2. Register the JSON Schema in `metadata.json_schema_registry` and its field
   definitions in `metadata.source_json_schema`.
3. Define `metadata.json_path_mapping` (and `metadata.json_flatten_config` if
   the payload has nested arrays to explode).
4. Add any `metadata.transformation_rules`, `metadata.validation_rules`,
   `metadata.lookup_config`, and `metadata.load_config` rows needed.
5. Point EventBridge at the new S3 prefix (`infra/eventbridge_rule.json`).

See `sql/004_seed_sample_pipeline.sql` for a worked example.

## AI-Agentic Framework

| Agent | Responsibility |
|---|---|
| Input Validation Agent | Validate JSON structure, mandatory fields, data types |
| Schema Drift Agent | Detect schema evolution and recommend metadata updates |
| Transformation Advisor | Recommend new mappings and transformations |
| Error Classification Agent | Classify failures and determine root cause |
| Self-Healing Agent | Retry failed payloads using recovery metadata |
| Documentation Agent | Generate metadata documentation |
| Observability Agent | Analyze pipeline health and operational metrics |

Agents call the configured LLM (`AGENT_MODEL_PROVIDER` / `AGENT_MODEL_NAME` in
`.env`, defaulting to Anthropic's Claude) but degrade gracefully to
deterministic heuristics or no-ops when `AGENTS_ENABLED=false` — the
pipeline's correctness never depends on AI availability.

## Self-healing framework

Individual failed JSON payloads (not whole batches) are written to
`metadata.error_record` and, when classified as recoverable, enqueued into
`metadata.self_healing_queue` with a recovery policy: `IMMEDIATE_RETRY`,
`DELAYED_RETRY`, `DEPENDENCY_RETRY`, `MANUAL_REVIEW`, or
`PERMANENT_REJECTION`. `SelfHealingAgent.run()` drains due items and retries
only those payloads.

## Security & governance notes

- Treat metadata as the system of record for pipeline behavior.
- Retain raw JSON payloads for replay, lineage, and audit.
- AI agents are restricted to advisory/operational functions; business
  transformations stay deterministic and version-controlled.
- Use IAM roles, AWS KMS, and Secrets Manager for credentials in production —
  none of this repository's code embeds credentials; everything is sourced
  from environment variables (see `.env.example`).
