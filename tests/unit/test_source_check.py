"""AF gate: prove Python imports EPISTEMOS from the repo source tree, not a global."""

from __future__ import annotations

import epistemos


def test_source_is_repo_tree() -> None:
    # portable: an editable install from this repo resolves under `src/epistemos/`, whereas an
    # installed wheel would live at `site-packages/epistemos/` (no `src/`). Machine-independent.
    assert epistemos.__file__.replace("\\", "/").endswith("src/epistemos/__init__.py")
    assert epistemos.__version__ == "0.6.0"
