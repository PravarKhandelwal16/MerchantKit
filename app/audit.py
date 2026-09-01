"""
Audit Logger — Part 6C.

Append-only audit trail for all tool calls, guardrail decisions, and
commerce actions. Written to the same SQLite database used by the rest of
the application.

Design principles:
- Completely decoupled from business logic: callers decide what to log.
- Append-only: existing rows are never modified.
- Structured JSON stored for arguments and results.
- No secrets (API keys, tokens) are ever written.
- Guardrail decisions carry an explicit APPROVED / REJECTED marker.
- Human-readable reason field on every record.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.database import get_db_connection, init_db


# ---------------------------------------------------------------------------
# Constants for policy_decision values
# ---------------------------------------------------------------------------

APPROVED = "APPROVED"
REJECTED = "REJECTED"
NA = "N/A"          # for actions that have no guardrail gate

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_REDACTED = "[REDACTED]"
_SECRET_KEYS = frozenset({
    "api_key", "apikey", "secret", "token", "password", "passwd",
    "authorization", "auth", "private_key", "razorpay_key",
    "razorpay_secret", "access_token", "refresh_token",
})


def _redact(obj: Any) -> Any:
    """
    Recursively walk a dict/list and replace any value whose key matches a
    known secret pattern with the string '[REDACTED]'.

    Called before serialising arguments or results to the audit log so that
    accidental secret leakage is prevented even if a caller passes them in.
    """
    if isinstance(obj, dict):
        return {
            k: _REDACTED if k.lower() in _SECRET_KEYS else _redact(v)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_redact(item) for item in obj]
    return obj


def _to_json(value: Any) -> Optional[str]:
    """Serialise a value to a compact JSON string, or None if value is None."""
    if value is None:
        return None
    try:
        return json.dumps(_redact(value), default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps({"_error": "not serialisable"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public data structure
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """
    A single record from the audit_logs table.

    All fields map 1-to-1 to columns so the entry can be returned directly
    to an API or dashboard without additional transformation.
    """
    id: int
    timestamp: str
    actor: str
    action: str
    arguments: Optional[Dict[str, Any]]
    result: Optional[Any]
    policy_decision: Optional[str]
    reason: Optional[str]
    success: bool
    error_code: Optional[str]


# ---------------------------------------------------------------------------
# AuditLogger service
# ---------------------------------------------------------------------------

class AuditLogger:
    """
    Append-only audit logger backed by the application SQLite database.

    Usage
    -----
    logger = AuditLogger()

    # Log a successful tool call
    logger.log_tool_call(
        actor="agent",
        action="add_to_cart",
        arguments={"cart_id": "...", "product_id": "M001", "quantity": 1},
        result={"cart_id": "...", "subtotal": 1299.0},
        success=True,
    )

    # Log a guardrail decision
    logger.log_guardrail(
        actor="gateway",
        action="create_order",
        policy_decision=APPROVED,
        reason="Order total ₹1299 is within the ₹5000 limit.",
        arguments={"cart_id": "..."},
    )

    # Retrieve recent entries
    entries = logger.get_recent(limit=20)
    """

    # ------------------------------------------------------------------
    # Core write methods
    # ------------------------------------------------------------------

    def log_tool_call(
        self,
        actor: str,
        action: str,
        arguments: Optional[Dict[str, Any]],
        result: Any = None,
        success: bool = True,
        error_code: Optional[str] = None,
        policy_decision: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> int:
        """
        Record a single tool execution attempt.

        Parameters
        ----------
        actor:
            Who initiated the call — e.g. "agent", "api", "system", "test".
        action:
            Tool or operation name, e.g. "search_products", "create_order".
        arguments:
            Tool arguments dict (secrets are auto-redacted before storage).
        result:
            Serialisable result returned by the tool, or None on failure.
        success:
            True if the tool completed without error.
        error_code:
            Machine-readable code on failure, e.g. "GUARDRAIL_VIOLATION".
        policy_decision:
            APPROVED, REJECTED, or N/A (None is coerced to N/A).
        reason:
            Human-readable explanation of the outcome.

        Returns
        -------
        int
            The auto-incremented row id of the inserted audit record.
        """
        return self._insert(
            actor=actor,
            action=action,
            arguments=arguments,
            result=result,
            success=success,
            error_code=error_code,
            policy_decision=policy_decision or NA,
            reason=reason,
        )

    def log_guardrail(
        self,
        actor: str,
        action: str,
        policy_decision: str,
        reason: str,
        arguments: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Record a guardrail check outcome (APPROVED or REJECTED).

        The `details` dict from GuardrailResult is merged into result storage
        so the auditor can see exact checked values (e.g. total_amount, limit).
        No secret values should ever appear in guardrail details.

        Returns
        -------
        int
            Row id of the inserted record.
        """
        return self._insert(
            actor=actor,
            action=action,
            arguments=arguments,
            result=details,
            success=(policy_decision == APPROVED),
            error_code=None if policy_decision == APPROVED else "GUARDRAIL_VIOLATION",
            policy_decision=policy_decision,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_recent(self, limit: int = 50) -> List[AuditEntry]:
        """
        Return the most recent audit entries, newest first.

        Parameters
        ----------
        limit:
            Maximum number of entries to return (capped internally at 500).
        """
        limit = min(max(1, limit), 500)
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """
                SELECT id, timestamp, actor, action, arguments, result,
                       policy_decision, reason, success, error_code
                FROM audit_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [_row_to_entry(row) for row in rows]
        finally:
            conn.close()

    def get_by_action(self, action: str, limit: int = 50) -> List[AuditEntry]:
        """Return recent entries for a specific action/tool name."""
        limit = min(max(1, limit), 500)
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """
                SELECT id, timestamp, actor, action, arguments, result,
                       policy_decision, reason, success, error_code
                FROM audit_logs
                WHERE action = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (action, limit),
            ).fetchall()
            return [_row_to_entry(row) for row in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _insert(
        self,
        actor: str,
        action: str,
        arguments: Optional[Dict[str, Any]],
        result: Any,
        success: bool,
        error_code: Optional[str],
        policy_decision: str,
        reason: Optional[str],
    ) -> int:
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO audit_logs
                    (timestamp, actor, action, arguments, result,
                     policy_decision, reason, success, error_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_now(),
                    actor,
                    action,
                    _to_json(arguments),
                    _to_json(result),
                    policy_decision,
                    reason,
                    1 if success else 0,
                    error_code,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Row → AuditEntry conversion
# ---------------------------------------------------------------------------

def _row_to_entry(row: Any) -> AuditEntry:
    def _parse(s: Optional[str]) -> Any:
        if s is None:
            return None
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return s

    return AuditEntry(
        id=row["id"],
        timestamp=row["timestamp"],
        actor=row["actor"],
        action=row["action"],
        arguments=_parse(row["arguments"]),
        result=_parse(row["result"]),
        policy_decision=row["policy_decision"],
        reason=row["reason"],
        success=bool(row["success"]),
        error_code=row["error_code"],
    )


# ---------------------------------------------------------------------------
# Module-level default logger instance
# ---------------------------------------------------------------------------

audit_logger = AuditLogger()
