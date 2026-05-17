from __future__ import annotations

import unittest

from run import build_parser


class RunParserTests(unittest.TestCase):
    def test_build_parser_supports_sponsor_mapping_review_export_command(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "export-sponsor-mapping-reviews",
                "--limit",
                "25",
                "--offset",
                "5",
                "--review-status",
                "pending",
                "--suggested-ticker",
                "PFE",
                "--reviewer-email",
                "arjaviyer@gmail.com",
                "--format",
                "jsonl",
                "--include-summary",
            ]
        )

        self.assertEqual(args.command, "export-sponsor-mapping-reviews")
        self.assertEqual(args.limit, 25)
        self.assertEqual(args.offset, 5)
        self.assertEqual(args.review_status, "pending")
        self.assertEqual(args.suggested_ticker, "PFE")
        self.assertEqual(args.reviewer_email, "arjaviyer@gmail.com")
        self.assertEqual(args.format, "jsonl")
        self.assertTrue(args.include_summary)

    def test_build_parser_supports_event_date_quality_backfill_filters(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "build-historical-dataset",
                "--limit",
                "50",
                "--min-event-date-quality-score",
                "80",
                "--event-date-quality-tier",
                "high",
            ]
        )

        self.assertEqual(args.command, "build-historical-dataset")
        self.assertEqual(args.limit, 50)
        self.assertEqual(args.min_event_date_quality_score, 80)
        self.assertEqual(args.event_date_quality_tier, "high")


if __name__ == "__main__":
    unittest.main()
