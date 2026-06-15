## ADDED Requirements

### Requirement: Git worktree session creation SHALL provision the worktree via the repository setup hook

When `review-gauntlet init --git-worktree` creates a linked session worktree,
the command SHALL, by default, run the repository worktree setup hook located at
`.wt/setup` relative to the newly created session worktree root, with the
working directory set to that worktree root, so the session worktree is
provisioned before agent steps execute in it.

A `--no-setup` flag SHALL suppress running the setup hook. The setup hook SHALL
only be attempted for `--git-worktree` sessions; non-Git-worktree `init`
SHALL NOT run the setup hook and SHALL NOT emit setup result data.

If the setup hook script is absent, setup SHALL be a no-op and `init` SHALL
succeed. If the setup hook exits non-zero or times out, `init` SHALL still
succeed, SHALL preserve the created worktree and session branch without
rollback, and SHALL surface the failure as a structured warning rather than an
error.

The command SHALL record the setup outcome under the `git_worktree` result as a
`setup` object in both the command output and the durable session metadata,
including whether setup ran, the script path, a skip reason when it did not run,
the process return code when it ran, and a human-readable warning when it failed.

#### Scenario: Setup hook runs by default on Git worktree init

**Given**: a repository whose worktree root contains an executable `.wt/setup` script
**When**: a developer runs `review-gauntlet init --git-worktree --format json`
**Then**: `.wt/setup` is executed with the working directory equal to the created session worktree root
**And**: the script's worktree-local side effects are present in the session worktree after init
**And**: the `git_worktree.setup` block reports `ran: true` with the script path and a `returncode` of 0

#### Scenario: --no-setup suppresses the setup hook

**Given**: a repository whose worktree root contains an executable `.wt/setup` script
**When**: a developer runs `review-gauntlet init --git-worktree --no-setup --format json`
**Then**: the session worktree is created but `.wt/setup` is not executed
**And**: the `git_worktree.setup` block reports `ran: false` with a skip reason indicating setup was disabled

#### Scenario: Missing setup hook is a no-op

**Given**: a repository whose worktree root has no `.wt/setup` script
**When**: a developer runs `review-gauntlet init --git-worktree --format json`
**Then**: `init` exits successfully and the session worktree is created
**And**: the `git_worktree.setup` block reports `ran: false` with a skip reason indicating the script is missing

#### Scenario: Setup failure warns and continues

**Given**: a repository whose worktree root contains a `.wt/setup` script that exits non-zero
**When**: a developer runs `review-gauntlet init --git-worktree --format json`
**Then**: `init` still exits successfully
**And**: the created worktree and session branch remain present and are not rolled back
**And**: the `git_worktree.setup` block reports `ran: true` with the non-zero `returncode` and a populated `warning`

#### Scenario: Non Git-worktree init does not run setup

**Given**: a repository whose worktree root contains an executable `.wt/setup` script
**When**: a developer runs `review-gauntlet init` without `--git-worktree`
**Then**: `.wt/setup` is not executed
**And**: the command output contains no `git_worktree` setup result
