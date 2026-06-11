# Design: CLI Output Option Standardization

## Scope

This change is limited to command-line option vocabulary and the parser wiring that determines accepted formats and audience flags. It does not change review coverage semantics, finding state transitions, durable ledger shape, adapter contracts, or JSON payload schemas.

## Parser Structure

The current shared session output helper couples two distinct concepts:

- final output format (`--format`)
- progress/display audience (`--audience`)

The implementation should separate these concerns:

- Use one helper or explicit parser wiring for `--format {text,json}`.
- Register `--audience {human,agent}` only on `review`, because it is currently the only command with progress display behavior.

This avoids reintroducing audience switches on commands that only emit a final summary.

## Text vs Markdown

`report` currently emits a Markdown report. The CLI format name should still be `text` for consistency, while the body may remain Markdown-formatted text. This preserves existing report readability and tests while removing `markdown` from the accepted option vocabulary.

## Compatibility

This is an intentional CLI cleanup with breaking behavior for obsolete option names:

- `--format human` is rejected.
- `--format markdown` is rejected.
- `--audience` is rejected outside `review`.

JSON output schemas and default command behavior remain otherwise unchanged.
