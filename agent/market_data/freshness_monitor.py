"""Freshness benchmarking, staleness logging, and data gap detection."""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

from agent.market_data import (
    DataGap,
    FreshnessViolation,
    LatencyBenchmark,
    MAX_STALENESS_MS,
    OracleSource,
    RawPriceSample,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FreshnessViolationRecord:
    """SQLite-serializable freshness violation record."""
    violation_id: str
    source: str
    symbol: str
    staleness_ms: int
    threshold_ms: int
    fetch_latency_ms: float
    recorded_at: int


class FreshnessMonitor:
    """
    Continuously measures oracle data freshness and logs violations for post-trade analysis.
    
    Detects staleness violations, data gaps, and generates freshness benchmarks.
    """

    def __init__(self, data_dir: str = "data"):
        """
        Initialize freshness monitor with SQLite database.
        
        Args:
            data_dir: Directory for freshness_violations.db
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.data_dir / "freshness_violations.db"
        self._init_database()

        # Per-source latency tracking (last 1000 samples)
        self.latency_samples: dict[OracleSource, deque] = {
            source: deque(maxlen=1000)
            for source in OracleSource
        }

        self._lock = threading.RLock()

    def _init_database(self) -> None:
        """Create freshness_violations table if it doesn't exist."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS freshness_violations (
                    violation_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    staleness_ms INTEGER NOT NULL,
                    threshold_ms INTEGER NOT NULL,
                    fetch_latency_ms REAL NOT NULL,
                    recorded_at INTEGER NOT NULL
                )
                """
            )
            conn.commit()
            conn.close()
            _logger.info("FRESHNESS_MONITOR_DATABASE_INITIALIZED: %s", self.db_path)
        except Exception as e:
            _logger.error("FRESHNESS_MONITOR_DB_INIT_ERROR: %s", str(e))

    def record_sample_received(self, sample: RawPriceSample) -> None:
        """
        Record a received price sample and check for staleness violations.
        
        If staleness exceeds MAX_STALENESS_MS, log a violation for post-trade analysis.
        
        Args:
            sample: RawPriceSample to check
        """
        # Check for violation
        if sample.staleness_ms > MAX_STALENESS_MS:
            self._log_violation(
                source=sample.source,
                symbol=sample.symbol,
                staleness_ms=sample.staleness_ms,
                fetch_latency_ms=sample.fetch_latency_ms,
            )
        else:
            # Record latency sample for benchmarking
            with self._lock:
                if sample.source in self.latency_samples:
                    self.latency_samples[sample.source].append(sample.fetch_latency_ms)

    def _log_violation(
        self,
        source: OracleSource,
        symbol: str,
        staleness_ms: int,
        fetch_latency_ms: float,
    ) -> None:
        """
        Log a freshness violation to the database.
        
        Args:
            source: Oracle source
            symbol: Trading pair symbol
            staleness_ms: Observed staleness
            fetch_latency_ms: Network fetch latency
        """
        violation_id = f"{source.value}_{symbol}_{int(time.time() * 1000)}"
        recorded_at = int(time.time())

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                """
                INSERT INTO freshness_violations
                (violation_id, source, symbol, staleness_ms, threshold_ms, fetch_latency_ms, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    violation_id,
                    source.value,
                    symbol,
                    staleness_ms,
                    MAX_STALENESS_MS,
                    fetch_latency_ms,
                    recorded_at,
                ),
            )
            conn.commit()
            conn.close()

            _logger.warning(
                "FRESHNESS_VIOLATION_RECORDED: source=%s, symbol=%s, staleness_ms=%d, threshold=%d",
                source.value,
                symbol,
                staleness_ms,
                MAX_STALENESS_MS,
            )
        except Exception as e:
            _logger.error("FRESHNESS_VIOLATION_LOG_ERROR: %s", str(e))

    def detect_data_gaps(
        self,
        symbol: str,
        expected_interval_ms: int = 500,
        samples: Optional[list[RawPriceSample]] = None,
    ) -> list[DataGap]:
        """
        Detect gaps in market data where samples are missing.
        
        A gap is flagged when consecutive samples have >3x expected interval between them.
        
        Args:
            symbol: Trading pair symbol
            expected_interval_ms: Expected time between samples
            samples: Samples to analyze (if None, would get from window_store)
            
        Returns:
            List of detected data gaps
        """
        if not samples or len(samples) < 2:
            return []

        gaps = []
        sorted_samples = sorted(samples, key=lambda s: s.fetched_at_ms)

        for i in range(1, len(sorted_samples)):
            prev_time = sorted_samples[i - 1].fetched_at_ms
            curr_time = sorted_samples[i].fetched_at_ms
            interval_ms = curr_time - prev_time

            if interval_ms > expected_interval_ms * 3:
                gap_duration = interval_ms - expected_interval_ms
                missing_estimate = gap_duration // expected_interval_ms

                gaps.append(
                    DataGap(
                        symbol=symbol,
                        gap_start_ms=prev_time,
                        gap_end_ms=curr_time,
                        duration_ms=gap_duration,
                        missing_samples_estimate=int(missing_estimate),
                    )
                )

        return gaps

    def benchmark_source_latency(self) -> dict[OracleSource, LatencyBenchmark]:
        """
        Compute latency percentile statistics per oracle source.
        
        Returns:
            Dict mapping OracleSource to LatencyBenchmark with p50, p95, p99, max
        """
        import numpy as np

        benchmarks = {}

        with self._lock:
            for source, latencies in self.latency_samples.items():
                if not latencies:
                    continue

                latencies_list = list(latencies)
                try:
                    benchmarks[source] = LatencyBenchmark(
                        p50_ms=float(np.percentile(latencies_list, 50)),
                        p95_ms=float(np.percentile(latencies_list, 95)),
                        p99_ms=float(np.percentile(latencies_list, 99)),
                        max_ms=float(np.max(latencies_list)),
                        sample_count=len(latencies_list),
                    )
                except Exception as e:
                    _logger.warning("LATENCY_BENCHMARK_ERROR: source=%s, error=%s", source.value, str(e))

        return benchmarks

    def generate_freshness_report(
        self, hours: int = 1
    ) -> dict:
        """
        Generate comprehensive freshness report with violations, gaps, and recommendations.
        
        Args:
            hours: Number of hours to include in report
            
        Returns:
            Dict with violation_count, violation_rate_pct, source_freshness, gaps, recommendation
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Count violations in last N hours
            since_timestamp = int(time.time()) - (hours * 3600)
            cursor.execute(
                """
                SELECT COUNT(*) as violation_count,
                       source,
                       AVG(staleness_ms) as avg_staleness,
                       MAX(staleness_ms) as max_staleness
                FROM freshness_violations
                WHERE recorded_at > ?
                GROUP BY source
                ORDER BY violation_count DESC
                """,
                (since_timestamp,),
            )

            violations_by_source = cursor.fetchall()
            total_violations = sum(row[0] for row in violations_by_source)

            # Get total samples to compute violation rate
            cursor.execute(
                "SELECT COUNT(*) FROM freshness_violations WHERE recorded_at > ?",
                (since_timestamp,),
            )
            total_samples = cursor.fetchone()[0]

            violation_rate = (
                100.0 * total_violations / max(1, total_samples)
            )

            conn.close()

            # Generate recommendation
            if total_violations == 0:
                recommendation = "System operating normally. All oracle sources are consistently fresh."
            elif total_violations < 10:
                recommendation = "Minor staleness detected. Monitor closely but no action needed yet."
            else:
                # Find worst source
                worst_source = violations_by_source[0][1] if violations_by_source else "UNKNOWN"
                recommendation = (
                    f"{worst_source} is experiencing staleness issues. Consider increasing weight "
                    "to alternative sources or investigating network connectivity."
                )

            return {
                "total_violations": total_violations,
                "violation_rate_pct": violation_rate,
                "violations_by_source": [
                    {
                        "source": row[1],
                        "count": row[0],
                        "avg_staleness_ms": row[2],
                        "max_staleness_ms": row[3],
                    }
                    for row in violations_by_source
                ],
                "hours_analyzed": hours,
                "recommendation": recommendation,
            }

        except Exception as e:
            _logger.error("FRESHNESS_REPORT_ERROR: %s", str(e))
            return {
                "total_violations": 0,
                "violation_rate_pct": 0.0,
                "violations_by_source": [],
                "recommendation": f"Error generating report: {str(e)}",
            }


__all__ = ["FreshnessMonitor", "FreshnessViolationRecord"]
