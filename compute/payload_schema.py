from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID
import re
import time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
HEX_HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid decimal value") from exc


def _enforce_precision(value: Decimal, max_places: int = 8) -> Decimal:
    exponent = -value.as_tuple().exponent
    if exponent > max_places:
        raise ValueError(f"decimal precision exceeds {max_places} places")
    return value

class InferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    opportunity_id: str = Field(..., max_length=36)
    dex_a: str
    dex_b: str
    price_a: Decimal
    price_b: Decimal
    borrow_amount_usdc: Decimal
    funding_rate_a: Decimal
    funding_rate_b: Decimal
    timestamp: int
    chain_id: int

    @field_validator("opportunity_id")
    @classmethod
    def validate_opportunity_id(cls, value: str) -> str:
        normalized = str(UUID(str(value)))
        if len(normalized) > 36:
            raise ValueError("opportunity_id too long")
        return normalized

    @field_validator("dex_a", mode="before")
    @classmethod
    def validate_dex_a(cls, v):
        if not EVM_ADDRESS_RE.match(v):
            raise ValueError("dex_a is not a valid EVM address")
        return v

    @field_validator("dex_b", mode="before")
    @classmethod
    def validate_dex_b(cls, v, values):
        if not EVM_ADDRESS_RE.match(v):
            raise ValueError("dex_b is not a valid EVM address")
        return v

    @field_validator("price_a", "price_b", "borrow_amount_usdc", mode="before")
    @classmethod
    def validate_positive(cls, v):
        value = _to_decimal(v)
        if value <= 0:
            raise ValueError("numeric fields must be positive")
        return _enforce_precision(value)

    @field_validator("borrow_amount_usdc", mode="before")
    @classmethod
    def validate_borrow_range(cls, v):
        value = _to_decimal(v)
        if value < 10 or value > 1_000_000:
            raise ValueError("borrow_amount_usdc out of range")
        return _enforce_precision(value)

    @field_validator("funding_rate_a", "funding_rate_b", mode="before")
    @classmethod
    def validate_funding(cls, v):
        value = _to_decimal(v)
        if value < Decimal("-1.0") or value > Decimal("1.0"):
            raise ValueError("funding_rate out of range")
        return _enforce_precision(value)

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v):
        now = int(time.time())
        if abs(now - int(v)) > 30:
            raise ValueError("timestamp is stale or too far in the future")
        return int(v)

    @field_validator("chain_id", mode="before")
    @classmethod
    def validate_chain(cls, v):
        import os

        cfg_chain = int(os.getenv("0G_CHAIN_ID", "16600"))
        if int(v) != cfg_chain:
            raise ValueError("chain_id does not match configured 0G chain id")
        return int(v)

    @model_validator(mode="after")
    def validate_distinct_dexes(self):
        if self.dex_a.lower() == self.dex_b.lower():
            raise ValueError("dex_a and dex_b must be different")
        return self

class InferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    opportunity_id: str
    decision: Literal["EXECUTE", "SKIP"]
    expected_profit_usdc: Decimal
    risk_score: float
    confidence: float
    reasoning_summary: str = Field(..., max_length=500)
    signal_hash: str
    tee_signature: str

    @field_validator("risk_score", "confidence", mode="before")
    @classmethod
    def validate_score(cls, v):
        f = float(v)
        if f < 0.0 or f > 1.0:
            raise ValueError("score must be between 0 and 1")
        return f

    @field_validator("signal_hash")
    @classmethod
    def validate_signal_hash(cls, value: str) -> str:
        if not HEX_HASH_RE.match(value):
            raise ValueError("signal_hash must be a 32-byte hex digest")
        return value.lower()

    @field_validator("tee_signature")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        if not value.startswith("0x") or len(value) < 10:
            raise ValueError("tee_signature must be hex encoded")
        return value.lower()
