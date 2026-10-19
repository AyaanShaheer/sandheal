# SandHeal

**Proof-Driven Autonomous CI/CD Repair Agent**

SandHeal is an autonomous software-repair system designed to investigate failed CI/CD pipelines, reproduce failures in isolated execution environments, explore multiple repair hypotheses, verify repairs through real test execution, and ultimately produce evidence-backed pull requests.

The core idea is simple:

> **The AI proposes repairs. Execution proves which repair works.**

Instead of asking an LLM for one patch and trusting its judgment, SandHeal is designed to treat software repair as an executable search problem.

---

## Project Status

SandHeal is currently being built incrementally with a production-oriented architecture.

### Implemented

* FastAPI application foundation
* Configuration management using Pydantic Settings
* Health endpoint
* Typed `RepairRun` domain model
* Explicit repair lifecycle state machine
* Persisted lifecycle transitions
* GitHub Actions `workflow_run` webhook ingestion
* HMAC-SHA256 webhook signature verification
* Fail-closed webhook secret validation
* GitHub failure-event normalization
* SQLAlchemy async database layer
* SQLite local development database
* Persistent `RepairRun` records
* Persistent asynchronous `RepairJob` records
* Repository abstraction for persistence
* Idempotent GitHub delivery handling
* Database-enforced uniqueness constraints
* Transactional creation of `RepairRun` + `RepairJob`
* Application-level logging
* Request correlation IDs
* Global error handling
* Readiness endpoint
* Database-enforced status constraints
* Persisted job lifecycle
* Alembic schema migrations
* CI pipeline
* Container image
* Automated test suite
* Coverage reporting
* Ruff linting and formatting

### Planned

* Asynchronous job dispatch
* Redis-backed job transport
* Worker execution layer
* GitHub repository/file retrieval
* Failure reproduction
* NVIDIA Nemotron reasoning
* Tavily technical research
* ConTree sandbox execution
* Parallel repair hypothesis execution
* Verification and regression-test generation
* Automated GitHub pull-request generation
* Web dashboard and live execution visualization
* Production PostgreSQL
* Alembic database migrations
* Deployment to Nebius infrastructure

---

# Why SandHeal?

Modern CI/CD systems can detect a failure quickly, but the remediation loop often remains manual.

A typical workflow looks like:

```text
CI failure
    ↓
Developer reads logs
    ↓
Investigates root cause
    ↓
Reproduces failure locally
    ↓
Writes a possible fix
    ↓
Runs tests
    ↓
Fix fails
    ↓
Reverts / modifies patch
    ↓
Runs tests again
    ↓
Eventually creates PR
```

SandHeal aims to automate the repetitive investigation and experimentation loop.

Its long-term workflow is:

```text
CI failure
    ↓
Reproduce failure
    ↓
Analyze root cause
    ↓
Research when necessary
    ↓
Generate repair hypotheses
    ↓
Execute hypotheses in isolated environments
    ↓
Compare real test results
    ↓
Select verified repair
    ↓
Generate regression protection
    ↓
Run final verification
    ↓
Create evidence-backed PR
```

The system is intentionally designed so that **model output is treated as a hypothesis rather than proof**.

---

# Core Design Principle

## AI proposes. Execution decides.

LLMs are probabilistic systems.

Code execution and automated tests provide deterministic evidence.

SandHeal combines these two properties:

```text
Reason
   ↓
Hypothesize
   ↓
Execute
   ↓
Observe
   ↓
Compare
   ↓
Verify
   ↓
Act
```

This is the central design philosophy of the project.

---

# High-Level Architecture

The target architecture is:

```text
                           ┌───────────────────────┐
                           │       GitHub          │
                           │                       │
                           │ Repository            │
                           │ GitHub Actions        │
                           │ Pull Requests         │
                           └───────────┬───────────┘
                                       │
                                 CI failure
                                       │
                                       ▼
                           ┌───────────────────────┐
                           │     FastAPI API       │
                           │                       │
                           │ Webhook ingestion     │
                           │ API endpoints         │
                           └───────────┬───────────┘
                                       │
                                       ▼
                           ┌───────────────────────┐
                           │   Application Layer   │
                           │                       │
                           │ RepairRunService      │
                           │ Workflow orchestration│
                           └───────────┬───────────┘
                                       │
                         ┌─────────────┴─────────────┐
                         │                           │
                         ▼                           ▼
                ┌─────────────────┐         ┌─────────────────┐
                │   RepairRun     │         │   RepairJob     │
                │                 │         │                 │
                │ Lifecycle       │         │ Async work      │
                │ State           │         │ Status          │
                └────────┬────────┘         └────────┬────────┘
                         │                           │
                         └─────────────┬─────────────┘
                                       │
                                    Database
                                       │
                                       ▼
                              ┌─────────────────┐
                              │    PostgreSQL   │
                              │   production    │
                              └─────────────────┘


                         Future Execution Path

                                       │
                                       ▼
                              ┌─────────────────┐
                              │ Redis / Worker  │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ Agent Runtime   │
                              └────────┬────────┘
                                       │
                       ┌───────────────┼────────────────┐
                       │               │                │
                       ▼               ▼                ▼
                 Nemotron           Tavily          ConTree
                 Reasoning          Research        Sandboxes
                       │               │                │
                       └───────────────┼────────────────┘
                                       │
                                       ▼
                              Repair hypotheses
                                       │
                                       ▼
                         Parallel sandbox execution
                                       │
                                       ▼
                               Test verification
                                       │
                                       ▼
                              Regression testing
                                       │
                                       ▼
                              GitHub Pull Request
```

---

# Current Architecture

The currently implemented backend follows clear separation of responsibilities.

```text
app/
├── api/
│   ├── errors.py
│   ├── github.py
│   └── health.py
│
├── application/
│   └── repair_runs.py
│
├── core/
│   ├── config.py
│   ├── logger.py
│   └── middleware.py
│
├── domain/
│   ├── enums.py
│   ├── errors.py
│   ├── failures.py
│   ├── job_enums.py
│   └── models.py
│
├── infrastructure/
│   ├── database.py
│   ├── migrations.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── repair_run.py
│   │   └── repair_job.py
│   │
│   └── repositories/
│       ├── repair_run.py
│       └── repair_job.py
│
├── integrations/
│   └── github/
│       ├── models.py
│       ├── security.py
│       └── webhook.py
│
└── migrations/               Alembic environment and revisions
    ├── env.py
    ├── script.py.mako
    └── versions/
```

---

# Architecture Responsibilities

## API Layer

The API layer deals with HTTP-specific concerns:

```text
request
headers
authentication/signatures
HTTP responses
dependency injection
error handling
```

It should not contain business logic or direct SQL operations.

### Error handling

Every response carries a correlation ID, taken from the incoming
`X-Request-ID` header when present and generated otherwise:

```text
X-Request-ID: 3f9c1c2e-...
```

The ID is returned in the response header and included in the body of
every error response, so a delivery reported by GitHub can be traced
through the server logs.

```text
GET /does-not-exist  →  404
{
  "detail": "Not Found",
  "request_id": "3f9c1c2e-..."
}
```

An unexpected server error is logged with its traceback and returned as a
generic body. Internals are never leaked to the caller:

```text
GET /boom  →  500
{
  "detail": "Internal Server Error",
  "request_id": "3f9c1c2e-..."
}
```

### Liveness and readiness

```text
GET /health  →  {"status": "ok"}          liveness only
GET /ready   →  {"status": "ready"}        verifies the database
```

`/health` intentionally does not touch any dependency, so a database
outage never restarts the process. `/ready` reports the database as
unavailable with HTTP 503, so a load balancer can take the instance out
of rotation.

---

## Application Layer

The application layer coordinates business workflows.

For example:

```text
GitHub failure
      ↓
RepairRunService
      ↓
create RepairRun
      +
create RepairJob
      ↓
single transaction
```

This layer will eventually coordinate the agent workflow as the system grows.

---

## Domain Layer

The domain layer contains business concepts independent of infrastructure.

Current examples:

```text
RepairRun
RunStatus
RepairJob
RepairJobStatus
WorkflowFailure
state transition rules
```

The `RepairRun` lifecycle is explicitly modeled rather than represented by arbitrary strings.

Current lifecycle:

```text
RECEIVED
    ↓
REPRODUCING
    ↓
ANALYZING
    ↓
RESEARCHING
    ↓
GENERATING_REPAIRS
    ↓
EXECUTING
    ↓
VERIFYING
    ↓
CREATING_PR
    ↓
COMPLETED
```

Terminal failure/cancellation paths are also represented.

The `RepairJob` lifecycle follows the same pattern:

```text
PENDING
    ↓
PROCESSING
    ↓
COMPLETED
```

A failed job is not terminal: it can return to `PENDING` so the worker
retries it. That is the difference between a run, which ends, and a job,
which can be requeued.

---

## Infrastructure Layer

The infrastructure layer handles persistence and external implementation details.

Current technology:

```text
SQLAlchemy
SQLite
AsyncSession
Repository pattern
```

### Database constraints

Invariants that matter are enforced by the database, not only by the
application. Both status columns are constrained:

```text
CHECK (status IN ('received', 'reproducing', ...))
CHECK (status IN ('pending', 'processing', ...))
```

A worker that writes a typo such as `generating_repair` is rejected by
the database instead of storing a value that would later crash every
read.

### Single write path

`RepairRunService` is the only supported way to create a repair run.
The standalone repository methods that create a run or a job on their own
are deprecated, because they break the invariant that a run always has
its initial job:

```text
RepairRun exists  ⇔  its initial RepairJob exists
```

Production target:

```text
PostgreSQL
```

### Schema migrations

The schema is managed by Alembic. The migration scripts live in
`app/migrations/versions/` and are applied automatically when the
application starts:

```text
alembic upgrade head
```

To create a migration after changing a model:

```bash
alembic revision --autogenerate -m "add repair hypothesis table"
```

The `Runtime` CI job and the test suite both verify that the migrations
and the ORM models agree, so the two can never silently drift apart.

A database that was created before Alembic existed already carries the
schema but has no version. SandHeal detects that and stamps it with the
baseline revision instead of trying to create tables that already exist.

Set `AUTO_MIGRATE=false` to skip migrations and create the tables from
the ORM metadata instead.

---

## Integration Layer

External systems are isolated behind integration-specific code.

Currently:

```text
GitHub webhook integration
```

Future integrations:

```text
GitHub API
Nebius Token Factory
ConTree
Tavily
Redis
```

This prevents external API structures from leaking throughout the application.

The integration layer does not depend on the web framework. It raises
`InvalidWebhookPayloadError`, a domain error, and the API layer decides
which status code to return:

```text
app/integrations/github/webhook.py  →  InvalidWebhookPayloadError
app/api/github.py                   →  400
```

The failure model itself lives in the domain as `WorkflowFailure`, so
neither the domain nor the persistence layer depends on a provider.
`app.integrations.github.models.GitHubWorkflowFailure` remains as an
alias for backwards compatibility.

---

# GitHub Webhook Flow

SandHeal currently accepts GitHub Actions `workflow_run` events.

The system specifically looks for:

```text
event = workflow_run
action = completed
conclusion = failure
```

The processing flow is:

```text
GitHub
   ↓
POST /webhooks/github
   ↓
Check the request body size and content type
   ↓
Read raw request body
   ↓
Verify HMAC-SHA256 signature
   ↓
Validate GitHub event
   ↓
Normalize payload
   ↓
RepairRunService
   ↓
Persist RepairRun
   ↓
Persist RepairJob
   ↓
Return HTTP response
```

Unrelated successful workflows are ignored.

### Input limits

The endpoint refuses traffic it cannot use:

```text
Body larger than 1 MiB      →  413
Content-Type not JSON       →  415
Delivery ID longer than 64  →  400
```

The delivery ID is length checked because it is stored in a `VARCHAR(255)`
column, and PostgreSQL enforces that length while SQLite does not.

---

# Webhook Security

GitHub webhook requests are verified using:

```text
X-Hub-Signature-256
```

SandHeal calculates the expected HMAC-SHA256 signature against the **raw request bytes** and compares it using a constant-time comparison.

This prevents the application from accepting forged webhook requests.

### Fail-closed secret handling

An HMAC keyed with an empty string is computable by anyone, so an unset secret must never be able to produce a valid signature.

SandHeal therefore treats the webhook secret as **not configured** when it is empty or a known placeholder such as the `replace-me` value shipped in `.env.example`.

When the secret is not configured:

```text
POST /webhooks/github  →  503 {"detail": "GitHub webhook secret is not configured."}
```

The application also refuses to start in the `production` environment:

```text
RuntimeError: GITHUB_WEBHOOK_SECRET is not configured ...
```

In `development` the application still starts, so the rest of the stack remains usable, but the misconfiguration is reported as an error and every delivery is rejected.

The normalized internal model intentionally hides GitHub's raw webhook structure from the rest of the application.

For example:

```text
GitHub:
workflow_run.head_sha

SandHeal:
commit_sha
```

---

# Idempotency

GitHub webhook deliveries must not result in duplicate SandHeal executions.

Each webhook delivery is identified using:

```text
X-GitHub-Delivery
```

The database stores this as:

```text
delivery_id
```

and enforces:

```text
UNIQUE(delivery_id)
```

Therefore:

```text
Delivery A
    ↓
RepairRun A
    ↓
RepairJob A
```

A repeated delivery:

```text
Delivery A
    ↓
existing RepairRun A
    ↓
NO second RepairJob
```

This is particularly important because future repair jobs will be expensive operations involving AI inference and sandbox execution.

---

# Transactional Guarantees

SandHeal treats creation of a repair run and its initial asynchronous job as one logical operation.

Target invariant:

```text
RepairRun exists
        ⇔
initial RepairJob exists
```

The service creates both within one database transaction:

```text
BEGIN
   │
   ├── INSERT RepairRun
   │
   ├── INSERT RepairJob
   │
   └── COMMIT
```

If an error occurs:

```text
ROLLBACK
```

so the application doesn't leave behind a run with no job.

---

# Technology Stack

## Backend

```text
Python 3.12+
FastAPI
Uvicorn
Pydantic
Pydantic Settings
```

## Persistence

```text
SQLAlchemy 2.x
SQLite              # local development
PostgreSQL           # production target
Alembic              # planned
```

## Testing

```text
Pytest
HTTPX
AnyIO
```

## Code Quality

```text
Ruff
Git
GitHub
```

## Planned asynchronous infrastructure

```text
Redis
Worker processes
```

## Planned AI stack

```text
NVIDIA Nemotron
Nebius Token Factory
```

## Planned research/tooling

```text
Tavily
```

## Planned sandbox execution

```text
Nebius Token Factory Sandboxes
ConTree
```

## Planned frontend

```text
Next.js
React
TypeScript
Tailwind CSS
```

---

# Target Agentic Architecture

Once the execution layer is implemented, SandHeal will evolve into several specialized components.

## Failure Analyst

Responsible for:

```text
CI logs
stack traces
repository context
changed files
dependency information
```

Output:

```text
root cause
failure class
evidence
confidence
research requirement
```

---

## Research Agent

Activated when external information is required.

Example:

```text
dependency changed
       ↓
Tavily search
       ↓
documentation
release notes
GitHub issues
migration guidance
       ↓
research context
       ↓
Nemotron
```

Tavily is intended to be a real runtime tool rather than a decorative integration.

---

## Repair Generator

Nemotron generates multiple repair hypotheses.

For example:

```text
Candidate A
dependency change

Candidate B
source compatibility patch

Candidate C
adapter layer
```

The model proposes the strategies.

It does not decide which one is correct.

---

## Sandbox Execution

Each candidate is executed independently.

Conceptually:

```text
                     ROOT FAILURE
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
         Sandbox A      Sandbox B      Sandbox C
             │             │             │
           Tests         Tests         Tests
             │             │             │
             ▼             ▼             ▼
             ❌             ✅             ❌
                           │
                           ▼
                         Winner
```

ConTree is intended to provide the branchable isolated execution environment for this repair search.

---

## Verification

A selected repair should not immediately become a pull request.

SandHeal will perform:

```text
targeted verification
       ↓
regression test
       ↓
unit tests
       ↓
integration tests
       ↓
final verification
```

Only after the repair passes the required checks should the system proceed toward pull-request creation.

---

# Repair Run State Machine

The current domain state machine is:

```text
                    ┌───────────────┐
                    │   RECEIVED    │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ REPRODUCING   │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │   ANALYZING   │
                    └───────┬───────┘
                            │
                    ┌───────┴────────┐
                    │                │
                    ▼                ▼
             RESEARCHING     GENERATING_REPAIRS
                    │                │
                    └───────┬────────┘
                            ▼
                    ┌───────────────┐
                    │   EXECUTING   │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │   VERIFYING   │
                    └───────┬───────┘
                            │
                      ┌─────┴─────┐
                      │           │
                      ▼           ▼
                 EXECUTING    CREATING_PR
                                  │
                                  ▼
                             COMPLETED
```

Any stage can also enter controlled failure/cancellation states.

### Persisting a transition

The state machine is not documentation only: it is the authority on every
status change. A transition is applied through the application service,
which delegates the legality check to the domain model and persists the
result in a single transaction.

```python
run = await RepairRunService(session).advance_run(
    run_id,
    RunStatus.REPRODUCING,
)
```

An illegal transition raises `InvalidTransitionError` and leaves the stored
run untouched. `InvalidTransitionError` subclasses `ValueError`, so
existing handling of `ValueError` keeps working.

The `RepairRun` domain object carries the same workflow metadata that the
persistence record holds (`delivery_id`, `workflow_name`, `workflow_run_id`,
`branch`, `conclusion`), so later phases can work from a stored run rather
than from a webhook payload.

---

# Reliability Principles

SandHeal is being built around several reliability principles.

## 1. Validate at the boundary

External data is validated and normalized before entering the core application.

## 2. Keep domain logic independent

The domain should not depend on GitHub, SQLAlchemy, Redis, or a specific AI provider.

## 3. Database constraints are part of correctness

Application checks alone are not enough.

Important invariants are enforced by the database where appropriate.

## 4. Idempotency by design

External events may be duplicated.

The system must remain correct under retries.

## 5. Models are not trusted blindly

Generated code must be executed and verified.

## 6. Evidence should accompany automated actions

A future SandHeal PR should explain:

```text
what failed
why it failed
what candidates were attempted
which candidate won
what tests passed
what research was used
```

---

# Testing Philosophy

SandHeal uses test-first development for critical behavior.

Tests are written around:

```text
normal behavior
invalid input
failure behavior
duplicate events
transaction rollback
state transitions
serialization
security validation
```

The goal is not simply high test count.

The goal is to protect the system's **behavioral contracts**.

---

# Current Test Coverage

The project currently contains tests covering:

```text
RepairRun domain behavior
RepairJob domain behavior
state transitions
terminal states
persisted lifecycle transitions
GitHub webhook validation
webhook payload normalization
webhook signatures
fail-closed secret handling
malformed payloads
Unicode payload handling
GitHub event filtering
RepairRun persistence
RepairJob persistence
idempotent delivery handling
database uniqueness
database status constraints
transactional Run + Job creation
concurrent duplicate delivery
startup schema registration
request correlation
global error handling
readiness reporting
```

The suite is executed with:

```bash
pytest -v
```

With a coverage report:

```bash
pytest --cov=app --cov-report=term-missing
```

Code quality checks:

```bash
ruff check .
ruff format --check .
```

### Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request:

```text
Lint          ruff check + ruff format --check
Test          pytest with coverage
Runtime       pip install -e . (no dev extra), then import and boot the app
```

The `Runtime` job exists because a missing runtime dependency only shows
up at deploy time. It installs the project exactly the way a production
install would and boots the application, so that failure mode fails the
build instead.

---

# Local Development

## Requirements

* Python 3.12+
* Git

## Create virtual environment

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## Install project

Using `uv`:

```bash
uv pip install -e ".[dev]"
```

Or using pip:

```bash
pip install -e ".[dev]"
```

The `[dev]` extra only adds the test and lint tooling. The runtime
dependencies, including the `aiosqlite` driver used by the default
database URL, are installed either way, so a production-style install is:

```bash
pip install -e .
```

## Run tests

```bash
pytest -v
```

## Run linting

```bash
ruff check .
```

## Check formatting

```bash
ruff format --check .
```

## Common tasks

A `Makefile` wraps the usual commands:

```bash
make help          # list the available targets
make install-dev   # install with the development extras
make test          # run the test suite
make coverage      # run the test suite with coverage
make lint          # run the linter
make check         # lint and format check
make migrate       # apply the database migrations
make revision m="message"   # create a new migration
make run           # start the development server
```

## Run with Docker

```bash
docker build -t sandheal .
docker run --rm -p 8000:8000 -e GITHUB_WEBHOOK_SECRET=your-secret sandheal
```

The image installs the runtime dependencies only, runs as a non-root
user and applies the database migrations on startup.

## Start development server

```bash
uvicorn app.main:app --reload
```

API:

```text
http://127.0.0.1:8000
```

Health endpoint:

```text
http://127.0.0.1:8000/health
```

Readiness endpoint:

```text
http://127.0.0.1:8000/ready
```

Webhook endpoint:

```text
http://127.0.0.1:8000/webhooks/github
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

---

# Environment Configuration

Create a local `.env` file based on:

```text
.env.example
```

Current configuration includes:

```env
APP_NAME=SandHeal
ENVIRONMENT=development
DEBUG=false
GITHUB_WEBHOOK_SECRET=replace-me
DATABASE_URL=sqlite+aiosqlite:///./sandheal.db
AUTO_MIGRATE=true
```

Never commit real secrets.

`GITHUB_WEBHOOK_SECRET` must be replaced with a real secret. The
placeholder value shown above is publicly known, so SandHeal treats it as
"not configured" and rejects every delivery with HTTP 503. See
[Fail-closed secret handling](#fail-closed-secret-handling).

`ENVIRONMENT` controls how a missing secret is handled: `development`
starts anyway and logs an error, while `production` refuses to start.

`AUTO_MIGRATE` controls the schema management. It is enabled by default,
so the database is brought up to date with the Alembic migrations on
startup. Set it to `false` to create the tables from the ORM metadata
instead.

The webhook secret is stored as a masked value, so it never appears in a
log line, a `repr()` or a serialised settings dump.

---

# Planned Production Evolution

The current local architecture is intentionally simple.

The target deployment architecture will eventually move toward:

```text
                    Nebius
                      │
          ┌───────────┴───────────┐
          │                       │
     API / Serverless        AI Inference
          │                       │
          │                  Nemotron
          │
          ▼
        Redis
          │
          ▼
       Workers
          │
          ▼
     ConTree Sandboxes
          │
          ▼
      Test Results
          │
          ▼
       PostgreSQL
```

Schema management will move from development-time metadata creation to:

```text
Alembic migrations
```

---

# Development Roadmap

## Phase 1 — Foundation

Completed:

```text
✓ FastAPI
✓ Configuration
✓ Health endpoint
✓ Domain model
✓ State machine
✓ GitHub webhook
✓ Webhook security
✓ SQLite persistence
✓ RepairRun
✓ RepairJob
✓ Idempotency
✓ Atomic transactions
```

## Phase 2 — Asynchronous Execution

Next:

```text
Redis
Worker
Job claiming
Retry handling
Backoff
Job lifecycle
```

## Phase 3 — GitHub Repository Context

Then:

```text
GitHub API
Repository checkout
Commit inspection
Changed-file analysis
Workflow log retrieval
```

## Phase 4 — AI Failure Analysis

Then:

```text
Nemotron
Failure classification
Root-cause analysis
Structured reasoning output
```

## Phase 5 — External Research

Then:

```text
Tavily
Conditional research
Documentation retrieval
GitHub issue research
Evidence extraction
```

## Phase 6 — Sandboxed Repair

Then:

```text
ConTree
Failure reproduction
Repair candidate generation
Branch creation
Parallel execution
Test result collection
```

## Phase 7 — Verification

Then:

```text
Repair selection
Regression test generation
Full test suite
Verification scoring
```

## Phase 8 — Pull Requests

Then:

```text
Git diff
Commit generation
PR description
Evidence report
GitHub PR creation
```

## Phase 9 — Developer Experience

Finally:

```text
Next.js dashboard
Repair timeline
Repair hypothesis tree
Sandbox activity
Test results
Evidence
PR status
```

---

# Hackathon Goal

SandHeal is being developed for the:

**Nebius x NVIDIA Global AI Hackathon**

The intended target track is:

**Coding and Agentic Engineering**

The project is designed around the central capabilities emphasized by the hackathon:

```text
AI agents
code generation
code execution
testing
Nebius infrastructure
NVIDIA open-source models
```

The architecture intentionally makes Nebius sandbox execution a core part of the repair process rather than simply using an LLM API.

---

# Long-Term Vision

SandHeal should ultimately transform software repair from:

```text
"AI, tell me how to fix this."
```

into:

```text
"Here is the failure.

Investigate it.

Develop several hypotheses.

Test them independently.

Determine which repair actually works.

Prove it.

Protect against regression.

Give the developer the evidence."
```

The end goal is not autonomous code generation.

It is **autonomous, evidence-driven software repair**.

---

# License

SandHeal is open source under the MIT License.

See `LICENSE` for details.
