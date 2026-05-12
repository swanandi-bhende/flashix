from __future__ import annotations

import concurrent.futures
import gzip
import json
import math
import random
import statistics
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from tests.integration_test import (
    DatasetMetadata,
    FundingRatePoint,
    GasPricePoint,
    HistoricalDataset,
    PricePoint,
    now_ms,
)


class HistoricalDataLoader:
    def __init__(self, fixture_path: str | Path = "tests/fixtures/historical_week.json.gz") -> None:
        self.fixture_path = Path(fixture_path)

    def _dataset_to_dict(self, dataset: HistoricalDataset) -> dict[str, Any]:
        return {
            "price_series": {
                symbol: [asdict(point) for point in series] for symbol, series in dataset.price_series.items()
            },
            "funding_rate_series": {
                symbol: [asdict(point) for point in series] for symbol, series in dataset.funding_rate_series.items()
            },
            "gas_price_series": [asdict(point) for point in dataset.gas_price_series],
            "metadata": asdict(dataset.metadata),
        }

    def _dict_to_dataset(self, payload: dict[str, Any]) -> HistoricalDataset:
        return HistoricalDataset(
            price_series={
                symbol: [PricePoint(**point) for point in series]
                for symbol, series in payload["price_series"].items()
            },
            funding_rate_series={
                symbol: [FundingRatePoint(**point) for point in series]
                for symbol, series in payload["funding_rate_series"].items()
            },
            gas_price_series=[GasPricePoint(**point) for point in payload["gas_price_series"]],
            metadata=DatasetMetadata(**payload["metadata"]),
        )

    def save_to_fixture(self, dataset: HistoricalDataset, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(self._dataset_to_dict(dataset), sort_keys=True).encode("utf-8")
        target.write_bytes(gzip.compress(raw))

    def load_from_fixture(self, path: str | Path) -> HistoricalDataset:
        payload = gzip.decompress(Path(path).read_bytes()).decode("utf-8")
        return self._dict_to_dataset(json.loads(payload))

    def _fetch_json(self, url: str, payload: dict[str, Any] | None = None, timeout: float = 12.0) -> dict[str, Any]:
        if payload is None:
            request = urllib.request.Request(url, headers={"User-Agent": "Flashix-Integration-Test"})
        else:
            encoded = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=encoded,
                headers={"Content-Type": "application/json", "User-Agent": "Flashix-Integration-Test"},
                method="POST",
            )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _fetch_hyperliquid_prices(self, symbol: str, start_ms: int, end_ms: int) -> list[PricePoint]:
        url = "https://api.hyperliquid.xyz/info"
        payload = {
            "type": "candleSnapshot",
            "req": {"coin": symbol, "interval": "1m", "startTime": start_ms, "endTime": end_ms},
        }
        try:
            response = self._fetch_json(url, payload=payload)
        except Exception:
            return []

        candles = response.get("candles") or response.get("data") or response.get("result") or []
        points: list[PricePoint] = []
        for candle in candles:
            timestamp = int(candle.get("t") or candle.get("timestamp") or candle.get("time") or start_ms)
            price = float(candle.get("c") or candle.get("close") or candle.get("price") or candle.get("mid") or 0.0)
            volume = float(candle.get("v") or candle.get("volume") or 0.0)
            points.append(
                PricePoint(
                    timestamp=timestamp,
                    symbol=symbol,
                    exchange="hyperliquid",
                    price=price,
                    volume=volume,
                    ohlcv={
                        "open": float(candle.get("o", price)),
                        "high": float(candle.get("h", price)),
                        "low": float(candle.get("l", price)),
                        "close": price,
                    },
                )
            )
        return points

    def _fetch_dydx_funding(self, symbol: str, start_ms: int, end_ms: int) -> list[FundingRatePoint]:
        market = symbol.lower().replace("-", "")
        url = f"https://api.dydx.exchange/v3/historical-funding/{urllib.parse.quote(market)}"
        try:
            response = self._fetch_json(url)
        except Exception:
            return []
        items = response.get("historicalFunding") or response.get("data") or response.get("result") or []
        points: list[FundingRatePoint] = []
        for item in items:
            timestamp = int(item.get("effectiveAt") or item.get("timestamp") or item.get("time") or start_ms)
            rate = float(item.get("rate") or item.get("fundingRate") or item.get("value") or 0.0)
            if start_ms <= timestamp <= end_ms:
                points.append(
                    FundingRatePoint(
                        timestamp=timestamp,
                        symbol=symbol,
                        exchange="dydx",
                        funding_rate=rate,
                    )
                )
        return points

    def _fetch_gas_history(self, start_ms: int, end_ms: int) -> list[GasPricePoint]:
        url = "https://api.etherscan.io/api?module=gastracker&action=gashistory"
        try:
            response = self._fetch_json(url)
        except Exception:
            return []
        items = response.get("result") or response.get("data") or []
        points: list[GasPricePoint] = []
        for item in items:
            timestamp = int(item.get("timestamp") or item.get("time") or start_ms)
            if start_ms <= timestamp <= end_ms:
                gas_price = float(item.get("gasPrice") or item.get("gas_price") or item.get("avgGasPrice") or 0.0)
                points.append(GasPricePoint(timestamp=timestamp, gas_price_gwei=gas_price, source="ETHERSCAN"))
        return points

    def fetch_historical_data(self, start_date: str, end_date: str, symbols: list[str]) -> HistoricalDataset:
        from datetime import datetime, timezone

        start_ms = int(datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc).timestamp() * 1000)
        end_ms = int(datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc).timestamp() * 1000)
        total_minutes = max(1, int((end_ms - start_ms) // 60000))
        source_apis = [
            "https://api.hyperliquid.xyz/info",
            "https://api.dydx.exchange/v3/historical-funding/{market}",
            "https://api.etherscan.io/api?module=gastracker&action=gashistory",
        ]

        price_series: dict[str, list[PricePoint]] = {symbol: [] for symbol in symbols}
        funding_rate_series: dict[str, list[FundingRatePoint]] = {symbol: [] for symbol in symbols}
        gas_price_series: list[GasPricePoint] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max(3, len(symbols) * 2)) as executor:
            future_map: dict[Any, tuple[str, str]] = {}
            for symbol in symbols:
                future_map[executor.submit(self._fetch_hyperliquid_prices, symbol, start_ms, end_ms)] = ("price", symbol)
                future_map[executor.submit(self._fetch_dydx_funding, symbol, start_ms, end_ms)] = ("funding", symbol)
            future_map[executor.submit(self._fetch_gas_history, start_ms, end_ms)] = ("gas", "")

            for future in concurrent.futures.as_completed(future_map):
                kind, symbol = future_map[future]
                try:
                    result = future.result()
                except Exception:
                    result = []
                if kind == "price":
                    price_series[symbol] = result or price_series[symbol]
                elif kind == "funding":
                    funding_rate_series[symbol] = result or funding_rate_series[symbol]
                else:
                    gas_price_series = result or gas_price_series

        if not any(price_series.values()) or not any(funding_rate_series.values()) or not gas_price_series:
            return self.generate_synthetic_fallback(n_days=max(1, total_minutes // 1440))

        dataset = HistoricalDataset(
            price_series=price_series,
            funding_rate_series=funding_rate_series,
            gas_price_series=gas_price_series,
            metadata=DatasetMetadata(
                start_date=start_date,
                end_date=end_date,
                total_minutes=total_minutes,
                symbols=symbols,
                source_apis=source_apis,
                fetch_timestamp=now_ms(),
            ),
        )
        try:
            self.save_to_fixture(dataset, self.fixture_path)
        except Exception:
            pass
        return dataset

    def generate_synthetic_fallback(self, n_days: int = 7) -> HistoricalDataset:
        symbols = ["BTC-USD-PERP", "ETH-USD-PERP", "SOL-USD-PERP"]
        start_ms = now_ms() - n_days * 24 * 60 * 60 * 1000
        minutes = n_days * 24 * 60
        dt = 1 / 1440.0
        mu = 0.0001
        sigma = 0.002
        random.seed(42)

        price_series: dict[str, list[PricePoint]] = {symbol: [] for symbol in symbols}
        funding_rate_series: dict[str, list[FundingRatePoint]] = {symbol: [] for symbol in symbols}
        gas_price_series: list[GasPricePoint] = []

        for symbol_index, symbol in enumerate(symbols):
            base_price = 20_000.0 if "BTC" in symbol else 1_500.0 if "ETH" in symbol else 120.0
            hyper_price = base_price * (1 + symbol_index * 0.01)
            dydx_price = base_price * (1 - symbol_index * 0.008)
            funding_rate = 0.0001 + symbol_index * 0.00002
            funding_mean = 0.0001
            funding_theta = 0.12
            funding_sigma = 0.00003
            for minute in range(minutes):
                timestamp = start_ms + minute * 60_000
                z1 = random.gauss(0.0, 1.0)
                z2 = random.gauss(0.0, 1.0)
                hyper_price *= math.exp((mu - (sigma**2) / 2.0) * dt + sigma * math.sqrt(dt) * z1)
                dydx_price *= math.exp((mu - (sigma**2) / 2.0) * dt + sigma * math.sqrt(dt) * z2)
                funding_rate += funding_theta * (funding_mean - funding_rate) * dt + funding_sigma * math.sqrt(dt) * random.gauss(0.0, 1.0)
                price_series[symbol].append(
                    PricePoint(
                        timestamp=timestamp,
                        symbol=symbol,
                        exchange="hyperliquid",
                        price=float(hyper_price),
                        volume=1_000.0 + minute % 250,
                        ohlcv={"open": float(hyper_price), "high": float(hyper_price * 1.001), "low": float(hyper_price * 0.999), "close": float(hyper_price)},
                    )
                )
                price_series[symbol].append(
                    PricePoint(
                        timestamp=timestamp,
                        symbol=symbol,
                        exchange="dydx",
                        price=float(dydx_price),
                        volume=900.0 + minute % 180,
                        ohlcv={"open": float(dydx_price), "high": float(dydx_price * 1.001), "low": float(dydx_price * 0.999), "close": float(dydx_price)},
                    )
                )
                if minute % 60 == 0:
                    funding_rate_series[symbol].append(
                        FundingRatePoint(
                            timestamp=timestamp,
                            symbol=symbol,
                            exchange="dydx",
                            funding_rate=float(funding_rate),
                        )
                    )
                gas_price_series.append(
                    GasPricePoint(
                        timestamp=timestamp,
                        gas_price_gwei=float(28.0 + 4.0 * random.random() + (symbol_index * 1.5)),
                        source="ETHERSCAN",
                    )
                )

        return HistoricalDataset(
            price_series=price_series,
            funding_rate_series=funding_rate_series,
            gas_price_series=gas_price_series,
            metadata=DatasetMetadata(
                start_date="synthetic-start",
                end_date=f"synthetic+{n_days}d",
                total_minutes=minutes,
                symbols=symbols,
                source_apis=["SYNTHETIC_GBM", "SYNTHETIC_OU", "SYNTHETIC_GAS"],
                fetch_timestamp=now_ms(),
            ),
        )
