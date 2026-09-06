# SandHeal

SandHeal is a proof-driven autonomous CI/CD repair agent.

It investigates failed CI/CD pipelines, reproduces failures in isolated
execution environments, explores multiple repair hypotheses, verifies fixes
through real test execution, and creates evidence-backed pull requests.

## Development

### Requirements

- Python 3.12+
- Git

### Setup

```bash
python -m venv .venv