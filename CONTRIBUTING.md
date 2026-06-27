# Contributing to VERITY CORE

Thank you for your interest. Contributions that increase adoption or fix real bugs are the most valuable.

## Quick start

```bash
git clone https://github.com/haynbroit-alt/V-rify-IA
cd V-rify-IA
pip install -e ".[dev]"
pytest
```

Docker is required to run the full sandbox. For unit tests only, Docker is not needed — the subprocess fallback activates automatically in CI.

## What to work on

Check [open issues](https://github.com/haynbroit-alt/V-rify-IA/issues). The most useful contributions right now:

- **Integrations**: tool wrappers for LlamaIndex, AutoGen, CrewAI, Haystack
- **SDK clients**: TypeScript/JavaScript SDK (`npm install verity-core`)
- **Bug reports**: if something breaks, open an issue with a minimal repro

## Pull requests

1. Fork → branch → commit → PR against `main`
2. Make sure `ruff check .` and `pytest` pass before opening the PR
3. Keep PRs focused — one fix or feature per PR

## Code style

```bash
ruff check .       # lint
ruff format .      # format
pytest --cov=app   # tests (coverage must stay above 80%)
```

## Reporting a security issue

Do not open a public issue. Email haynbroit@hotmail.com directly.
