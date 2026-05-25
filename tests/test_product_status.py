from __future__ import annotations

import unittest

from app.research import (
    PRODUCT_STATUS_VERSION,
    build_product_status_snapshot,
    render_product_status_markdown,
)


class ProductStatusTests(unittest.TestCase):
    def test_product_status_snapshot_captures_final_capabilities(self) -> None:
        snapshot = build_product_status_snapshot()

        capability_names = {item["name"] for item in snapshot["core_capabilities"]}

        self.assertEqual(snapshot["status_version"], PRODUCT_STATUS_VERSION)
        self.assertEqual(snapshot["production_readiness"]["status"], "demo_ready")
        self.assertIn("modeled_success_probability", capability_names)
        self.assertIn("expected_reaction_comparison", capability_names)
        self.assertIn("production_readiness_scoring", capability_names)
        self.assertIn("python run.py project-status --format markdown", snapshot["demo_commands"])

    def test_product_status_markdown_is_recruiter_readable(self) -> None:
        markdown = render_product_status_markdown()

        self.assertIn("# BTQ Project Status", markdown)
        self.assertIn("## Production Readiness", markdown)
        self.assertIn("`demo_ready`", markdown)
        self.assertIn("## Core Capabilities", markdown)
        self.assertIn("modeled_success_probability", markdown)
        self.assertIn("## Demo Commands", markdown)


if __name__ == "__main__":
    unittest.main()
