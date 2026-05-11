# Trace API

The reasoning trace API runs on port `8001` and exposes the full audit trail for every executed trade.

## Base URL

```bash
http://localhost:8001
```

## GET /traces

List recent traces.

Query parameters:
- `limit` default `10`, max `100`
- `decision` optional filter: `APPROVE` or `REJECT`
- `min_profit` optional minimum expected profit in USDC
- `since_timestamp` optional Unix timestamp filter

Example:

```bash
curl "http://localhost:8001/traces?limit=5&decision=APPROVE"
```

Sample response:

```json
[
  {
    "trace_id": "4a3d6f77-0c72-4bda-8d45-b1d49b6f2b61",
    "opportunity_id": "opp_20260511_001",
    "opportunity_analysis": {
      "narrative": "Signal shows 4.2% price discrepancy between Hyperliquid (long at $43210.5) and dYdX (short at $43028.2). Borrow amount: $10000 USDC. Signal confidence: 0.91. Expires in 28 seconds.",
      "data": {
        "price_dex_a": 43210.5,
        "price_dex_b": 43028.2,
        "long_dex": "Hyperliquid",
        "short_dex": "dYdX",
        "gross_spread_usdc": 420.0,
        "gross_spread_percent": 4.2,
        "borrow_amount_usdc": 10000.0,
        "signal_confidence": 0.91,
        "signal_expiry_seconds": 28
      }
    },
    "cost_breakdown": {
      "narrative": "Flashloan fee: 0.09% = $9.00. Slippage: 0.20% = $20.00. Collateral cost: $0.63. Gas: $3.20. Total cost: 0.33% = $32.83.",
      "data": {
        "flashloan_fee_pct": 0.09,
        "flashloan_fee_usdc": 9.0,
        "slippage_estimate_pct": 0.2,
        "slippage_estimate_usdc": 20.0,
        "collateral_rate_pct_per_day": 0.15,
        "collateral_cost_usdc": 0.63,
        "gas_price_gwei": 30.0,
        "gas_cost_usdc": 3.2,
        "total_cost_pct": 0.33,
        "total_cost_usdc": 32.83
      }
    },
    "profit_calculation": {
      "narrative": "Gross spread: 4.2%. Total cost: 0.33%. Net profit: 3.87% = $387.17.",
      "data": {
        "gross_spread_pct": 4.2,
        "total_cost_pct": 0.33,
        "net_profit_pct": 3.87,
        "net_profit_usdc": 387.17,
        "profit_after_gas_usdc": 383.97,
        "break_even_spread_pct": 0.33
      }
    },
    "risk_assessment": {
      "narrative": "VIX-equivalent: 28/100 (LOW). Funding rate volatility: LOW. Execution risk: LOW. Liquidity risk: LOW. Gas spike risk: LOW.",
      "data": {
        "vix_equivalent_score": 28.0,
        "funding_rate_volatility": "LOW",
        "execution_risk": "LOW",
        "liquidity_risk": "LOW",
        "gas_spike_risk": "LOW",
        "overall_risk": "LOW",
        "risk_factors": [],
        "mitigating_factors": ["tight spread", "deep liquidity"]
      }
    },
    "final_decision": {
      "narrative": "APPROVE execution. Expected profit after gas: $383.97. Expected execution time: 8 seconds.",
      "data": {
        "decision": "APPROVE",
        "rejection_reason": null,
        "expected_profit_usdc": 383.97,
        "expected_execution_time_seconds": 8,
        "decision_confidence": 0.91,
        "conditions": ["signal_valid", "profit_positive", "gas_stable"]
      }
    },
    "total_reasoning_ms": 182.4,
    "gemini_tokens_used": 0,
    "created_at": 1746950400,
    "model_version": "arbitrage_scorer_v1"
  }
]
```

## GET /traces/{opportunity_id}

Return the complete reasoning trace for a specific opportunity.

Example:

```bash
curl "http://localhost:8001/traces/opp_20260511_001"
```

This response includes the same trace fields plus `full_trace_json`.

## GET /traces/stats

Return aggregate audit statistics.

Example:

```bash
curl "http://localhost:8001/traces/stats"
```

Sample response:

```json
{
  "total_traces": 128,
  "approve_count": 47,
  "reject_count": 81,
  "avg_net_profit_approved": 5.42,
  "avg_vix_approved": 29.6,
  "avg_reasoning_ms": 181.8,
  "most_common_rejection_reason": "Confidence below threshold"
}
```

## GET /traces/{opportunity_id}/verify

Re-run numeric consistency checks on a stored trace.

Example:

```bash
curl "http://localhost:8001/traces/opp_20260511_001/verify"
```

Sample response:

```json
{
  "consistent": true,
  "warnings": []
}
```
