from __future__ import annotations

import unittest

from app.ingestion.clinical_trials import ClinicalTrialsIngestor


class ClinicalTrialsIngestorTests(unittest.TestCase):
    def test_extract_trial_record_builds_expected_fields(self) -> None:
        ingestor = ClinicalTrialsIngestor()
        study = {
            "hasResults": True,
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT00000001",
                    "briefTitle": "Example Study",
                    "officialTitle": "Example Study Official Title",
                    "organization": {"fullName": "Example Bio"},
                },
                "statusModule": {
                    "overallStatus": "COMPLETED",
                    "primaryCompletionDateStruct": {"date": "2025-01-15"},
                    "completionDateStruct": {"date": "2025-02-01"},
                    "studyFirstPostDateStruct": {"date": "2024-01-01"},
                },
                "sponsorCollaboratorsModule": {
                    "leadSponsor": {"name": "Example Bio", "class": "INDUSTRY"},
                },
                "conditionsModule": {
                    "conditions": ["Lung Cancer"],
                    "keywords": ["oncology", "tumor"],
                },
                "designModule": {
                    "studyType": "INTERVENTIONAL",
                    "phases": ["PHASE3"],
                    "enrollmentInfo": {"count": "120", "type": "ACTUAL"},
                    "designInfo": {
                        "allocation": "RANDOMIZED",
                        "interventionModel": "PARALLEL",
                        "primaryPurpose": "TREATMENT",
                        "maskingInfo": {"masking": "DOUBLE"},
                    },
                },
                "armsInterventionsModule": {
                    "interventions": [
                        {"type": "DRUG", "name": "Drug A", "description": "Example therapy"}
                    ]
                },
                "outcomesModule": {
                    "primaryOutcomes": [{"measure": "Overall Survival", "timeFrame": "12 months"}]
                },
                "eligibilityModule": {
                    "eligibilityCriteria": "Adults with disease",
                    "sex": "ALL",
                    "minimumAge": "18 Years",
                    "maximumAge": "80 Years",
                    "stdAges": ["ADULT"],
                },
                "contactsLocationsModule": {
                    "locations": [{"facility": "Site A", "country": "United States"}]
                },
                "referencesModule": {
                    "references": [{"pmid": "123456", "type": "RESULT", "citation": "Paper"}]
                },
                "descriptionModule": {
                    "briefSummary": "Primary endpoint is overall survival in lung cancer."
                },
                "oversightModule": {"isFdaRegulatedDrug": True},
            },
        }

        record = ingestor.extract_trial_record(study)

        self.assertEqual(record["nct_id"], "NCT00000001")
        self.assertEqual(record["sponsor_name"], "Example Bio")
        self.assertEqual(record["phase_score"], 3)
        self.assertEqual(record["event_date_candidate"], "2025-01-15")
        self.assertEqual(record["event_date_source"], "primary_completion_date")
        self.assertTrue(record["has_primary_outcomes"])
        self.assertTrue(record["has_locations"])
        self.assertTrue(record["has_results"])
        self.assertGreater(record["data_completeness_ratio"], 0)


if __name__ == "__main__":
    unittest.main()
