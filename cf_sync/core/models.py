"""
Domain models and dataclasses for Codeforces to GitHub sync.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class SubmissionSyncStatus(str, Enum):
    FETCHED = "FETCHED"
    FILTERED = "FILTERED"
    ALREADY_SYNCED = "ALREADY_SYNCED"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


class VerdictMode(str, Enum):
    ALL = "ALL"
    ACCEPTED_ONLY = "ACCEPTED_ONLY"
    REJECTED_ONLY = "REJECTED_ONLY"
    CUSTOM = "CUSTOM"


@dataclass
class Problem:
    contest_id: Optional[int] = None
    problemset_name: Optional[str] = None
    index: str = ""
    name: str = ""
    problem_type: str = "PROGRAMMING"
    points: Optional[float] = None
    rating: Optional[int] = None
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Problem":
        return cls(
            contest_id=data.get("contestId"),
            problemset_name=data.get("problemsetName"),
            index=str(data.get("index", "")).strip(),
            name=str(data.get("name", "")).strip(),
            problem_type=data.get("type", "PROGRAMMING"),
            points=data.get("points"),
            rating=data.get("rating"),
            tags=data.get("tags", []) or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contestId": self.contest_id,
            "problemsetName": self.problemset_name,
            "index": self.index,
            "name": self.name,
            "type": self.problem_type,
            "points": self.points,
            "rating": self.rating,
            "tags": self.tags,
        }


@dataclass
class Submission:
    id: int
    contest_id: Optional[int]
    creation_time_seconds: int
    relative_time_seconds: Optional[int]
    problem: Problem
    author_members: List[str]
    programming_language: str
    verdict: Optional[str]
    testset: str = "TESTS"
    pass_test_count: int = 0
    time_consumed_millis: int = 0
    memory_consumed_bytes: int = 0
    contest_name: Optional[str] = None
    source_code: Optional[str] = None
    source_available: bool = False
    status: SubmissionSyncStatus = SubmissionSyncStatus.FETCHED
    error_message: Optional[str] = None
    target_path: Optional[str] = None

    @property
    def created_at_utc(self) -> datetime:
        return datetime.fromtimestamp(self.creation_time_seconds, tz=timezone.utc)

    @property
    def is_accepted(self) -> bool:
        return self.verdict == "OK"

    @property
    def problem_url(self) -> str:
        if self.contest_id:
            if self.contest_id > 10000:
                # Gym contest
                return f"https://codeforces.com/gym/{self.contest_id}/problem/{self.problem.index}"
            return f"https://codeforces.com/contest/{self.contest_id}/problem/{self.problem.index}"
        elif self.problem.problemset_name:
            return f"https://codeforces.com/problemsets/{self.problem.problemset_name}/problem/{self.problem.index}"
        return "https://codeforces.com/problemset"

    @property
    def submission_url(self) -> str:
        if self.contest_id:
            if self.contest_id > 10000:
                return f"https://codeforces.com/gym/{self.contest_id}/submission/{self.id}"
            return f"https://codeforces.com/contest/{self.contest_id}/submission/{self.id}"
        return f"https://codeforces.com/submission/{self.id}"

    @classmethod
    def from_dict(cls, data: Dict[str, Any], contest_name: Optional[str] = None) -> "Submission":
        prob_data = data.get("problem", {})
        author_data = data.get("author", {})
        members = [m.get("handle") for m in author_data.get("members", []) if m.get("handle")]
        
        source = data.get("sourceCode") or data.get("source")
        source_available = bool(source)

        return cls(
            id=int(data["id"]),
            contest_id=data.get("contestId"),
            creation_time_seconds=int(data.get("creationTimeSeconds", 0)),
            relative_time_seconds=data.get("relativeTimeSeconds"),
            problem=Problem.from_dict(prob_data),
            author_members=members,
            programming_language=str(data.get("programmingLanguage", "Unknown")),
            verdict=data.get("verdict"),
            testset=data.get("testset", "TESTS"),
            pass_test_count=int(data.get("passedTestCount", data.get("pass_test_count", 0))),
            time_consumed_millis=int(data.get("timeConsumedMillis", 0)),
            memory_consumed_bytes=int(data.get("memoryConsumedBytes", 0)),
            contest_name=contest_name,
            source_code=source,
            source_available=source_available,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "contestId": self.contest_id,
            "contestName": self.contest_name,
            "creationTimeSeconds": self.creation_time_seconds,
            "createdAtUtc": self.created_at_utc.isoformat(),
            "problem": self.problem.to_dict(),
            "authorMembers": self.author_members,
            "programmingLanguage": self.programming_language,
            "verdict": self.verdict,
            "isAccepted": self.is_accepted,
            "passTestCount": self.pass_test_count,
            "timeConsumedMillis": self.time_consumed_millis,
            "memoryConsumedBytes": self.memory_consumed_bytes,
            "problemUrl": self.problem_url,
            "submissionUrl": self.submission_url,
            "sourceAvailable": self.source_available,
            "status": self.status.value,
            "errorMessage": self.error_message,
            "targetPath": self.target_path,
        }


@dataclass
class SyncFilter:
    verdict_mode: VerdictMode = VerdictMode.ALL
    custom_verdict: Optional[str] = None
    after_date: Optional[datetime] = None
    before_date: Optional[datetime] = None
    contest_id: Optional[int] = None
    problem_index: Optional[str] = None
    problem_tag: Optional[str] = None
    language: Optional[str] = None
    limit: Optional[int] = None
    only_new: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdictMode": self.verdict_mode.value,
            "customVerdict": self.custom_verdict,
            "afterDate": self.after_date.isoformat() if self.after_date else None,
            "beforeDate": self.before_date.isoformat() if self.before_date else None,
            "contestId": self.contest_id,
            "problemIndex": self.problem_index,
            "problemTag": self.problem_tag,
            "language": self.language,
            "limit": self.limit,
            "onlyNew": self.only_new,
        }


@dataclass
class GitHubRepo:
    owner: str
    name: str
    full_name: str
    default_branch: str = "main"
    is_private: bool = False
    permissions: Dict[str, bool] = field(default_factory=lambda: {"push": True, "pull": True, "admin": False})

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GitHubRepo":
        owner_data = data.get("owner", {})
        owner_login = owner_data.get("login") if isinstance(owner_data, dict) else str(owner_data)
        return cls(
            owner=owner_login,
            name=data.get("name", ""),
            full_name=data.get("full_name", f"{owner_login}/{data.get('name', '')}"),
            default_branch=data.get("default_branch", "main"),
            is_private=bool(data.get("private", False)),
            permissions=data.get("permissions", {"push": True, "pull": True}),
        )


@dataclass
class SyncConfig:
    handle: str
    github_token: str
    repo_owner: str
    repo_name: str
    branch: str = "main"
    destination_dir: str = "codeforces"
    commit_message: Optional[str] = None
    create_pr: bool = False
    pr_branch: Optional[str] = None
    is_own_account: bool = False
    cf_api_key: Optional[str] = None
    cf_api_secret: Optional[str] = None
    sync_filter: SyncFilter = field(default_factory=SyncFilter)


@dataclass
class SyncItemResult:
    submission_id: int
    contest_id: Optional[int]
    problem_index: str
    problem_name: str
    verdict: Optional[str]
    language: str
    status: SubmissionSyncStatus
    file_path: Optional[str] = None
    message: Optional[str] = None
    source_available: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "submissionId": self.submission_id,
            "contestId": self.contest_id,
            "problemIndex": self.problem_index,
            "problemName": self.problem_name,
            "verdict": self.verdict,
            "language": self.language,
            "status": self.status.value,
            "filePath": self.file_path,
            "message": self.message,
            "sourceAvailable": self.source_available,
        }


@dataclass
class SyncResult:
    total_fetched: int = 0
    eligible_submissions: int = 0
    already_synced: int = 0
    successfully_synced: int = 0
    failed: int = 0
    skipped: int = 0
    source_unavailable: int = 0
    commit_sha: Optional[str] = None
    commit_url: Optional[str] = None
    pr_url: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    items: List[SyncItemResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "totalFetched": self.total_fetched,
            "eligibleSubmissions": self.eligible_submissions,
            "alreadySynced": self.already_synced,
            "successfullySynced": self.successfully_synced,
            "failed": self.failed,
            "skipped": self.skipped,
            "sourceUnavailable": self.source_unavailable,
            "commitSha": self.commit_sha,
            "commitUrl": self.commit_url,
            "prUrl": self.pr_url,
            "errors": self.errors,
            "items": [item.to_dict() for item in self.items],
        }
