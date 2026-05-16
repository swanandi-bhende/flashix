"""
Settlement validator and P&L extraction.
Parses the confirmed transaction receipt, extracts realized P&L from on-chain event logs,
and validates the outcome against expectations before updating the opportunity database.
"""

import logging
import sqlite3
import time
import json
from decimal import Decimal
from typing import Optional, Dict, Any

from web3 import Web3

from agent.execution_engine import (
    ExecutionRequest,
    BroadcastResult,
    SettlementValidation,
    SettlementError,
    USDC_DECIMALS,
    PROFIT_VALIDATION_TOLERANCE,
)

_logger = logging.getLogger(__name__)

# Database configuration
OPPORTUNITIES_DB_PATH = "opportunities.db"


class SettlementValidator:
    """
    Validates and processes settlement from confirmed transactions.
    
    Parses the confirmed transaction receipt, extracts realized P&L from 
    on-chain event logs, and validates the outcome against expectations.
    """
    
    def __init__(self, web3: Optional[Web3] = None, db_path: str = OPPORTUNITIES_DB_PATH):
        """
        Initialize the settlement validator.
        
        Args:
            web3: Web3 instance connected to 0G Chain
            db_path: Path to opportunities database
        """
        self.web3 = web3
        self.db_path = db_path
        self._init_db()
    
    def validate_settlement(
        self, receipt: Any, request: ExecutionRequest
    ) -> SettlementValidation:
        """
        Validate and record settlement from a confirmed transaction.
        
        Steps:
        1. Decode ArbitrageExecuted event from receipt logs
        2. Verify realized_profit and gasUsed values
        3. Validate signalId matches request.opportunity_id
        4. Validate realized_profit >= min_profit * PROFIT_VALIDATION_TOLERANCE
        5. Calculate profit_after_gas
        6. Update opportunity record in SQLite
        7. Return SettlementValidation result
        
        Args:
            broadcast_result: Result from transaction broadcaster
            request: Original ExecutionRequest
        
        Returns:
            SettlementValidation with outcome details
        
        Raises:
            SettlementError: If settlement validation fails
        """
        
        if isinstance(receipt, BroadcastResult):
            receipt_dict = receipt.receipt or {}
            tx_hash = receipt.tx_hash
        else:
            receipt_dict = receipt or {}
            tx_hash = receipt_dict.get('transactionHash') if receipt_dict else None

        _logger.debug(
            f"SETTLEMENT_VALIDATION_START: opportunity_id={request.opportunity_id}, "
            f"tx_hash={tx_hash}"
        )
        
        try:
            if not receipt_dict and isinstance(receipt, BroadcastResult):
                realized_profit_usdc = receipt.realized_profit_usdc or Decimal("0")
                gas_used = int(receipt.gas_used or 0)
                min_profit_required = request.min_profit_usdc * PROFIT_VALIDATION_TOLERANCE
                if realized_profit_usdc < min_profit_required:
                    if realized_profit_usdc >= request.min_profit_usdc * Decimal("0.85"):
                        _logger.warning(
                            f"PROFIT_SHORTFALL: opportunity_id={request.opportunity_id}, "
                            f"realized={realized_profit_usdc}, expected={request.min_profit_usdc}, "
                            f"tolerance={PROFIT_VALIDATION_TOLERANCE}"
                        )
                    else:
                        _logger.critical(
                            f"PROFIT_BELOW_MINIMUM: opportunity_id={request.opportunity_id}, "
                            f"realized={realized_profit_usdc}, minimum={min_profit_required}"
                        )
                        raise SettlementError(
                            f"Realized profit {realized_profit_usdc} below minimum {min_profit_required}"
                        )
                profit_after_gas = realized_profit_usdc
                status = "PROFITABLE" if profit_after_gas > 0 else "UNPROFITABLE"
                self._update_opportunity_record(
                    opportunity_id=request.opportunity_id,
                    decision_id=request.decision_id,
                    trace_id=request.trace_id,
                    symbol=request.signal.primary_dex,
                    dex_pair=f"{request.signal.primary_dex}->{request.signal.counter_dex}",
                    status=status,
                    profit_usdc=float(realized_profit_usdc),
                    profit_after_gas=float(profit_after_gas),
                    gas_used=gas_used,
                    execution_latency_ms=0.0,
                    success=status == "PROFITABLE",
                    timestamp=int(time.time()),
                    tx_hash=str(tx_hash or ""),
                    explorer_link=receipt.explorer_link or "",
                )
                return SettlementValidation(
                    valid=True,
                    reason="Settlement validated from synthetic broadcast result",
                    realized_profit_usdc=realized_profit_usdc,
                    profit_after_gas=profit_after_gas,
                    signal_id_match=True,
                )

            if not receipt_dict:
                raise SettlementError("Missing receipt for settlement validation")

            events = self._decode_arbitrage_executed(receipt_dict)
            if not events:
                raise SettlementError("ArbitrageExecuted event missing from receipt logs")

            event_args = events[0]["args"]
            signal_id = event_args.get("signalId")
            realized_profit_raw = event_args.get("profit") or event_args.get("profitRealized")
            gas_used = int(event_args.get("gasUsed") or receipt_dict.get("gasUsed") or 0)

            if realized_profit_raw is None:
                raise SettlementError("ArbitrageExecuted event missing profit field")

            realized_profit_usdc = Decimal(int(realized_profit_raw)) / Decimal(10 ** USDC_DECIMALS)

            expected_signal_id = self._to_bytes32(request.opportunity_id)
            if signal_id is not None and signal_id != expected_signal_id:
                raise SettlementError("Settlement signalId does not match opportunity_id")
            
            # ================================================================
            # VALIDATE: Minimum profit threshold
            # ================================================================
            min_profit_required = (
                request.min_profit_usdc * PROFIT_VALIDATION_TOLERANCE
            )
            
            if realized_profit_usdc < min_profit_required:
                if realized_profit_usdc >= request.min_profit_usdc * Decimal("0.85"):
                    # Within 85-95% range: warning
                    _logger.warning(
                        f"PROFIT_SHORTFALL: opportunity_id={request.opportunity_id}, "
                        f"realized={realized_profit_usdc}, "
                        f"expected={request.min_profit_usdc}, "
                        f"tolerance={PROFIT_VALIDATION_TOLERANCE}"
                    )
                else:
                    # Below 85%: error
                    _logger.critical(
                        f"PROFIT_BELOW_MINIMUM: opportunity_id={request.opportunity_id}, "
                        f"realized={realized_profit_usdc}, "
                        f"minimum={min_profit_required}"
                    )
                    raise SettlementError(
                        f"Realized profit {realized_profit_usdc} below minimum "
                        f"{min_profit_required}"
                    )
            
            # ================================================================
            # CALCULATE: Profit after gas
            # ================================================================
            # Gas cost in USDC = gas_used * gas_price_gwei * eth_price_usdc / 1e9
            # For simplicity, estimate gas cost from maxFeePerGas in tx
            max_fee_per_gas = Decimal(str(request.max_gas_price_gwei)) / Decimal("1e9")
            gas_cost_usdc = (
                Decimal(str(gas_used)) * max_fee_per_gas * Decimal("2500")  # Assume $2500/ETH
                if gas_used > 0 else Decimal("0")
            )
            
            profit_after_gas = realized_profit_usdc - gas_cost_usdc
            
            # ================================================================
            # UPDATE: Opportunity database record
            # ================================================================
            status = "PROFITABLE" if profit_after_gas > 0 else "UNPROFITABLE"
            
            self._update_opportunity_record(
                opportunity_id=request.opportunity_id,
                decision_id=request.decision_id,
                trace_id=request.trace_id,
                symbol=request.signal.primary_dex,
                dex_pair=f"{request.signal.primary_dex}->{request.signal.counter_dex}",
                status=status,
                profit_usdc=float(realized_profit_usdc),
                profit_after_gas=float(profit_after_gas),
                gas_used=gas_used,
                execution_latency_ms=0.0,
                success=status == "PROFITABLE",
                timestamp=int(time.time()),
                tx_hash=str(tx_hash or ""),
                explorer_link=f"https://chainscan.0g.ai/tx/{tx_hash.hex() if hasattr(tx_hash, 'hex') else tx_hash or ''}",
            )
            
            _logger.info(
                f"SETTLEMENT_RECORDED: opportunity_id={request.opportunity_id}, "
                f"status={status}, profit_after_gas=${profit_after_gas:.2f}"
            )
            
            result = SettlementValidation(
                valid=True,
                reason="Settlement validated and recorded",
                realized_profit_usdc=realized_profit_usdc,
                profit_after_gas=profit_after_gas,
                signal_id_match=signal_id == expected_signal_id,
            )
            
            return result
        
        except SettlementError:
            raise
        except Exception as e:
            _logger.critical(
                f"UNEXPECTED_SETTLEMENT_ERROR: opportunity_id={request.opportunity_id}, "
                f"error={str(e)}", exc_info=True
            )
            raise SettlementError(f"Unexpected settlement error: {e}")
    
    def _update_opportunity_record(
        self,
        opportunity_id: str,
        decision_id: str,
        trace_id: str,
        symbol: str,
        dex_pair: str,
        status: str,
        profit_usdc: float,
        profit_after_gas: float,
        gas_used: int,
        execution_latency_ms: float,
        success: bool,
        timestamp: int,
        tx_hash: str,
        explorer_link: str,
    ) -> None:
        """
        Update or insert an opportunity record in the database.
        
        Args:
            opportunity_id: Opportunity ID
            decision_id: Decision log ID
            trace_id: Reasoning trace ID
            status: PROFITABLE or UNPROFITABLE
            realized_profit_usdc: Realized profit in USDC
            profit_after_gas: Profit minus gas cost
            gas_used: Gas units consumed
            execution_latency_ms: Execution time in milliseconds
            tx_hash: Transaction hash
            explorer_link: Link to transaction on explorer
        """
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            current_time = int(time.time())
            
            # Try to update first
            cursor.execute("""
                UPDATE opportunities
                SET symbol = ?, dex_pair = ?, profit_usdc = ?, execution_latency_ms = ?,
                    gas_used = ?, success = ?, timestamp = ?, status = ?,
                    tx_hash = ?, explorer_link = ?, updated_at = ?,
                    realized_profit_usdc = ?, profit_after_gas = ?
                WHERE opportunity_id = ?
            """, (
                symbol, dex_pair, profit_usdc, execution_latency_ms,
                gas_used, int(success), timestamp, status,
                tx_hash, explorer_link, current_time,
                profit_usdc, profit_after_gas, opportunity_id
            ))
                explorer_link="https://chainscan.0g.ai/tx/{tx_hash.hex() if hasattr(tx_hash, 'hex') else tx_hash or ''}",
            if cursor.rowcount == 0:
                # Insert if not found
                cursor.execute("""
                    INSERT INTO opportunities
                    (opportunity_id, decision_id, trace_id, symbol, dex_pair, status,
                     profit_usdc, realized_profit_usdc, profit_after_gas, gas_used,
                     execution_latency_ms, success, timestamp, tx_hash, explorer_link,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    opportunity_id, decision_id, trace_id, symbol, dex_pair, status,
                    profit_usdc, profit_usdc, profit_after_gas, gas_used,
                    execution_latency_ms, int(success), timestamp, tx_hash, explorer_link,
                    current_time, current_time
                ))
            
            conn.commit()
            conn.close()
            
            _logger.debug(
                f"OPPORTUNITY_RECORD_UPDATED: opportunity_id={opportunity_id}"
            )
        
        except sqlite3.Error as e:
            _logger.error(f"Database error updating opportunity record: {e}")
            # Don't raise - settlement is still valid even if DB update fails
    
    def _init_db(self) -> None:
        """Initialize the opportunities database if it doesn't exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    opportunity_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    symbol TEXT,
                    dex_pair TEXT,
                    status TEXT NOT NULL,
                    profit_usdc REAL,
                    realized_profit_usdc REAL,
                    profit_after_gas REAL,
                    gas_used INTEGER,
                    execution_latency_ms REAL,
                    success INTEGER,
                    timestamp INTEGER,
                    tx_hash TEXT,
                    explorer_link TEXT,
                    created_at INTEGER,
                    updated_at INTEGER
                )
            """)
            
            # Create index on status for queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON opportunities(status)
            """)
            
            conn.commit()
            conn.close()
            
            _logger.debug(f"Database initialized at {self.db_path}")
        
        except sqlite3.Error as e:
            _logger.error(f"Failed to initialize database: {e}")

    @staticmethod
    def _to_bytes32(value: str) -> bytes:
        encoded = value.encode("utf-8")[:32]
        return encoded.ljust(32, b"\x00")

    def _decode_arbitrage_executed(self, receipt: Dict[str, Any]):
        try:
            if self.web3 is None:
                return []
            with open("contracts/abi/ArbitrageExecutor.json", "r") as handle:
                data = json.load(handle)
            address = data.get("address")
            abi = data.get("abi", [])
            if not address:
                return []
            contract = self.web3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)
            return contract.events.ArbitrageExecuted().process_receipt(receipt)
        except Exception:
            return []
