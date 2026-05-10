from pydantic import BaseModel, Field, ValidationError, field_validator
from typing import Literal
from decimal import Decimal
import re
import time

EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

class InferenceRequest(BaseModel):
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

    @field_validator("dex_a", mode="before")
    def validate_dex_a(cls, v):
        if not EVM_ADDRESS_RE.match(v):
            raise ValueError("dex_a is not a valid EVM address")
        return v

    @field_validator("dex_b", mode="before")
    def validate_dex_b(cls, v, values):
        if not EVM_ADDRESS_RE.match(v):
            raise ValueError("dex_b is not a valid EVM address")
        if "dex_a" in values and values["dex_a"].lower() == v.lower():
            raise ValueError("dex_a and dex_b must be different")
        return v

    @field_validator("price_a", "price_b", "borrow_amount_usdc", mode="before")
    def validate_positive(cls, v):
        if Decimal(v) <= 0:
            raise ValueError("numeric fields must be positive")
        return Decimal(v).quantize(Decimal("0.00000001"))

    @field_validator("borrow_amount_usdc", mode="before")
    def validate_borrow_range(cls, v):
        v = Decimal(v)
        if v < 10 or v > 1_000_000:
            raise ValueError("borrow_amount_usdc out of range")
        return v

    @field_validator("funding_rate_a", "funding_rate_b", mode="before")
    def validate_funding(cls, v):
        v = Decimal(v)
        if v < Decimal("-1.0") or v > Decimal("1.0"):
            raise ValueError("funding_rate out of range")
        return v

    @field_validator("timestamp", mode="before")
    def validate_timestamp(cls, v):
        now = int(time.time())
        if abs(now - int(v)) > 30:
            raise ValueError("timestamp is stale or too far in the future")
        return int(v)

    @field_validator("chain_id", mode="before")
    def validate_chain(cls, v):
        cfg_chain = int(16600)  # testnet 0g chain id; replace from config if needed
        if int(v) != cfg_chain:
            raise ValueError("chain_id does not match configured 0G chain id")
        return int(v)

class InferenceResponse(BaseModel):
    opportunity_id: str
    decision: Literal["EXECUTE", "SKIP"]
    expected_profit_usdc: Decimal
    risk_score: float
    confidence: float
    reasoning_summary: str = Field(..., max_length=500)
    signal_hash: str
    tee_signature: str

    @field_validator("risk_score", "confidence", mode="before")
    def validate_score(cls, v):
        f = float(v)
        if f < 0.0 or f > 1.0:
            raise ValueError("score must be between 0 and 1")
        return f
