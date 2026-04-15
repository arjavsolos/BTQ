from __future__ import annotations

import unittest

from app.ingestion.sec_mapping import SecCompanyMapper


class SecCompanyMapperTests(unittest.TestCase):
    def test_match_sponsor_to_ticker_prefers_exact_normalized_match(self) -> None:
        mapper = SecCompanyMapper()
        mapper._registry = [
            {
                "company_name": "Acme Therapeutics, Inc.",
                "normalized_company_name": mapper._normalize_company_name("Acme Therapeutics, Inc."),
                "ticker": "ACME",
                "cik": "0000000001",
            },
            {
                "company_name": "Beta Bio Corp.",
                "normalized_company_name": mapper._normalize_company_name("Beta Bio Corp."),
                "ticker": "BETA",
                "cik": "0000000002",
            },
        ]

        result = mapper.match_sponsor_to_ticker("Acme Therapeutics")

        self.assertEqual(result.ticker, "ACME")
        self.assertEqual(result.match_type, "exact_normalized")
        self.assertEqual(result.confidence, 1.0)

    def test_match_sponsor_to_ticker_returns_candidates_when_no_confident_match(self) -> None:
        mapper = SecCompanyMapper()
        mapper._registry = [
            {
                "company_name": "Acme Therapeutics, Inc.",
                "normalized_company_name": mapper._normalize_company_name("Acme Therapeutics, Inc."),
                "ticker": "ACME",
                "cik": "0000000001",
            }
        ]

        result = mapper.match_sponsor_to_ticker("Unrelated Sponsor", minimum_confidence=0.95)

        self.assertIsNone(result.ticker)
        self.assertEqual(result.match_type, "no_match")
        self.assertTrue(result.alternatives)


if __name__ == "__main__":
    unittest.main()
