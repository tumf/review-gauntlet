# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: 60621a27c1648d0f84c6536994964bdc3faa6645
- Session ID: RGS-9722815ee8a5
- Created at: 2026-06-18T10:10:45.526163Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-1014 | confirmed | src/review_gauntlet/cli.py | cli-contract | _cmd_mark only maps 2 of 7 valid mark states. The argparse choices at lines 286-296 accept confirmed, fixed_pending_verification, fixed_verified, false_positive, accepted_risk, waived, dismissed, but the local mapping dict at line 2283 only contains confirmed and dismissed. Calling `review-gauntlet mark <id> waived` (or any of the other 5 states) raises an unhandled KeyError at line 2288 instead of running correctly. The complete mapping already exists in _FINDING_MARK_TO_STATE (line 110) but is not used here. |
| RGF-1015 | confirmed | src/review_gauntlet/cli.py | data-validation | _cmd_mark accesses mapping[args.state] at line 2288 without first validating that args.state is a key in mapping. The argparse layer accepts 7 states but mapping only has 2 keys, so 5 valid CLI inputs bypass validation and crash with KeyError. The fix is to use _FINDING_MARK_TO_STATE (line 110) which has all states, or guard with an explicit membership check before the dict lookup. |
| RGF-1016 | confirmed | src/review_gauntlet/cli.py | test-evidence | The _cmd_mark implementation (lines 2281-2289) has no test coverage for mark states other than confirmed and dismissed. The KeyError bug for waived, fixed_pending_verification, fixed_verified, false_positive, and accepted_risk went undetected because no test exercises review-gauntlet mark with these states. Each of the 7 accepted states should have a regression test to verify _cmd_mark correctly dispatches them. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 1678 | RGF-1014 | open | confirmed | Expanded _cmd_mark to cover all 7 FindingState values; mapping was incomplete (2/7 states) |
| 1679 | RGF-1015 | open | confirmed | mapping[args.state] would KeyError for 5 of 7 valid states; fixed by using FindingState(args.state) directly |
| 1680 | RGF-1016 | open | confirmed | No test coverage for mark states other than confirmed/dismissed; real gap in test suite (test file changes required, out of scope for cli.py) |

## Blockers

None
