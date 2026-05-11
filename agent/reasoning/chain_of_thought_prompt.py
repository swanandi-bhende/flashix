"""Master prompt for structured arbitrage reasoning."""

try:
    from langchain_core.prompts import ChatPromptTemplate
except ImportError:  # pragma: no cover - local dry-run fallback
    class ChatPromptTemplate:  # type: ignore[no-redef]
        @classmethod
        def from_messages(cls, messages):
            instance = cls()
            instance.messages = messages
            return instance

        def invoke(self, values):
            return values

from agent.prompts.system_prompt import SYSTEM_PROMPT

REASONING_INSTRUCTIONS = """When evaluating any arbitrage signal, you MUST reason through EXACTLY FIVE sections in this order. Do not skip sections. Do not merge sections. Each section must contain a 'narrative' field written as a complete English sentence AND a 'data' field containing the numeric values as a JSON object. OUTPUT FORMAT: Wrap your entire reasoning in a JSON object with keys: opportunity_analysis, cost_breakdown, profit_calculation, risk_assessment, final_decision. Each key maps to an object with 'narrative' (string) and 'data' (object with numeric fields).

Opportunity Analysis section:
Calculate gross_spread_percent as abs(price_a - price_b) / min(price_a, price_b) * 100. State which DEX you will go long and which you will short. Write narrative in format: 'Signal shows {spread}% price discrepancy between {dex_a} (long at ${price_a}) and {dex_b} (short at ${price_b}). Borrow amount: ${borrow_amount} USDC. Signal confidence: {confidence}. Expires in {expiry} seconds.'

Cost Breakdown section:
Calculate each cost component individually using the exact formulas: flashloan_fee = borrow_amount * 0.0009; slippage = borrow_amount * slippage_rate (use 0.002 for amounts < $10k, 0.0035 for $10k–$50k, 0.005 for > $50k); collateral_cost = collateral_required * daily_rate / 24 * estimated_hold_hours; gas_cost from current gas price * 180000 units converted to USDC. Write narrative in format: 'Flashloan fee: 0.09% = ${flashloan_fee}. Slippage: {slippage_pct}% = ${slippage_usdc}. Collateral cost: ${collateral_cost}. Gas: ${gas_cost}. Total cost: {total_pct}% = {total_usdc}.'

Profit Calculation section:
Calculate gross_spread_pct, total_cost_pct, net_profit_pct = gross_spread_pct - total_cost_pct, net_profit_usdc, profit_after_gas_usdc, and break_even_spread_pct. Write narrative in format: 'Gross spread: {gross_spread}%. Total cost: {total_cost}%. Net profit: {net_profit}% = ${net_profit_usdc}.'

Risk Assessment section:
Convert vix_equivalent_score into a qualitative label and assess funding rate volatility, execution risk, liquidity risk, and gas spike risk. Explicitly list risk_factors and mitigating_factors. Write narrative in format: 'VIX-equivalent: {score}/100 ({label}). Funding rate volatility: {funding_label}. Execution risk: {execution_label}. Liquidity risk: {liquidity_label}. Gas spike risk: {gas_label}.'

Final Decision section:
Decide APPROVE or REJECT using the numeric thresholds supplied in the signal. If rejecting, set rejection_reason. If approving, state expected profit after gas and expected execution time. Write narrative in format: 'APPROVE execution. Expected profit after gas: ${profit_after_gas}. Expected execution time: {seconds} seconds.' or a rejection equivalent."""

CHAIN_OF_THOUGHT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            f"{SYSTEM_PROMPT}\n\nREASONING_INSTRUCTIONS:\n{REASONING_INSTRUCTIONS}\n",
        ),
        (
            "human",
            "{input}",
        ),
    ]
)
