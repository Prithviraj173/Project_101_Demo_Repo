import json
import unittest
from unittest.mock import MagicMock, patch
from cf_sync.services.codeforces_client import (
    CodeforcesAPIError,
    CodeforcesClient,
    CodeforcesHandleNotFoundError,
    CodeforcesRateLimitError,
)


class TestCodeforcesClient(unittest.TestCase):
    def setUp(self):
        self.client = CodeforcesClient(min_request_interval_sec=0)
        # Pre-seed cache so contest.list is not called unexpectedly in test mocks
        self.client._contest_names_cache = {1900: "Round 950"}

    @patch("urllib.request.urlopen")
    def test_validate_handle_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "OK",
            "result": [{"handle": "tourist", "rating": 3800, "rank": "legendary grandmaster"}]
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        info = self.client.validate_handle("tourist")
        self.assertEqual(info["handle"], "tourist")
        self.assertEqual(info["rating"], 3800)

    @patch("urllib.request.urlopen")
    def test_validate_handle_not_found(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "FAILED",
            "comment": "handles: User with handle not_existing_user not found"
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with self.assertRaises(CodeforcesHandleNotFoundError):
            self.client.validate_handle("not_existing_user")

    @patch("urllib.request.urlopen")
    def test_fetch_submissions_flow_a_and_b(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "OK",
            "result": [
                {
                    "id": 111,
                    "contestId": 1900,
                    "creationTimeSeconds": 1700000000,
                    "problem": {"index": "A", "name": "Problem A"},
                    "author": {"members": [{"handle": "tourist"}]},
                    "programmingLanguage": "GNU C++20",
                    "verdict": "OK",
                    "sourceCode": "#include <iostream>",
                },
                {
                    "id": 112,
                    "contestId": 1900,
                    "creationTimeSeconds": 1700000100,
                    "problem": {"index": "B", "name": "Problem B"},
                    "author": {"members": [{"handle": "other_user"}]},
                    "programmingLanguage": "Python 3",
                    "verdict": "OK",
                }
            ]
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        # Flow A (own account)
        subs_own = self.client.fetch_submissions("tourist", is_own_account=True)
        self.assertEqual(len(subs_own), 2)
        self.assertTrue(subs_own[0].source_available)

        # Flow B (public handle without source)
        subs_public = self.client.fetch_submissions("other_user", is_own_account=False)
        self.assertEqual(len(subs_public), 2)
        self.assertFalse(subs_public[1].source_available)

    @patch("urllib.request.urlopen")
    def test_pagination_fetch_all(self, mock_urlopen):
        batch1 = json.dumps({
            "status": "OK",
            "result": [{"id": i, "creationTimeSeconds": 17000, "problem": {"index": "A", "name": "P"}, "programmingLanguage": "C++"} for i in range(1, 11)]
        }).encode("utf-8")
        batch2 = json.dumps({
            "status": "OK",
            "result": [{"id": 11, "creationTimeSeconds": 17000, "problem": {"index": "B", "name": "P2"}, "programmingLanguage": "Python"}]
        }).encode("utf-8")

        mock_resp1 = MagicMock()
        mock_resp1.read.return_value = batch1
        mock_resp1.__enter__.return_value = mock_resp1

        mock_resp2 = MagicMock()
        mock_resp2.read.return_value = batch2
        mock_resp2.__enter__.return_value = mock_resp2

        mock_urlopen.side_effect = [mock_resp1, mock_resp2]

        subs = self.client.fetch_all_submissions("tourist", batch_size=10)
        self.assertEqual(len(subs), 11)


if __name__ == "__main__":
    unittest.main()
