"""Startup reconciliation for sessions."""

from __future__ import annotations

from .manager import SessionManager


def reconcile_on_startup(session_manager: SessionManager) -> dict:
    """Called at startup to reconcile sessions. Delegates to session_manager.reconcile()."""
    return session_manager.reconcile()
