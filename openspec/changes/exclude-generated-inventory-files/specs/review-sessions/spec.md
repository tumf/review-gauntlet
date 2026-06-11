## MODIFIED Requirements

### Requirement: Existing planning commands SHALL remain compatible

The new session workflow SHALL preserve the existing `inventory`, `plan`, and `report` command contracts while reusing their concepts for review-universe generation. Inventory generation SHALL exclude review-gauntlet-generated session state, common cache/build/editor artifacts, and files ignored by Git when Git-backed discovery is available, so coverage reflects the project review target rather than generated tool state.

#### Scenario: Existing inventory JSON remains parseable

**Given**: a repository with files to classify
**When**: the developer runs `review-gauntlet inventory <root> --json`
**Then**: stdout is valid JSON emitted with the existing Pydantic JSON contract

#### Scenario: Existing report remains available

**Given**: a repository with files to review
**When**: the developer runs `review-gauntlet report <root>`
**Then**: the command emits the markdown review matrix report
**And**: existing tests for report output continue to pass

#### Scenario: Generated review state is excluded from inventory

**Given**: a repository containing `.review-gauntlet/` session state and run artifacts
**When**: the developer runs `review-gauntlet inventory <root> --json`
**Then**: no path under `.review-gauntlet/` appears in the inventory output
**And**: generated review state does not create review cells for subsequent session reconciliation

#### Scenario: Common generated artifacts are excluded from fallback inventory

**Given**: a project tree with normal source files and generated artifacts under cache, build, coverage, virtualenv, or editor metadata paths
**And**: Git-backed discovery is unavailable
**When**: review-gauntlet builds inventory by recursively walking the filesystem
**Then**: normal source files remain included
**And**: generated artifact paths such as `.ruff_cache/`, `.pyright/`, `.mypy_cache/`, `build/`, `dist/`, `wheels/`, `*.egg-info/`, `.coverage`, `htmlcov/`, `.DS_Store`, `.idea/`, and `.vscode/` are excluded

#### Scenario: Git-backed inventory applies built-in exclusions

**Given**: Git-backed discovery returns untracked files that are not ignored by Git
**And**: some of those paths are under review-gauntlet built-in excluded directories
**When**: review-gauntlet builds inventory from Git output
**Then**: built-in excluded paths are filtered out before classification
**And**: legitimate tracked or untracked project files outside built-in exclusions remain eligible for classification
