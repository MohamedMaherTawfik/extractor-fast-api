from __future__ import annotations

import subprocess
import sys

from backend.core.runtime_capabilities import _pyarrow_failure_status


def test_backend_import_does_not_load_pyarrow() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import backend.main; print('pyarrow' in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "False"


def test_windows_application_control_failure_has_stable_status() -> None:
    exc = ImportError(
        "DLL load failed while importing lib: "
        "An Application Control policy has blocked this file."
    )
    assert _pyarrow_failure_status(exc) == "BLOCKED_BY_WINDOWS_APPLICATION_CONTROL"
