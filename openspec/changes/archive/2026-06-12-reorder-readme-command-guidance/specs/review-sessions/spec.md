## MODIFIED Requirements

### Requirement: Existing planning commands SHALL remain compatible

The session workflow SHALL preserve the existing `inventory`, `plan`, and `report` command concepts while making legacy planning command output selection explicit. `inventory` and `plan` SHALL accept `--format json|text`, default to `text`, and SHALL no longer accept the legacy `--json` flag. JSON output for `inventory --format json` and `plan --format json` SHALL remain parseable using the existing Pydantic JSON contracts. Inventory generation SHALL exclude review-gauntlet-generated session state, common cache/build/editor artifacts, and files ignored by Git when Git-backed discovery is available, so coverage reflects the project review target rather than generated tool state. User-facing README command guidance SHALL present the session workflow as the primary review path and document `inventory`, `plan`, and `report` as diagnostic or legacy planning inspection commands rather than the first day-to-day entry points.

<!-- Expected canonical result after archive: the planning command compatibility requirement documents `--format json|text` for inventory/plan, default text output, removal of the legacy `--json` flag, retained report behavior, and README guidance that places planning commands after the primary session workflow as diagnostic inspection commands. -->

#### Scenario: Existing inventory JSON remains parseable

**Given**: a repository with files to classify
**When**: the developer runs `review-gauntlet inventory <root> --format json`
**Then**: stdout is valid JSON emitted with the existing Pydantic JSON contract

#### Scenario: Existing plan JSON remains parseable

**Given**: a repository with files to classify into review slices
**When**: the developer runs `review-gauntlet plan <root> --format json`
**Then**: stdout is valid JSON emitted with the existing Pydantic JSON contract

#### Scenario: Inventory defaults to text output

**Given**: a repository with files to classify
**When**: the developer runs `review-gauntlet inventory <root>`
**Then**: stdout is deterministic human-readable text
**And**: stdout is not required to be parseable as JSON

#### Scenario: Plan defaults to text output

**Given**: a repository with files to classify into review slices
**When**: the developer runs `review-gauntlet plan <root>`
**Then**: stdout is deterministic human-readable text
**And**: stdout is not required to be parseable as JSON

#### Scenario: Legacy JSON flag is rejected for planning commands

**Given**: a repository with files to classify
**When**: the developer runs `review-gauntlet inventory <root> --json` or `review-gauntlet plan <root> --json`
**Then**: argument parsing fails with a usage error

#### Scenario: Existing report remains available

**Given**: a repository with files to review
**When**: the developer runs `review-gauntlet report <root>`
**Then**: the command emits the markdown review matrix report
**And**: existing tests for report output continue to pass

#### Scenario: Generated review state is excluded from inventory

**Given**: a repository containing `.review-gauntlet/` session state and run artifacts
**When**: the developer runs `review-gauntlet inventory <root> --format json`
**Then**: no path under `.review-gauntlet/` appears in the inventory output
**And**: generated review state does not create review cells for subsequent session reconciliation

#### Scenario: README leads with session workflow

**Given**: a reader opens the README command guidance
**When**: they follow the first operational Review Gauntlet review workflow shown after setup
**Then**: the guidance starts with session initialization through `review-gauntlet init`
**And**: it continues through one `review-gauntlet review` run and related session-state commands before introducing `inventory`, `plan`, or `report`

#### Scenario: Planning commands are documented as diagnostics

**Given**: a reader needs to inspect file discovery, slicing, or report rendering
**When**: they read the README command guidance for `inventory`, `plan`, and `report`
**Then**: those commands are still documented with example invocations
**And**: the wording identifies them as diagnostic, inspection, or legacy planning commands rather than the primary review lifecycle
