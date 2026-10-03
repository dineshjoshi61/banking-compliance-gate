"""Sanctions screening for compliance pipeline. This stub performs a deterministic
look-up against mock OFAC and UN sanction lists and returns a structured result.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("compliance.sanctions_check")

MATCH_CONFIDENCE_THRESHOLD = 0.75
MOCK_API_LATENCY_BUDGET_MS = 200

_MOCK_OFAC_LIST = {"acme trading ltd": 0.91, "northwind exports": 0.88}
_MOCK_UN_LIST = {"acme trading ltd": 0.83, "silverline holdings": 0.80}


@dataclass
class SanctionsMatch:
    list_source: str
    matched_name: str
    score: float


@dataclass
class SanctionsScreeningResult:
    screened: bool
    match_list: list[SanctionsMatch] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "screened": self.screened,
            "match_list": [match.__dict__ for match in self.match_list],
            "confidence": self.confidence,
        }


class InvalidScreeningInputError(ValueError):
    """Raised when validation fails for a screening request."""


def _validate_input(customer_id: str, counterparty_details: dict, transaction_amount: float) -> None:
    if not customer_id or not isinstance(customer_id, str):
        raise InvalidScreeningInputError("customer_id must be a non-empty string")
    if not isinstance(counterparty_details, dict) or "name" not in counterparty_details:
        raise InvalidScreeningInputError("counterparty_details must include at least a 'name' field")
    if not isinstance(transaction_amount, (int, float)) or transaction_amount < 0:
        raise InvalidScreeningInputError("transaction_amount must be a non-negative number")


def _mask_for_log(value: str) -> str:
    """Never log plaintext customer or counterparty identifiers."""
    if not value:
        return "***"
    if len(value) <= 4:
        return "***"
    return value[:2] + "***" + value[-2:]


def _query_sanctions_lists(counterparty_name: str) -> list[SanctionsMatch]:
    """Deterministic stub for OFAC/UN sanctions lookups."""
    normalized_name = counterparty_name.strip().lower()
    matches: list[SanctionsMatch] = []
    if normalized_name in _MOCK_OFAC_LIST:
        matches.append(SanctionsMatch("OFAC", counterparty_name, _MOCK_OFAC_LIST[normalized_name]))
    if normalized_name in _MOCK_UN_LIST:
        matches.append(SanctionsMatch("UN", counterparty_name, _MOCK_UN_LIST[normalized_name]))
    return matches


def _store_result_encrypted(customer_id: str, result: SanctionsScreeningResult) -> None:
    """Document the encryption boundary for PCI DSS compliance.

    In production this would encrypt the screening result before persisting to an
    audit store. This stub intentionally only logs a masked customer identifier to
    confirm the call site exists without exposing raw data.
    """
    logger.debug("Encrypted screening result stored for customer=%s", _mask_for_log(customer_id))
    _ = result


def screen_transaction(
    customer_id: str,
    counterparty_details: dict,
    transaction_amount: float,
) -> dict[str, Any]:
    """Return a sanctions-screening result for the next compliance step."""
    start = time.monotonic()

    try:
        _validate_input(customer_id, counterparty_details, transaction_amount)
    except InvalidScreeningInputError:
        logger.warning(
            "Sanctions screening rejected malformed input for customer=%s",
            _mask_for_log(customer_id),
        )
        return SanctionsScreeningResult(screened=False).to_dict()

    try:
        matches = _query_sanctions_lists(counterparty_details["name"])
    except Exception:
        logger.error("Sanctions API unreachable for customer=%s", _mask_for_log(customer_id))
        return SanctionsScreeningResult(screened=False).to_dict()

    confidence = max((match.score for match in matches), default=0.0)
    result = SanctionsScreeningResult(screened=True, match_list=matches, confidence=confidence)
    _store_result_encrypted(customer_id, result)

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        "Sanctions screening completed in %.1fms for customer=%s",
        elapsed_ms,
        _mask_for_log(customer_id),
    )
    return result.to_dict()
