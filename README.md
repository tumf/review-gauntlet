Review Gauntlet
===============

Coverage-driven review orchestration for agentic code reviews.

The goal is not to pretend an LLM can guarantee bug-free code. The goal is to
guarantee that a defined review surface was inspected, with evidence, before a
project is called reviewed.

## Commands

```bash
uv sync
make check
```

Generate an inventory for a repository:

```bash
uv run review-gauntlet inventory /path/to/repo --json
```

Generate a review plan with slices and required checks:

```bash
uv run review-gauntlet plan /path/to/repo --json
```

Generate a markdown report:

```bash
uv run review-gauntlet report /path/to/repo
```

## Developer Workflow

```bash
make format
make lint
make typecheck
make test
make coverage
```

## Design

Review Gauntlet treats review as a coverage matrix:

- inventory the project files
- classify files into review slices
- attach risk-specific checks to each slice
- require evidence for each matrix row before final pass

The first version is intentionally small: it creates the inventory, review plan,
and matrix. Review runners for Codex, Claude, static analyzers, and custom tools
can plug into the same matrix later.
