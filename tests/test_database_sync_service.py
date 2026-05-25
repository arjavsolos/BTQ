from __future__ import annotations

import unittest

from app.services.database_sync_service import DatabaseSyncService


class DatabaseSyncServiceTests(unittest.TestCase):
    def test_normalize_value_serializes_json_types(self) -> None:
        service = DatabaseSyncService()

        self.assertEqual(service._normalize_value({"a": 1}), '{"a": 1}')
        self.assertEqual(service._normalize_value([1, 2]), "[1, 2]")
        self.assertEqual(service._normalize_value("text"), "text")


if __name__ == "__main__":
    unittest.main()
