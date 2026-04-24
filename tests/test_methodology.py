from __future__ import annotations

import unittest

from app.research import METHODOLOGY_VERSION, build_methodology_snapshot, render_methodology_markdown


class MethodologyTestCase(unittest.TestCase):
    def test_snapshot_exposes_expected_sections(self) -> None:
        snapshot = build_methodology_snapshot()

        self.assertEqual(snapshot["methodology_version"], METHODOLOGY_VERSION)
        self.assertIn("project_identity", snapshot)
        self.assertIn("dataset_methodology", snapshot)
        self.assertIn("final_output_framework", snapshot)
        self.assertIn("event_date_methodology", snapshot)
        self.assertIn("sponsor_mapping_methodology", snapshot)
        self.assertIn("dataset_quality_methodology", snapshot)
        self.assertIn("evaluation_methodology", snapshot)

    def test_markdown_render_contains_key_sections(self) -> None:
        markdown = render_methodology_markdown()

        self.assertIn("# Methodology", markdown)
        self.assertIn("## Final Output Framework", markdown)
        self.assertIn("## Event-Date Methodology", markdown)
        self.assertIn("## Sponsor Mapping Methodology", markdown)
        self.assertIn("## Dataset Quality Methodology", markdown)


if __name__ == "__main__":
    unittest.main()
