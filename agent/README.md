# Flashix Agent: Autonomous Arbitrage Executor

A LangChain-powered autonomous arbitrage agent that receives signals from 0G Compute's sealed inference engine and makes real-time execution decisions on perpetual arbitrage opportunities.

## Quick Start

### 1. Install Dependencies

```bash
pip install langchain==0.1.14 langchain-google-genai==0.0.11 langchain-core==0.1.37 google-generativeai==0.4.1 python-dotenv==1.0.0 pydantic==2.5.0
```

### 2. Configure Environment

```bash
cp ../.env.template .env
nano .env  # Fill in GEMINI_API_KEY and blockchain addresses
```

### 3. Test Connectivity

```bash
python tests/test_gemini_connection.py
```

### 4. Validate with Mock Signals

```bash
python tests/run_tests.py
```

## Architecture

**Mandatory 5-Step Reasoning Protocol**:

Signal → Validate → Assess → Learn → Decide → Log → Decision ID

### The Four Tools

1. **ValidateInferenceSignal**: Authenticate TEE signature, verify confidence & expiry
2. **AssessMarketConditions**: Evaluate gas, funding rates, liquidity, volatility
3. **QueryTradeHistory**: Analyze recent trades for pattern learning
4. **LogExecutionDecision**: Record decision immutably (required for execution authorization)

## Decision Criteria

Agent APPROVES if ALL criteria are met:
- ✓ Signal validation passed
- ✓ Confidence > 0.75
- ✓ Profit > $2.00 USDC
- ✓ No gas spike
- ✓ Liquidity adequate
- ✓ Signal not expired
- ✓ < 3 concurrent positions

## Key Files

- `flashloan_agent.py` - Main agent executor
- `agent_config.py` - Configuration with validation
- `agent_memory.py` - Trade history context
- `signal_processor.py` - Signal formatting & response parsing
- `decision_logger.py` - Auditability & metrics
- `prompts/system_prompt.py` - Master reasoning prompt
- `tools/` - Four custom LangChain tools

## Documentation

- Full Architecture: [`docs/AGENT_ARCHITECTURE.md`](../docs/AGENT_ARCHITECTURE.md)
- System Prompt: [`prompts/system_prompt.py`](prompts/system_prompt.py)

## Deployment

```bash
python tests/test_gemini_connection.py  # Verify API connectivity
python tests/run_tests.py  # Validate with 40+ mock signals
export DRY_RUN_MODE=false  # Only in production!
python -m flashloan_agent  # Start agent
```

## Hard Safety Rules

1. **Never execute without approval**: decision_id required from decision log
2. **When uncertain, reject**: Better to miss profit than execute bad trade
3. **Immutable audit trail**: All decisions logged to data/agent_decisions.jsonl
4. **Timeout enforcement**: 25-second maximum reasoning time
5. **Signature validation**: Invalid TEE signatures always rejected
- decision_logger.py
