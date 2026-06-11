# Design: File-backed command verdicts by default

## Current Behavior

`CommandOutputConfig` currently defaults to `stdout-json`. In that mode, the adapter captures stdout and validates the entire stdout stream as one `VerdictPayload` JSON object. This is fragile for agent-style CLIs because they often print progress, reasoning, or summaries before or after machine-readable output.

`file-json` already exists, but configs must opt into it and must provide a path. The per-cell artifact path already includes a deterministic `verdict.json`, making it a natural default.

## Target Behavior

The default output contract becomes file-backed:

1. If `adapter.output` is omitted, the effective output mode is `file-json`.
2. If file-json output path is omitted, the effective path is the per-cell `{output_file}` artifact path.
3. The external process may print anything to stdout/stderr; these streams are saved but not parsed as verdicts in file-json mode.
4. The adapter validates only the configured output file as the verdict source.
5. Explicit `stdout-json` remains available for deterministic non-agent commands.

## Prompt Contract

The generated prompt should include the verdict transport expectation. For file-json, it should state:

- write exactly one JSON object matching the contract to the effective output file;
- overwrite/create that file;
- stdout/stderr are ignored for verdict parsing and may be used only for logs;
- do not wrap the JSON in markdown inside the file.

The prompt builder may receive the effective output path so the instruction can include the concrete location.

## Safety and Auditability

The adapter continues to execute without a shell and preserve artifacts. `stdout.txt` and `stderr.txt` remain useful audit logs, but coverage/finding state is affected only by the validated verdict file. Missing or invalid verdict files preserve failure artifacts and keep the selected cell incomplete.

## Compatibility

Existing configs that explicitly set `stdout-json` continue to behave as before. Existing configs that set file-json with an explicit path continue to work subject to the current safe-path checks. The only intentional compatibility shift is for omitted `output`, which now means the safer file-json default.
