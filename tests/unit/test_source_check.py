"""AF gate: prove Python imports EPISTEMOS from the repo source tree, not a global."""

from __future__ import annotations

import epistemos


def test_source_is_repo_tree() -> None:
    assert epistemos.__file__.endswith("/Users/AI/Projects/epistemos/src/epistemos/__init__.py")
    assert epistemos.__version__ == "0.3.0"
