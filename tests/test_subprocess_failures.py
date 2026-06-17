from __future__ import annotations

import errno
from collections.abc import Sequence

from review_gauntlet.subprocess_failures import (
    RESOURCE_EXHAUSTION_HINT,
    is_resource_exhaustion_startup_error,
    subprocess_startup_failure_blocker,
    subprocess_startup_failure_details,
)


def _make_oserror(err: int, msg: str = "mock") -> OSError:
    e = OSError(msg)
    e.errno = err
    return e


class TestSubprocessStartupFailureDetails:
    def test_resource_exhaustion_emfile(self) -> None:
        err = _make_oserror(errno.EMFILE, "Too many open files")
        details = subprocess_startup_failure_details(["git", "status"], err)
        assert details["argv"] == ["git", "status"]
        assert details["errno"] == errno.EMFILE
        assert details["startup_error_reason"] == "resource_exhaustion"
        assert details["hint"] == RESOURCE_EXHAUSTION_HINT
        assert details["exception_type"] == "OSError"

    def test_resource_exhaustion_enfile(self) -> None:
        err = _make_oserror(errno.ENFILE)
        details = subprocess_startup_failure_details(["ls"], err)
        assert details["startup_error_reason"] == "resource_exhaustion"
        assert details["hint"] == RESOURCE_EXHAUSTION_HINT

    def test_non_resource_error(self) -> None:
        err = _make_oserror(errno.ENOENT, "No such file")
        details = subprocess_startup_failure_details(["missing-bin"], err)
        assert details["startup_error_reason"] == "os_error"
        assert "hint" not in details
        assert details["detail"] == "No such file"

    def test_argv_is_list_copy(self) -> None:
        argv: Sequence[str] = ("a", "b")
        details = subprocess_startup_failure_details(argv, _make_oserror(errno.ENOENT))
        assert details["argv"] == ["a", "b"]
        assert isinstance(details["argv"], list)


class TestIsResourceExhaustionStartupError:
    def test_emfile(self) -> None:
        assert is_resource_exhaustion_startup_error(_make_oserror(errno.EMFILE)) is True

    def test_enfile(self) -> None:
        assert is_resource_exhaustion_startup_error(_make_oserror(errno.ENFILE)) is True

    def test_enoent(self) -> None:
        assert is_resource_exhaustion_startup_error(_make_oserror(errno.ENOENT)) is False


class TestSubprocessStartupFailureBlocker:
    def test_resource_exhaustion_blocker(self) -> None:
        err = _make_oserror(errno.EMFILE, "Too many open files")
        msg = subprocess_startup_failure_blocker("git-diff", ["git", "diff"], err)
        assert msg.startswith("git-diff unavailable: subprocess startup failed")
        assert "startup_error_reason=resource_exhaustion" in msg
        assert f"errno={errno.EMFILE}" in msg
        assert f"hint={RESOURCE_EXHAUSTION_HINT}" in msg
        assert "detail=Too many open files" in msg

    def test_non_resource_blocker(self) -> None:
        err = _make_oserror(errno.ENOENT, "No such file")
        msg = subprocess_startup_failure_blocker("lint", ["eslint", "."], err)
        assert "startup_error_reason=os_error" in msg
        assert "hint=" not in msg
        assert "detail=No such file" in msg

    def test_errno_none(self) -> None:
        err = OSError("unknown")
        err.errno = None
        details = subprocess_startup_failure_details(["x"], err)
        assert details["startup_error_reason"] == "os_error"
        msg = subprocess_startup_failure_blocker("op", ["x"], err)
        assert "errno=" not in msg
