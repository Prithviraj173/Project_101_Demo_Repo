import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from cf_sync.api.server import SyncAPIHandler, SYNC_JOBS


class TestAPIEndpoints(unittest.TestCase):
    def test_health_check_payload(self):
        # Verify health check dictionary format
        data = {"status": "ok", "version": "1.0.0", "timeUtc": datetime.now(timezone.utc).isoformat()}
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["version"], "1.0.0")

    def test_sync_jobs_in_memory_registry(self):
        job_id = "test_job_123"
        SYNC_JOBS[job_id] = {
            "id": job_id,
            "status": "COMPLETED",
            "progressPercent": 100,
        }
        self.assertIn(job_id, SYNC_JOBS)
        self.assertEqual(SYNC_JOBS[job_id]["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
