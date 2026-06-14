# Design: `review-gauntlet run`

## Current Architecture

`review-gauntlet ready` already computes the next continuation prompt from active session state. It considers effective current target coverage, finding states, fixed-finding verification, stale cells, and finalization blockers.

`review-gauntlet review` uses `CommandReviewAdapter` for a different responsibility: selecting review cells, generating OCR-derived review prompts, requiring OCR-style verdict JSON, and recording findings/coverage from parsed verdicts.

## Key Decision: Reuse adapter configuration, not review-cell adapter execution

`run` should reuse the configured command adapter settings because users already configure an external agent through that surface. However, `run` must not call `CommandReviewAdapter.review()` because that method is intentionally review-cell specific and validates OCR verdict JSON.

Instead, implement a session-level command runner that accepts a ready prompt and uses the same command configuration fields:

- `command`
- `args`
- `cwd`
- `env`
- `timeout_seconds`

The runner treats stdout/stderr as agent execution diagnostics, not as verdict input.

## Template Variables

For `run`, supported session-level template variables should include:

- `{repo_root}`
- `{state_dir}`
- `{prompt}`

These variables are enough for bundled presets such as:

```jsonc
{
  "adapter": {
    "type": "command",
    "command": "opencode",
    "args": ["run", "{prompt}"]
  }
}
```

Cell-level variables such as `{cell_id}`, `{cell_dir}`, `{output_file}`, `{file_path}`, and `{rule_id}` belong to review-cell execution. If a configuration used by `run` contains cell-level variables, `run` should fail clearly rather than silently expanding dummy values.

## Loop Semantics

For each step:

1. Resolve active session through `SessionStore`.
2. Call the same ready prompt function used by the `ready` command.
3. If no prompt exists, stop with exit `1`.
4. Invoke the configured command with `{prompt}` expanded.
5. If the command fails, stop with exit `1`.
6. Re-check active session state.
7. If active session is gone, stop with exit `0`.
8. Continue until `--max-steps` is reached.

The loop must not mutate Session Store directly except through existing commands invoked by the external agent. This preserves the design principle that `run` owns orchestration, while durable state remains in the existing session ledger and active-session marker.

## Failure Semantics

`run` returns exit `1` for operational blockage rather than usage error when:

- active session remains but no ready task exists
- agent command returns non-zero
- agent command cannot start
- agent command times out
- `--max-steps` is exhausted before completion

Usage errors such as invalid `--max-steps` values should continue using the existing CLI usage-error behavior.

## Documentation Strategy

The README should make `run` the recommended session progression command:

```bash
review-gauntlet init
review-gauntlet run
```

`ready` remains documented for CI, custom orchestrators, external integrations, and debugging. This preserves power-user workflows while making the default workflow simpler.
