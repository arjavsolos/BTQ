from __future__ import annotations

import unittest

from app.services.historical_trial_event_service import HistoricalTrialEventService


class HistoricalTrialEventServiceTests(unittest.TestCase):
    def test_build_event_record_creates_model_ready_snapshot(self) -> None:
        service = HistoricalTrialEventService()
        analysis = {
            "analysis_version": "1.0",
            "trial": {
                "nct_id": "NCT00000001",
                "requested_nct_id": "NCT00000001",
                "brief_title": "Example Trial",
                "sponsor_name": "Pfizer Inc",
                "sponsor_class": "INDUSTRY",
                "overall_status": "COMPLETED",
                "phase_label": "PHASE3",
                "phase_score": 3,
                "study_type": "INTERVENTIONAL",
                "therapeutic_area": "Oncology",
                "enrollment_count": 240,
                "has_results": True,
                "data_completeness_score": 8,
                "data_completeness_ratio": 0.8,
                "event_date_candidate": "2025-01-15",
                "event_date_source": "primary_completion_date",
                "event_date_precision": "day",
                "intervention_types": ["DRUG"],
                "conditions": ["Lung Cancer"],
                "condition_keywords": ["oncology"],
                "primary_endpoint_measures": ["Overall Survival"],
                "secondary_endpoint_measures": ["Progression Free Survival"],
            },
            "sponsor_mapping": {
                "ticker": "PFE",
                "cik": "0000078003",
                "matched_company_name": "PFIZER INC",
                "confidence": 1.0,
                "match_type": "exact_normalized",
            },
            "fda_context": {
                "approval_records": [
                    {
                        "application_number": "NDA000001",
                        "brand_name": "Drug A",
                        "sponsor_name": "Pfizer Inc",
                        "submission_status": "APPROVED",
                        "submission_type": "ORIG",
                    }
                ]
            },
            "market_data": {
                "record_count": 12,
                "trade_start": "2025-01-08",
                "trade_end": "2025-01-22",
                "prior_close": 20.0,
                "event_close": 22.0,
                "latest_close": 23.0,
                "event_day_return": 0.1,
                "post_window_return": 0.045455,
            },
            "warnings": [],
        }

        record = service.build_event_record(analysis, analysis_id=17)

        self.assertEqual(record["analysis_id"], 17)
        self.assertEqual(record["nct_id"], "NCT00000001")
        self.assertEqual(record["mapped_ticker"], "PFE")
        self.assertEqual(record["approval_record_count"], 1)
        self.assertEqual(record["approval_application_numbers"], ["NDA000001"])
        self.assertTrue(record["is_model_ready"])
        self.assertEqual(record["feature_payload"]["mapping_features"]["match_type"], "exact_normalized")


if __name__ == "__main__":
    unittest.main()
