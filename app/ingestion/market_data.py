import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


@dataclass(slots=True)
class EventWindow:
    ticker: str
    event_date: str
    pre_days: int = 5
    post_days: int = 5
    include_prepost: bool = False


class MarketDataIngestor:
    def __init__(
        self,
        use_env_proxy: bool = False,
        timeout: int = 30,
        user_agent: str = "BTQ Market Data Ingestor/1.0",
    ) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = use_env_proxy
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": user_agent,
            }
        )

    def _parse_date(self, value: str) -> datetime:
        return datetime.strptime(value, "%Y-%m-%d")

    def _to_unix(self, value: datetime) -> int:
        return int(value.replace(tzinfo=UTC).timestamp())

    def _extract_chart_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        result = ((payload.get("chart") or {}).get("result") or [None])[0]
        if result is None:
            return []
        timestamps = result.get("timestamp") or []
        quote = (((result.get("indicators") or {}).get("quote") or [None])[0]) or {}
        adjclose = (((result.get("indicators") or {}).get("adjclose") or [None])[0]) or {}

        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []
        adjusted = adjclose.get("adjclose") or []

        rows: list[dict[str, Any]] = []
        for index, ts in enumerate(timestamps):
            trade_date = datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d")
            rows.append(
                {
                    "trade_date": trade_date,
                    "open": opens[index] if index < len(opens) else None,
                    "high": highs[index] if index < len(highs) else None,
                    "low": lows[index] if index < len(lows) else None,
                    "close": closes[index] if index < len(closes) else None,
                    "adj_close": adjusted[index] if index < len(adjusted) else None,
                    "volume": volumes[index] if index < len(volumes) else None,
                }
            )
        return [row for row in rows if row.get("close") is not None]

    def fetch_daily_history(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        include_prepost: bool = False,
    ) -> list[dict[str, Any]]:
        start_dt = self._parse_date(start_date)
        end_dt = self._parse_date(end_date) + timedelta(days=1)
        params = {
            "period1": self._to_unix(start_dt),
            "period2": self._to_unix(end_dt),
            "interval": "1d",
            "includeAdjustedClose": "true",
            "includePrePost": str(include_prepost).lower(),
            "events": "div,splits,capitalGains",
        }
        response = self.session.get(YAHOO_CHART_URL.format(ticker=ticker), params=params, timeout=self.timeout)
        response.raise_for_status()
        return self._extract_chart_rows(response.json())

    def fetch_event_window(self, window: EventWindow) -> list[dict[str, Any]]:
        event_dt = self._parse_date(window.event_date)
        start_date = (event_dt - timedelta(days=max(7, window.pre_days * 3))).strftime("%Y-%m-%d")
        end_date = (event_dt + timedelta(days=max(7, window.post_days * 3))).strftime("%Y-%m-%d")
        return self.fetch_daily_history(
            ticker=window.ticker,
            start_date=start_date,
            end_date=end_date,
            include_prepost=window.include_prepost,
        )

    def summarize_event_reaction(
        self,
        ticker: str,
        event_date: str,
        pre_days: int = 5,
        post_days: int = 5,
    ) -> dict[str, Any]:
        records = self.fetch_event_window(
            EventWindow(
                ticker=ticker,
                event_date=event_date,
                pre_days=pre_days,
                post_days=post_days,
            )
        )
        if not records:
            return {
                "ticker": ticker,
                "event_date": event_date,
                "record_count": 0,
                "error": "No market data returned for event window.",
            }

        trade_dates = [row["trade_date"] for row in records]
        closes = [row["close"] for row in records]
        event_index = None
        for idx, trade_date in enumerate(trade_dates):
            if trade_date >= event_date:
                event_index = idx
                break
        if event_index is None:
            event_index = len(records) - 1

        prior_index = max(0, event_index - 1)
        prior_close = closes[prior_index]
        event_close = closes[event_index]
        latest_close = closes[-1]

        event_day_return = None
        post_window_return = None
        if prior_close not in {None, 0} and event_close is not None:
            event_day_return = round((event_close - prior_close) / prior_close, 6)
        if event_close not in {None, 0} and latest_close is not None:
            post_window_return = round((latest_close - event_close) / event_close, 6)

        return {
            "ticker": ticker,
            "event_date": event_date,
            "record_count": len(records),
            "trade_start": trade_dates[0],
            "trade_end": trade_dates[-1],
            "prior_close": prior_close,
            "event_close": event_close,
            "latest_close": latest_close,
            "event_day_return": event_day_return,
            "post_window_return": post_window_return,
            "records": records,
        }

    def export_records(self, records: list[dict[str, Any]], output_path: str, format: str = "jsonl") -> None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        format = format.lower()
        if format not in {"json", "jsonl"}:
            raise ValueError("format must be 'json' or 'jsonl'")
        if format == "json":
            output_file.write_text(json.dumps(records, indent=2, ensure_ascii=True), encoding="utf-8")
            return
        with output_file.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch historical equity data and event-window reactions")
    parser.add_argument("ticker")
    parser.add_argument("--event-date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--pre-days", type=int, default=5)
    parser.add_argument("--post-days", type=int, default=5)
    parser.add_argument("--out")
    parser.add_argument("--out-format", choices=["json", "jsonl"], default="json")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    ingestor = MarketDataIngestor()

    if args.event_date:
        payload = ingestor.summarize_event_reaction(
            ticker=args.ticker,
            event_date=args.event_date,
            pre_days=args.pre_days,
            post_days=args.post_days,
        )
        if args.out:
            ingestor.export_records(payload["records"], args.out, format=args.out_format)
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return

    if not args.start_date or not args.end_date:
        raise SystemExit("Provide either --event-date or both --start-date and --end-date.")
    records = ingestor.fetch_daily_history(
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    if args.out:
        ingestor.export_records(records, args.out, format=args.out_format)
    print(json.dumps({"count": len(records), "records": records}, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
