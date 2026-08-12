"""EPISTEMOS Panel — the official operational interface (panel-v1).

A local-first, zero-egress web panel served by a stdlib HTTP+SSE server over an authorized
read-model of an :class:`~epistemos.core.Engine`. The panel is a *consumer*: authorization stays
server-side and the browser grants no authority (ADR-030). Run ``python -m epistemos.panel --demo``.
"""

from __future__ import annotations

from ..api.server import PanelHTTPServer, make_panel_server

__all__ = ["PanelHTTPServer", "make_panel_server"]
