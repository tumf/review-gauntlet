## ADDED Requirements

### Requirement: Ready task prompts SHALL be file-scoped workflows

`review-gauntlet ready` SHALL return a concrete file-scoped task prompt when review cells or findings require action. `review-gauntlet run` SHALL pass that same prompt to the external agent. The prompt SHALL identify one target file and instruct the agent to process that file through triage, optional fix, and marking steps instead of issuing broad state-category instructions such as "triage all untriaged findings" or "review all pending cells."

#### Scenario: Pending review work returns file-scoped task

**Given**: an active session has pending or stale review cells for multiple files
**When**: the developer runs `review-gauntlet ready`
**Then**: the prompt identifies exactly one target `file_path`
**And**: the prompt lists the actionable review cells for that file
**And**: the prompt instructs the agent to review, triage any findings, fix if needed, and mark findings for that file
**And**: the prompt does not instruct the agent to process all pending or stale cells across the session.

#### Scenario: Findings return file-scoped triage-fix-mark task

**Given**: an active session has untriaged, reopened, confirmed, or fixed-pending findings across multiple files
**When**: the developer runs `review-gauntlet ready`
**Then**: the prompt identifies exactly one target `file_path`
**And**: the prompt lists the relevant finding IDs for that file
**And**: the prompt instructs the agent to triage, fix if needed, and mark those findings
**And**: the prompt does not instruct the agent to sweep findings in other files.

#### Scenario: Run uses same file-scoped task

**Given**: `review-gauntlet ready` would return a file-scoped prompt for `src/foo.py`
**When**: the developer runs `review-gauntlet run`
**Then**: the external agent receives the same file-scoped task prompt
**And**: one run step is scoped to that file's workflow.
