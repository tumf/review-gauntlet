from __future__ import annotations

import errno
from collections.abc import Sequence

RESOURCE_EXHAUSTION_HINT = (
    "Subprocess startup exhausted available file descriptors. Retry with lower --concurrency "
    "or raise the process open-file limit."
)

_RESOURCE_EXHAUSTION_ERRNOS = {errno.EMFILE, errno.ENFILE}


def subprocess_startup_failure_details(argv: Sequence[str], error: OSError) -> dict[str, object]:
    """Return structured metadata for an OS-level subprocess startup failure."""
    details: dict[str, object] = {
        "argv": list(argv),
        "exception_type": error.__class__.__name__,
        "errno": error.errno,
        "detail": str(error),
    }
    if error.errno in _RESOURCE_EXHAUSTION_ERRNOS:
        details.update(
            {
                "startup_error_reason": "resource_exhaustion",
                "hint": RESOURCE_EXHAUSTION_HINT,
            }
        )
    else:
        details["startup_error_reason"] = "os_error"
    return details


def is_resource_exhaustion_startup_error(error: OSError) -> bool:
    return error.errno in _RESOURCE_EXHAUSTION_ERRNOS


def subprocess_startup_failure_blocker(operation: str, argv: Sequence[str], error: OSError) -> str:
    """Return a human-readable blocker with structured startup-failure fields."""
    details = subprocess_startup_failure_details(argv, error)
    parts = [
        f"{operation} unavailable: subprocess startup failed",
        f"startup_error_reason={details['startup_error_reason']}",
    ]
    if error.errno is not None:
        parts.append(f"errno={error.errno}")
    hint = details.get("hint")
    if isinstance(hint, str):
        parts.append(f"hint={hint}")
    detail = str(error)
    if detail:
        parts.append(f"detail={detail}")
    return "; ".join(parts)
