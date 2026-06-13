# Design: Ready Prompt Command

## Overview

`review-gauntlet ready` is a small agent handoff surface. It does not replace `status`; it uses the same underlying session state to choose a single next prompt that an external orchestration layer can hand to an agent with the review-gauntlet task execution skill.

The design intentionally avoids durable task state. The current ledger already records review cells, findings, finding events, runs, and finalization state. `ready` reads those records and emits a prompt; it does not claim, reserve, complete, or mutate tasks.

## Behavior Boundary

`ready` is a read-only command:

- It may read the active session id, review cell states, finding states, run evidence, target digest freshness, finalization blockers, and checkpoint-relevant state.
- It must not create runs, update cells, transition findings, write finding events, write checkpoint files, or invoke git mutations.
- It must not attempt to coordinate multiple agents.

This preserves the constitution's separation between review-gauntlet state/verdicts and external orchestration.

## Prompt Contract

JSON output is intentionally minimal:

```json
{"prompt":"..."}
```

or:

```json
{"prompt":null}
```

Text output prints only the prompt body or `no ready task`.

The prompt is short because the external skill owns concrete procedures. Each prompt names:

1. The review-gauntlet task execution skill.
2. The next work category.
3. The stop condition.

It does not include detailed commands, task IDs, claim instructions, or structured completion metadata.

## Prompt Selection

The selection order mirrors completion dependencies:

1. Reopened findings need re-triage before they can be fixed or closed.
2. Untriaged findings need classification before fixing or finalization.
3. Confirmed findings need fixing before verification and finalization.
4. Fixed-pending findings need verification before finalization.
5. Stale coverage must be refreshed before current completion can be trusted.
6. Pending coverage must be reviewed before completion.
7. Finalization is available only after review/finding dependencies are resolved.

Within categories where the prompt says "next", implementation may use deterministic ordering by persisted IDs when inspecting details internally, but the output remains prompt-only.

## Finalize Handling

Finalization is special because `finalize` itself requires a committed clean review universe, but users specifically want the ready prompt to instruct agents to commit intended git changes before finalizing.

Therefore the finalize prompt includes git-commit-before-finalize guidance. `ready` itself remains read-only and does not commit or finalize.

If unresolved blockers remain other than the dirty-worktree situation that the finalize prompt can direct an agent to handle, `ready` should return no prompt rather than pretending finalization can proceed. The external skill can use `status` to surface the concrete blocker.

## Non-Goals

- No durable task table.
- No claim or release commands.
- No queue, lease, or timeout behavior.
- No expansion of `status`.
- No skill authoring in this change.
