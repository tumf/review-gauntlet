## MODIFIED Requirements

### Requirement: Review execution SHALL support JSON and JSONC command adapter configuration

`review-gauntlet` SHALL support external review execution through a JSON or JSONC command adapter configuration. The configuration SHALL identify the command, argv arguments, optional output mode, and optional timeout/cwd/env settings without requiring in-process LLM SDK dependencies. The generated OCR-derived prompt SHALL be available as the `{prompt}` template variable for argv/env expansion. Command adapter configuration SHALL NOT include an `input` section or prompt-file transport mode. When output configuration is omitted, the adapter SHALL default to file-backed verdict output using the per-cell output artifact path.

#### Scenario: Review loads explicit adapter config

**Given**: an active review session
**And**: a valid command adapter configuration file at `/tmp/review-gauntlet.jsonc`
**When**: the developer runs `review-gauntlet review --config /tmp/review-gauntlet.jsonc`
**Then**: the review command uses that configuration for external command execution
**And**: no repository default config path overrides it

#### Scenario: Review discovers repository adapter config

**Given**: an active review session
**And**: no `--config` argument
**And**: config files may exist at `.review-gauntlet/config.jsonc`, `.review-gauntlet/config.json`, `review-gauntlet.jsonc`, and `review-gauntlet.json`
**When**: the developer runs `review-gauntlet review`
**Then**: the review command selects the first existing valid config in that precedence order

#### Scenario: JSONC config is accepted

**Given**: a command adapter config containing `//` line comments, `/* */` block comments, and trailing commas
**When**: the review command loads the config
**Then**: the config is parsed as JSONC
**And**: comment-like text inside JSON strings remains unchanged

#### Scenario: Missing command config does not implicitly execute a tool

**Given**: an active review session
**And**: no `--fixture` argument
**And**: no command adapter configuration is available
**When**: the developer runs `review-gauntlet review`
**Then**: the command fails with an actionable configuration error
**And**: it does not implicitly execute `opencode`, `claude`, `codex`, or any other default external tool

#### Scenario: Prompt template is accepted in argv

**Given**: a valid command adapter configuration whose `args` include `{prompt}`
**When**: the review command loads the config
**Then**: `{prompt}` is accepted as a supported template variable
**And**: `{prompt_file}` is rejected as an unsupported template variable
**And**: no `input` or `input.mode` field is accepted in the config

#### Scenario: Timeout defaults to 600 seconds

**Given**: a valid command adapter configuration without `timeout_seconds`
**When**: the review command loads the config
**Then**: the command adapter timeout defaults to 600 seconds
**And**: explicitly configured non-positive timeout values remain invalid

#### Scenario: Process context controls are optional

**Given**: a valid command adapter configuration without `cwd` or `env`
**When**: the review command invokes the command adapter
**Then**: the external process inherits the parent process cwd
**And**: the external process inherits the parent process environment without automatic fixed env injection
**And**: explicit `cwd` and `env` values remain supported when configured

#### Scenario: Output config defaults to file-json

**Given**: a valid command adapter configuration without an `output` section
**When**: the review command evaluates a cell
**Then**: the adapter treats the effective output mode as `file-json`
**And**: the effective verdict path is the deterministic per-cell output artifact path

### Requirement: Command adapter SHALL invoke external tools safely and preserve artifacts

The command adapter SHALL invoke configured tools without a shell, SHALL expose generated prompts through `{prompt}` argv/env template expansion, SHALL collect verdicts from stdout JSON when explicitly configured or from file JSON by default, and SHALL preserve per-cell artifacts for auditability. In file-json mode, stdout and stderr SHALL be preserved as logs but SHALL NOT be parsed or trusted as verdict input.

#### Scenario: Command adapter executes without shell

**Given**: a valid command adapter configuration with `command` and `args` as structured values
**When**: `review-gauntlet review` invokes the command adapter
**Then**: the process is executed without `shell=True`
**And**: configured arguments are passed as an argv array
**And**: shell metacharacters in paths, arguments, or generated prompt text are not interpreted by a shell

#### Scenario: Command adapter expands generated prompt as argv element

**Given**: a command adapter configuration whose args include `{prompt}`
**When**: a review cell is evaluated
**Then**: `review-gauntlet` expands `{prompt}` to the generated OCR-derived prompt as one argv element
**And**: the command adapter does not send the prompt through stdin as a transport side effect
**And**: the command adapter does not pass a prompt file as a transport side effect

#### Scenario: Command adapter supports stdout-json output

**Given**: a command adapter configuration explicitly using output mode `stdout-json`
**When**: a review cell is evaluated
**Then**: `review-gauntlet` validates the JSON verdict emitted to stdout
**And**: non-JSON stdout text remains invalid verdict output

#### Scenario: Command adapter defaults to file-json output

**Given**: a command adapter configuration without an output mode
**When**: a review cell is evaluated
**Then**: `review-gauntlet` validates the JSON verdict written to the default per-cell output file
**And**: stdout content is preserved but ignored for verdict parsing

#### Scenario: Command adapter supports explicit file-json output paths

**Given**: a command adapter configuration using output mode `file-json`
**And**: the configured output path includes `{output_file}` or another safe artifact-local path
**When**: a review cell is evaluated
**Then**: `review-gauntlet` validates the JSON verdict written to the output file

#### Scenario: File-json ignores noisy stdout

**Given**: a command adapter configuration using file-json output
**And**: the external command writes valid verdict JSON to the output file
**And**: the external command writes progress text, reasoning text, or other non-JSON text to stdout
**When**: a review cell is evaluated
**Then**: the adapter validates the output file verdict
**And**: stdout noise does not cause an invalid verdict failure

#### Scenario: Review artifacts are persisted per evaluated cell

**Given**: a review run evaluates a cell through the command adapter
**When**: command execution finishes or fails
**Then**: `review-gauntlet` preserves the generated prompt, command metadata, stdout, stderr, and verdict or failure details under a deterministic run/cell artifact path
**And**: the artifact path is associated with the review run evidence

#### Scenario: Unsafe output paths are rejected

**Given**: a command adapter configuration with file-json output
**When**: the configured output path would escape the intended run or cell artifact area through traversal, absolute unsafe paths, or unsupported template expansion
**Then**: the review command rejects the configuration or run before trusting the output
**And**: the cell is not marked reviewed

### Requirement: Command verdicts SHALL normalize through OCR comments only

External command adapter verdicts SHALL be JSON objects containing a `comments` array whose entries validate as OCR-style comments before they can affect findings or coverage. The verdict source SHALL be the configured output transport: stdout only for explicit stdout-json mode, and the verdict file for file-json mode.

#### Scenario: Valid command verdict creates finding occurrences

**Given**: a command adapter verdict with one valid OCR-style comment
**When**: `review-gauntlet review` processes the verdict
**Then**: the comment is validated against the OCR comment model
**And**: the existing finding normalization and deduplication path records the finding occurrence
**And**: the finding remains untriaged until explicitly marked

#### Scenario: Empty command verdict reviews the cell without findings

**Given**: a command adapter verdict with an empty `comments` array
**When**: `review-gauntlet review` processes the verdict
**Then**: the selected cell can be marked reviewed
**And**: no finding occurrence is created for that cell

#### Scenario: Invalid file-json verdict is not rescued from stdout

**Given**: a command adapter using file-json output
**And**: the configured output file is missing or contains an invalid verdict
**And**: stdout contains valid JSON or other text
**When**: `review-gauntlet review` processes the adapter result
**Then**: no finding occurrence is created from stdout
**And**: the selected cell is not marked reviewed
**And**: the review command exits non-zero with failure artifacts preserved

#### Scenario: Invalid command verdict is not trusted

**Given**: a command adapter returns unparseable JSON or a JSON object that does not match the verdict contract
**When**: `review-gauntlet review` processes the adapter result
**Then**: no finding occurrence is created from that result
**And**: the selected cell is not marked reviewed
**And**: the review command exits non-zero with failure artifacts preserved
