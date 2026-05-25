from __future__ import annotations

import unittest

from app.api import TrialAnalysisRequest, analyze_trial_route, create_app, health_route


class _TrialAnalysisServiceStub:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def analyze_trial(
        self,
        nct_id: str,
        approval_limit: int = 5,
        market_pre_days: int = 5,
        market_post_days: int = 5,
        include_raw_trial: bool = False,
        save_to_db: bool = False,
    ) -> dict:
        self.calls.append(
            {
                "nct_id": nct_id,
                "approval_limit": approval_limit,
                "market_pre_days": market_pre_days,
                "market_post_days": market_post_days,
                "include_raw_trial": include_raw_trial,
                "save_to_db": save_to_db,
            }
        )
        final_summary = {
            "conclusion": "stronger_than_expected",
            "headline": "Observed market reaction was stronger than historical expectation.",
        }
        return {
            "status": "success",
            "summary": {
                "nct_id": nct_id,
                "analysis_readiness": {
                    "status": "production_ready",
                    "score": 96,
                    "blockers": [],
                    "cautions": [],
                },
                "bayesian_probability": {
                    "status": "available",
                    "posterior_probability_percent": 68.4,
                    "confidence_tier": "moderate",
                },
                "expected_reaction_status": "available",
                "expected_reaction_profile": {
                    "expected_direction": "positive",
                    "confidence_tier": "moderate",
                },
                "market_expected_reaction_comparison": {
                    "classification": "stronger_than_expected",
                    "return_gap": 0.043,
                },
                "final_comparison_summary": final_summary,
            },
            "final_comparison_summary": final_summary,
        }


class _ReadinessServiceStub:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def check_readiness(self, include_database: bool = True) -> dict:
        self.calls.append({"include_database": include_database})
        return {
            "status": "ok",
            "checks": {
                "python": {"status": "ok"},
                "database": {"status": "skipped" if not include_database else "ok"},
            },
        }


class ApiRouteTests(unittest.TestCase):
    def test_trial_analysis_request_normalizes_payload(self) -> None:
        request = TrialAnalysisRequest.from_payload(
            {
                "nct_id": " NCT00000001 ",
                "approval_limit": "7",
                "market_pre_days": "3",
                "market_post_days": "9",
                "include_raw_trial": True,
                "save_to_db": False,
                "summary_only": True,
            }
        )

        self.assertEqual(request.nct_id, "NCT00000001")
        self.assertEqual(request.approval_limit, 7)
        self.assertEqual(request.market_pre_days, 3)
        self.assertEqual(request.market_post_days, 9)
        self.assertTrue(request.include_raw_trial)
        self.assertTrue(request.summary_only)

    def test_analyze_trial_route_exposes_final_comparison_fields(self) -> None:
        service = _TrialAnalysisServiceStub()

        response = analyze_trial_route(
            {
                "nct_id": "NCT00000001",
                "approval_limit": 7,
                "market_pre_days": 3,
                "market_post_days": 9,
                "include_raw_trial": True,
                "summary_only": True,
            },
            service=service,
        )

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["request"]["nct_id"], "NCT00000001")
        self.assertEqual(response["summary"]["analysis_readiness"]["status"], "production_ready")
        self.assertEqual(response["summary"]["bayesian_probability"]["posterior_probability_percent"], 68.4)
        self.assertEqual(response["summary"]["expected_reaction_status"], "available")
        self.assertEqual(response["summary"]["expected_reaction_profile"]["expected_direction"], "positive")
        self.assertEqual(
            response["summary"]["market_expected_reaction_comparison"]["classification"],
            "stronger_than_expected",
        )
        self.assertEqual(
            response["summary"]["final_comparison_summary"]["headline"],
            "Observed market reaction was stronger than historical expectation.",
        )
        self.assertEqual(
            service.calls[0],
            {
                "nct_id": "NCT00000001",
                "approval_limit": 7,
                "market_pre_days": 3,
                "market_post_days": 9,
                "include_raw_trial": True,
                "save_to_db": False,
            },
        )

    def test_analyze_trial_route_rejects_missing_final_comparison_fields(self) -> None:
        class IncompleteService:
            def analyze_trial(self, **_: object) -> dict:
                return {"status": "success", "summary": {"nct_id": "NCT00000001"}}

        with self.assertRaises(ValueError):
            analyze_trial_route({"nct_id": "NCT00000001"}, service=IncompleteService())

    def test_health_route_runs_fast_readiness_check_by_default(self) -> None:
        service = _ReadinessServiceStub()

        response = health_route(service=service)

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["service"], "btq-api")
        self.assertFalse(response["include_database"])
        self.assertEqual(response["readiness"]["checks"]["database"]["status"], "skipped")
        self.assertEqual(service.calls[0], {"include_database": False})

    def test_health_route_can_include_database_check(self) -> None:
        service = _ReadinessServiceStub()

        response = health_route(include_database=True, service=service)

        self.assertTrue(response["include_database"])
        self.assertEqual(response["readiness"]["checks"]["database"]["status"], "ok")
        self.assertEqual(service.calls[0], {"include_database": True})

    def test_create_app_exposes_route_registry(self) -> None:
        app = create_app()

        self.assertEqual(app["name"], "btq-api")
        self.assertIs(app["routes"]["analyze_trial"], analyze_trial_route)
        self.assertIs(app["routes"]["health"], health_route)


if __name__ == "__main__":
    unittest.main()
