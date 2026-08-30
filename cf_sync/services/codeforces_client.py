"""
Codeforces API Client with rate-limiting, retries, pagination, handle validation,
and Flow A (own account) vs Flow B (public handle) handling.
"""
import hashlib
import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from cf_sync.core.models import Submission

logger = logging.getLogger(__name__)


class CodeforcesAPIError(Exception):
    """Generic exception for Codeforces API failures."""
    pass


class CodeforcesHandleNotFoundError(CodeforcesAPIError):
    """Raised when a Codeforces handle does not exist."""
    pass


class CodeforcesRateLimitError(CodeforcesAPIError):
    """Raised when Codeforces API rate limit is exceeded."""
    pass


class CodeforcesClient:
    """
    Client for interacting with the official Codeforces API.
    """
    BASE_URL = "https://codeforces.com/api"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        min_request_interval_sec: float = 0.5,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        timeout: int = 15,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.min_request_interval = min_request_interval_sec
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self._last_request_time = 0.0
        self._contest_names_cache: Dict[int, str] = {}

    def _rate_limit_wait(self) -> None:
        """Enforces a polite rate limit between outgoing API requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _generate_api_sig(self, method_name: str, params: Dict[str, Any]) -> str:
        """
        Generates apiSig parameter for authenticated Codeforces API requests.
        Format: 6-char random hex + SHA512(rand/methodName?k1=v1&k2=v2#secret)
        """
        rand_prefix = f"{random.randint(100000, 999999)}"
        # Sort params alphabetically by key, then value
        sorted_items = sorted((str(k), str(v)) for k, v in params.items() if k != "apiSig")
        param_str = "&".join(f"{k}={v}" for k, v in sorted_items)
        to_hash = f"{rand_prefix}/{method_name}?{param_str}#{self.api_secret}"
        sha512_hash = hashlib.sha512(to_hash.encode("utf-8")).hexdigest()
        return f"{rand_prefix}{sha512_hash}"

    def _make_request(self, method_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Executes an HTTP GET request to Codeforces API with exponential backoff.
        """
        params = dict(params or {})

        if self.api_key and self.api_secret:
            params["apiKey"] = self.api_key
            params["time"] = int(time.time())
            params["apiSig"] = self._generate_api_sig(method_name, params)

        query_str = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}/{method_name}?{query_str}" if query_str else f"{self.BASE_URL}/{method_name}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CF-GitHub-Sync/1.0 (+https://github.com/RishabhRaj120/Project-101)",
                "Accept": "application/json",
            }
        )

        for attempt in range(self.max_retries + 1):
            self._rate_limit_wait()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("status") == "OK":
                        return data.get("result")
                    else:
                        comment = data.get("comment", "Unknown error from Codeforces API")
                        if "not found" in comment.lower():
                            raise CodeforcesHandleNotFoundError(comment)
                        if "limit exceeded" in comment.lower():
                            raise CodeforcesRateLimitError(comment)
                        raise CodeforcesAPIError(f"Codeforces API error: {comment}")

            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="ignore")
                try:
                    err_json = json.loads(body)
                    comment = err_json.get("comment", str(e))
                except Exception:
                    comment = body or str(e)

                if e.code == 400 and ("not found" in comment.lower() or "handle" in comment.lower()):
                    raise CodeforcesHandleNotFoundError(f"Codeforces handle not found: {comment}")
                elif e.code in (429, 503):
                    if attempt == self.max_retries:
                        raise CodeforcesRateLimitError(f"Rate limit / service unavailable ({e.code}): {comment}")
                else:
                    if attempt == self.max_retries:
                        raise CodeforcesAPIError(f"HTTP {e.code} error: {comment}")

            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt == self.max_retries:
                    raise CodeforcesAPIError(f"Network connection failed: {str(e)}")

            # Exponential backoff
            sleep_time = self.backoff_factor * (2 ** attempt) + random.uniform(0.1, 0.5)
            logger.warning(f"Retrying Codeforces API request to {method_name} in {sleep_time:.2f}s...")
            time.sleep(sleep_time)

        raise CodeforcesAPIError(f"Failed to fetch {method_name} after {self.max_retries} retries.")

    def validate_handle(self, handle: str) -> Dict[str, Any]:
        """
        Validates whether a Codeforces handle exists and returns basic user info.
        """
        clean_handle = handle.strip()
        if not clean_handle:
            raise CodeforcesHandleNotFoundError("Handle cannot be empty")

        result = self._make_request("user.info", {"handles": clean_handle})
        if not result or not isinstance(result, list) or len(result) == 0:
            raise CodeforcesHandleNotFoundError(f"User '{clean_handle}' not found")

        return result[0]

    def load_contest_names(self, gym: bool = False) -> Dict[int, str]:
        """Loads and caches contest names for rich folder labelling."""
        if not self._contest_names_cache:
            try:
                contests = self._make_request("contest.list", {"gym": "true" if gym else "false"})
                if isinstance(contests, list):
                    for c in contests:
                        cid = c.get("id")
                        cname = c.get("name")
                        if cid and cname:
                            self._contest_names_cache[cid] = cname
            except Exception as e:
                logger.warning(f"Could not preload contest names: {e}")
        return self._contest_names_cache

    def get_contest_name(self, contest_id: Optional[int]) -> Optional[str]:
        if contest_id is None:
            return None
        return self._contest_names_cache.get(contest_id)

    def fetch_submissions(
        self,
        handle: str,
        from_index: int = 1,
        count: int = 100,
        is_own_account: bool = False,
    ) -> List[Submission]:
        """
        Fetches submissions for a handle with pagination.
        Handles Flow A (own account) vs Flow B (public account).
        """
        clean_handle = handle.strip()
        params = {
            "handle": clean_handle,
            "from": from_index,
            "count": count,
        }

        # Flow A: If own account with API credentials, includeSources can be requested if supported
        if is_own_account and self.api_key:
            params["includeSources"] = "true"

        raw_submissions = self._make_request("user.status", params)
        if not isinstance(raw_submissions, list):
            return []

        # Ensure contest cache is populated for first run
        if not self._contest_names_cache:
            self.load_contest_names()

        submissions: List[Submission] = []
        for raw in raw_submissions:
            cid = raw.get("contestId")
            contest_name = self.get_contest_name(cid)
            sub = Submission.from_dict(raw, contest_name=contest_name)
            
            # Flow differentiation
            if not is_own_account and not sub.source_code:
                sub.source_available = False
            
            submissions.append(sub)

        return submissions

    def fetch_all_submissions(
        self,
        handle: str,
        max_submissions: Optional[int] = None,
        batch_size: int = 100,
        is_own_account: bool = False,
    ) -> List[Submission]:
        """
        Paginates through all submissions for a user up to max_submissions.
        """
        all_subs: List[Submission] = []
        from_idx = 1

        while True:
            fetch_count = batch_size
            if max_submissions:
                remaining = max_submissions - len(all_subs)
                if remaining <= 0:
                    break
                fetch_count = min(batch_size, remaining)

            batch = self.fetch_submissions(
                handle,
                from_index=from_idx,
                count=fetch_count,
                is_own_account=is_own_account,
            )

            if not batch:
                break

            all_subs.extend(batch)

            if len(batch) < fetch_count:
                # Reached the end of submissions
                break

            from_idx += len(batch)

        return all_subs
