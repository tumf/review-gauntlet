# Review Gauntlet Checkpoint

- Checkpoint state: complete
- Usable as review base: True
- Review base commit: 9e5f6db071049087b931e4dea0422246e2f96d24
- Session ID: RGS-bf5d11c1d8ec
- Created at: 2026-06-14T14:17:43.264173Z (generation timestamp)

## Coverage

| State | Count |
| --- | ---: |
| reviewed | 21 |

## Findings

| ID | State | Path | Rule | Content |
| --- | --- | --- | --- | --- |
| RGF-0086 | fixed_verified | Makefile | ci-reproducibility | `make check` is documented as the CI-equivalent check, but it omits the coverage target even though CI runs `make coverage` after `make test`. This means a local `make check` can pass while the configured CI still fails in coverage collection/reporting, reducing reproducibility between local and CI validation. |
| RGF-0087 | fixed_verified | .github/workflows/ci.yml | ci-reproducibility | GitHub-hosted runner image is not pinned. `ubuntu-latest` can move to a new Ubuntu release and change system packages or Python/uv behavior, making CI failures non-reproducible. Pin the runner to a concrete image version. |
| RGF-0088 | fixed_verified | .github/workflows/ci.yml | ci-reproducibility | The `setup-uv` action is referenced by a moving tag rather than an immutable commit SHA. If the tag is retargeted or the action changes behavior, this CI job may no longer be reproducible. Pin the action to a reviewed commit SHA. |
| RGF-0089 | fixed_verified | pyproject.toml | ci-reproducibility | The project advertises Python 3.12 and 3.13 support in its package metadata, but the repository's CI only installs and tests Python 3.11 and Pyright is configured for Python 3.11. This makes the published compatibility claim unreproducible from CI and can let unsupported-version breakage ship unnoticed. |
| RGF-0090 | fixed_verified | README.md | docs-accuracy | The opencode example does not match the bundled opencode preset created by `review-gauntlet config init --preset opencode`. The preset invokes `opencode run {prompt}` without `--dangerously-skip-permissions`, so readers following the generated-config flow will see different args than this documented minimal configuration. |
| RGF-0091 | fixed_verified | .github/workflows/ci.yml | ci-reproducibility | CI only installs and tests Python 3.11 even though the package metadata advertises support for Python 3.12 and 3.13. This can let incompatibilities in the declared supported versions ship unnoticed; use a matrix to run the same checks across each advertised Python version, or narrow the classifiers if only 3.11 is intended. |
| RGF-0092 | fixed_verified | .github/workflows/ci.yml | ci-reproducibility | `actions/checkout@v4` is pinned only to a mutable version tag, while the workflow already pins `astral-sh/setup-uv` to a commit SHA. For reproducible CI and to reduce supply-chain drift, pin checkout to a full commit SHA as well. |
| RGF-0093 | fixed_verified | .github/workflows/ci.yml | ci-reproducibility | CI runs `uv sync --all-groups` without enabling locked/frozen resolution, so dependency versions can drift from `uv.lock` whenever package indexes change or the lockfile is out of date. For reproducible CI, install exactly from the committed lockfile and fail when it is stale. |
| RGF-0094 | fixed_verified | Makefile | ci-reproducibility | The aggregate check target is not CI-equivalent because it also runs coverage, while the GitHub workflow executes format-check, lint, typecheck, test, and then coverage as a separate step. This makes the documented local CI command do extra work and can make local/CI failure boundaries differ. Consider keeping check aligned with the required gates and leaving coverage as an explicit target. |
| RGF-0095 | fixed_verified | README.md | docs-accuracy | This path is documented as `.review-gauntlet/checkpoints/latest/status.json`, but `latest` is a pointer file written with the checkpoint id, while the JSON snapshots are written under `.review-gauntlet/checkpoints/<checkpoint_id>/`. Following the README literally will point users at a non-existent path after finalize. |
| RGF-0096 | fixed_verified | src/review_gauntlet/cli.py | test-evidence | A normal `review` run intentionally selects files with `fixed_pending_verification` findings via `_select_review_cells`, but this path never calls `verify_fixed_findings`. If the reviewer no longer reports the fingerprint, the finding stays fixed-pending forever and `status`/`finalize` remain blocked unless the user separately runs `verify-fixes`, even though the evidence was already collected in this review run. Either remove fixed-pending paths from normal review selection or apply the same verification transition after evaluating those paths. |
| RGF-0097 | fixed_verified | src/review_gauntlet/cli.py | test-evidence | review-fixes exits with failure whenever targeted fixed-pending findings are reopened, even if the reviewer reported a fresh finding for the same issue. In that path `finding_ids` contains actionable reopened findings, but the command still returns exit 1, so automation cannot distinguish a successful verification that found regressions from an adapter/runtime failure and may treat valid test evidence as a broken review run. |

## Triage Events

| Event | Finding | From | To | Reason |
| ---: | --- | --- | --- | --- |
| 166 | RGF-0087 | untriaged | confirmed | Confirmed: workflow uses ubuntu-latest at .github/workflows/ci.yml:11, so the runner image is moving rather than pinned. |
| 167 | RGF-0088 | untriaged | confirmed | Confirmed: workflow uses astral-sh/setup-uv@v6 at .github/workflows/ci.yml:18, which is a tag rather than an immutable SHA. |
| 168 | RGF-0086 | untriaged | confirmed | Confirmed: Makefile check omits coverage at Makefile:21 while CI runs make coverage at .github/workflows/ci.yml:38-39. |
| 169 | RGF-0090 | untriaged | confirmed | Confirmed: README opencode example includes --dangerously-skip-permissions at README.md:331 but the bundled preset args omit it in src/review_gauntlet/presets/opencode.jsonc:9-12. |
| 170 | RGF-0089 | untriaged | confirmed | Confirmed: pyproject advertises Python 3.12 and 3.13 at pyproject.toml:20-21 while CI installs only Python 3.11 and pyright targets 3.11. |
| 171 | RGF-0087 | confirmed | fixed_pending_verification | Pinned GitHub Actions runner to ubuntu-24.04 and make check passes. |
| 172 | RGF-0091 | untriaged | confirmed | CI hardcodes Python 3.11 while pyproject advertises Python 3.12 and 3.13 support; confirmed as a real reproducibility gap. |
| 173 | RGF-0088 | confirmed | fixed_pending_verification | Pinned astral-sh/setup-uv v6 to commit d0d8abe699bfb85fec6de9f7adb5ae17292296ff in CI workflow. |
| 174 | RGF-0092 | untriaged | confirmed | actions/checkout remains pinned to the mutable v4 tag in .github/workflows/ci.yml, so this reproducibility finding is real. |
| 175 | RGF-0092 | confirmed | fixed_pending_verification | Pinned actions/checkout to the current v4 commit SHA in CI workflow. |
| 176 | RGF-0091 | confirmed | fixed_pending_verification | Added CI Python matrix for advertised 3.11, 3.12, and 3.13 support. |
| 177 | RGF-0091 | fixed_pending_verification | fixed_verified | review_verification |
| 178 | RGF-0092 | fixed_pending_verification | fixed_verified | review_verification |
| 179 | RGF-0087 | fixed_pending_verification | fixed_verified | review_verification |
| 180 | RGF-0088 | fixed_pending_verification | fixed_verified | review_verification |
| 181 | RGF-0093 | untriaged | confirmed | CI dependency sync does not enforce the committed uv.lock; .github/workflows/ci.yml:30-31 runs uv sync --all-groups without --locked. |
| 182 | RGF-0093 | confirmed | fixed_pending_verification | Added --locked to uv sync in CI so dependencies are installed from the committed lockfile; make check passes. |
| 183 | RGF-0086 | confirmed | fixed_pending_verification | Updated make check to include coverage so local CI-equivalent validation matches the CI workflow; make check passes. |
| 184 | RGF-0090 | confirmed | fixed_pending_verification | Aligned README opencode minimal config with the bundled opencode preset args; make check passes. |
| 185 | RGF-0089 | confirmed | fixed_pending_verification | Added CI matrix for Python 3.11, 3.12, and 3.13 so advertised classifiers are covered by CI; make check passes locally. |
| 186 | RGF-0093 | fixed_pending_verification | fixed_verified | review_verification |
| 187 | RGF-0089 | fixed_pending_verification | fixed_verified | review_verification |
| 188 | RGF-0086 | fixed_pending_verification | fixed_verified | review_verification |
| 189 | RGF-0090 | fixed_pending_verification | fixed_verified | review_verification |
| 190 | RGF-0094 | untriaged | confirmed | Makefile check target includes coverage while AGENTS.md documents CI-equivalent check as format-check lint typecheck test and coverage is a separate Make target |
| 191 | RGF-0095 | untriaged | confirmed | README documents latest/status.json, but implementation uses latest as a pointer file and stores snapshots under checkpoints/<checkpoint_id>/ |
| 192 | RGF-0094 | confirmed | fixed_pending_verification | Aligned Makefile check target with CI gate steps by leaving coverage as explicit target. |
| 193 | RGF-0095 | confirmed | fixed_pending_verification | Corrected README checkpoint snapshot location and latest pointer description. |
| 194 | RGF-0095 | fixed_pending_verification | fixed_verified | review_verification |
| 195 | RGF-0094 | fixed_pending_verification | fixed_verified | review_verification |
| 196 | RGF-0096 | untriaged | confirmed | Normal review selects fixed-pending paths in _select_review_cells but _cmd_review does not call verify_fixed_findings; verify transition only occurs in verify-fixes. |
| 197 | RGF-0096 | confirmed | fixed_pending_verification | Normal review now verifies fixed-pending findings for evaluated paths; focused tests cover verified, reopened, and partial-failure behavior |
| 198 | RGF-0096 | fixed_pending_verification | fixed_verified | review_verification |
| 199 | RGF-0097 | untriaged | confirmed | 現行コードは verify-fixes で reopened_ids があるだけでも exit 1 になっており、adapter/runtime failure と検証による再オープンを終了コードで区別できないため実在する指摘として確認した |
| 200 | RGF-0097 | confirmed | fixed_pending_verification | Changed verify-fixes to treat reopened findings as successful verification results rather than command failures; updated regression test; make check passes |
| 201 | RGF-0097 | fixed_pending_verification | fixed_verified | review_verification |

## Blockers

None
