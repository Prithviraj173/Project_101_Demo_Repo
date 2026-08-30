import unittest
from unittest.mock import MagicMock, patch
from cf_sync.core.models import (
    Problem,
    Submission,
    SubmissionSyncStatus,
    SyncConfig,
    SyncFilter,
    VerdictMode,
)
from cf_sync.services.sync_service import SyncService


class TestSyncService(unittest.TestCase):
    def setUp(self):
        self.mock_cf_client = MagicMock()
        self.mock_cf_client.validate_handle.return_value = {"handle": "tourist", "rating": 3800}

        self.sub1 = Submission(
            id=1001,
            contest_id=2000,
            contest_name="Round 990",
            creation_time_seconds=1700000000,
            relative_time_seconds=100,
            problem=Problem(contest_id=2000, index="A", name="Problem A"),
            author_members=["tourist"],
            programming_language="GNU C++20",
            verdict="OK",
            source_code="#include <iostream>",
            source_available=True,
        )
        self.sub2 = Submission(
            id=1002,
            contest_id=2000,
            contest_name="Round 990",
            creation_time_seconds=1700000200,
            relative_time_seconds=200,
            problem=Problem(contest_id=2000, index="B", name="Problem B"),
            author_members=["tourist"],
            programming_language="Python 3",
            verdict="WRONG_ANSWER",
            source_code=None,
            source_available=False,
        )

        self.mock_cf_client.fetch_all_submissions.return_value = [self.sub1, self.sub2]
        self.service = SyncService(codeforces_client=self.mock_cf_client)

    @patch("cf_sync.services.sync_service.GitHubClient")
    def test_successful_sync_flow_a(self, MockGitHubClient):
        mock_gh = MagicMock()
        MockGitHubClient.return_value = mock_gh
        mock_gh.verify_write_access.return_value = True
        mock_gh.fetch_synced_submission_ids.return_value = set()
        mock_gh.commit_files_bundle.return_value = (
            "commit_sha_abc123",
            "https://github.com/RishabhRaj120/Project-101/commit/commit_sha_abc123",
        )

        config = SyncConfig(
            handle="tourist",
            github_token="ghp_mock_token",
            repo_owner="RishabhRaj120",
            repo_name="Project-101",
            branch="prithvi",
            is_own_account=True,
            sync_filter=SyncFilter(verdict_mode=VerdictMode.ALL),
        )

        result = self.service.sync(config)

        self.assertEqual(result.total_fetched, 2)
        self.assertEqual(result.eligible_submissions, 2)
        self.assertEqual(result.successfully_synced, 2)
        self.assertEqual(result.commit_sha, "commit_sha_abc123")
        self.assertEqual(len(result.errors), 0)

        # Check commit files bundle was called
        mock_gh.commit_files_bundle.assert_called_once()
        call_args = mock_gh.commit_files_bundle.call_args[1]
        files = call_args["files_to_commit"]
        self.assertIn("codeforces/.cf_sync_index.json", files)

    @patch("cf_sync.services.sync_service.GitHubClient")
    def test_sync_idempotency_skip_already_synced(self, MockGitHubClient):
        mock_gh = MagicMock()
        MockGitHubClient.return_value = mock_gh
        mock_gh.verify_write_access.return_value = True
        # Mark sub1 (1001) as already synced
        mock_gh.fetch_synced_submission_ids.return_value = {1001}
        mock_gh.commit_files_bundle.return_value = ("sha_new", "https://github.com/...")

        config = SyncConfig(
            handle="tourist",
            github_token="ghp_mock_token",
            repo_owner="RishabhRaj120",
            repo_name="Project-101",
            branch="prithvi",
            sync_filter=SyncFilter(verdict_mode=VerdictMode.ALL, only_new=True),
        )

        result = self.service.sync(config)

        self.assertEqual(result.total_fetched, 2)
        self.assertEqual(result.already_synced, 1)
        self.assertEqual(result.eligible_submissions, 1) # only sub2
        self.assertEqual(result.items[0].submission_id, 1002)


if __name__ == "__main__":
    unittest.main()
