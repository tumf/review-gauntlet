# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: 76e3ccec22b1ecdb3b511eb193d76e63f65c381d
- Session ID: RGS-efeeca905d3a
- Created at: 2026-06-18T11:38:38.093512Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 15 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-1017 | dismissed | src/review_gauntlet/checkpoint.py | cli-contract | target_from_latest_checkpoint() calls _git(root, 'rev-parse', '--verify', 'HEAD^{commit}') at line 110 without catching subprocess.CalledProcessError. If HEAD does not resolve (empty repo, detached HEAD failure, or git corruption), the raw CalledProcessError propagates to CLI callers. All other git invocations in _validate_latest_checkpoint() (lines 199-212) are wrapped in try/except CalledProcessError with descriptive ValueError messages. This inconsistency breaks the agent-friendly CLI contract: callers must unexpectedly handle subprocess.CalledProcessError from a function whose signature gives no indication of that possibility. |
| RGF-1018 | dismissed | src/review_gauntlet/checkpoint.py | data-validation | write_latest_checkpoint() accepts status: dict[str, object] (line 264) but does not validate the types of values at lines 295-298 before use. status.get('coverage', {}) is passed directly into base_status, and _render_summary() at line 452 calls coverage.items() on it. If a caller passes status['coverage'] as a non-dict (e.g. a string, int, or None from a buggy serialization), the function writes a malformed checkpoint then raises AttributeError inside _render_summary rather than a clear validation error at the boundary. The input should be validated at the point of entry before any writes occur. |
| RGF-1019 | confirmed | src/review_gauntlet/checkpoint.py | test-evidence | _validate_latest_checkpoint() (lines 120-212) contains 20+ distinct validation branches covering schema_version, checkpoint_state, usable_as_review_base, SHA format, git ancestry, per-entry field presence, field types, and state-enum values. There are no direct unit tests for this function. The only test coverage is through two high-level CLI finalize tests (test_finalize_writes_checkpoint_with_two_phase_states and test_finalize_blocks_dirty_review_universe_without_override), which exercise only the happy path and one dirty-tree path. Edge cases — missing required fields, invalid SHA format, non-ancestor base commit, invalid finding state string — have no automated regression coverage, making it easy to silently break the validation logic. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 1681 | RGF-1017 | open | dismissed | False positive: _git() at line 111 is wrapped in a try/except CalledProcessError block starting at line 110; the exception is properly caught and re-raised as ValueError. The finding incorrectly asserts it is uncaught. |
| 1682 | RGF-1018 | open | dismissed | Accepted risk: write_latest_checkpoint() is an internal API called only from trusted finalize code within the library. The status values (coverage, finding_state_counts, run_count, blockers) come from SessionStore which returns well-typed data. JSON serialization provides a basic type gate; _validate_latest_checkpoint() catches structural issues on load. Adding runtime type assertions would be redundant over trusted internal callers. |
| 1683 | RGF-1019 | open | confirmed | Real gap: _validate_latest_checkpoint() (lines 120-212) contains 20+ distinct validation branches covering schema_version, checkpoint_id integrity, findings.json/events.json structure, field type checks, base commit SHA format, and git ancestry. No test evidence was found for these branches. This is critical checkpoint integrity logic where untested edge cases could allow a corrupted checkpoint to be silently accepted as valid. |

## Blockers

None
