from __future__ import annotations

import unittest

from app.ingestion.market_data import MarketDataIngestor


class _ResponseStub:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class _SessionStub:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def get(self, url: str, params: dict, timeout: int) -> _ResponseStub:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return _ResponseStub(self.payload)


class MarketDataIngestorTests(unittest.TestCase):
    def test_fetch_daily_history_normalizes_ticker_and_validates_dates(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1736899200],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [40.0],
                                    "high": [41.0],
                                    "low": [39.5],
                                    "close": [40.5],
                                    "volume": [1000],
                                }
                            ],
                            "adjclose": [{"adjclose": [40.5]}],
                        },
                    }
                ]
            }
        }
        session = _SessionStub(payload)
        ingestor = MarketDataIngestor()
        ingestor.session = session

        records = ingestor.fetch_daily_history(" pfe ", "2025-01-15", "2025-01-16")

        self.assertEqual(records[0]["close"], 40.5)
        self.assertEqual(session.calls[0]["url"], "https://query1.finance.yahoo.com/v8/finance/chart/PFE")
        self.assertLess(session.calls[0]["params"]["period1"], session.calls[0]["params"]["period2"])

    def test_fetch_daily_history_rejects_bad_inputs_before_request(self) -> None:
        session = _SessionStub({})
        ingestor = MarketDataIngestor()
        ingestor.session = session

        with self.assertRaisesRegex(ValueError, "Invalid ticker"):
            ingestor.fetch_daily_history("$BAD", "2025-01-15", "2025-01-16")
        with self.assertRaisesRegex(ValueError, "Invalid date"):
            ingestor.fetch_daily_history("PFE", "01-15-2025", "2025-01-16")
        with self.assertRaisesRegex(ValueError, "end_date"):
            ingestor.fetch_daily_history("PFE", "2025-01-16", "2025-01-15")

        self.assertEqual(session.calls, [])

    def test_summarize_event_reaction_reports_selected_trade_date(self) -> None:
        ingestor = MarketDataIngestor()
        ingestor.fetch_event_window = lambda window: [
            {"trade_date": "2025-01-14", "close": 40.0},
            {"trade_date": "2025-01-15", "close": 42.0},
            {"trade_date": "2025-01-16", "close": 43.0},
        ]

        summary = ingestor.summarize_event_reaction("pfe", "2025-01-15")

        self.assertEqual(summary["ticker"], "PFE")
        self.assertEqual(summary["event_date"], "2025-01-15")
        self.assertEqual(summary["selected_trade_date"], "2025-01-15")
        self.assertEqual(summary["event_day_return"], 0.05)
        self.assertEqual(summary["post_window_return"], 0.02381)


if __name__ == "__main__":
    unittest.main()
