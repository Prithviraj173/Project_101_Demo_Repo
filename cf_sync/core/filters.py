"""
Reusable, composable filtering pipeline for Codeforces submissions.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Callable, Iterable, List, Optional, Set
from cf_sync.core.models import Submission, SyncFilter, VerdictMode


class BaseFilter(ABC):
    """Abstract base class for submission filter predicates."""

    @abstractmethod
    def matches(self, submission: Submission) -> bool:
        """Returns True if the submission passes this filter, False otherwise."""
        pass


class VerdictFilter(BaseFilter):
    def __init__(self, mode: VerdictMode = VerdictMode.ALL, custom_verdict: Optional[str] = None):
        self.mode = mode
        self.custom_verdict = custom_verdict.strip().upper() if custom_verdict else None

    def matches(self, submission: Submission) -> bool:
        if self.mode == VerdictMode.ALL:
            return True
        elif self.mode == VerdictMode.ACCEPTED_ONLY:
            return submission.is_accepted
        elif self.mode == VerdictMode.REJECTED_ONLY:
            return not submission.is_accepted
        elif self.mode == VerdictMode.CUSTOM and self.custom_verdict:
            return (submission.verdict or "").upper() == self.custom_verdict
        return True


class DateRangeFilter(BaseFilter):
    def __init__(self, after_date: Optional[datetime] = None, before_date: Optional[datetime] = None):
        # Ensure UTC timezone awareness for comparison
        self.after_date = self._ensure_utc(after_date) if after_date else None
        self.before_date = self._ensure_utc(before_date) if before_date else None

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def matches(self, submission: Submission) -> bool:
        sub_time = submission.created_at_utc
        if self.after_date and sub_time < self.after_date:
            return False
        if self.before_date and sub_time > self.before_date:
            return False
        return True


class ContestFilter(BaseFilter):
    def __init__(self, contest_id: Optional[int] = None):
        self.contest_id = contest_id

    def matches(self, submission: Submission) -> bool:
        if self.contest_id is None:
            return True
        return submission.contest_id == self.contest_id


class ProblemFilter(BaseFilter):
    def __init__(self, problem_index: Optional[str] = None, problem_tag: Optional[str] = None):
        self.problem_index = problem_index.strip().upper() if problem_index else None
        self.problem_tag = problem_tag.strip().lower() if problem_tag else None

    def matches(self, submission: Submission) -> bool:
        if self.problem_index:
            if (submission.problem.index or "").upper() != self.problem_index:
                return False
        if self.problem_tag:
            tags = [t.lower() for t in submission.problem.tags]
            if self.problem_tag not in tags:
                return False
        return True


class LanguageFilter(BaseFilter):
    def __init__(self, language_query: Optional[str] = None):
        self.query = language_query.strip().lower() if language_query else None

    def matches(self, submission: Submission) -> bool:
        if not self.query:
            return True
        return self.query in submission.programming_language.lower()


class AlreadySyncedFilter(BaseFilter):
    def __init__(self, synced_ids: Set[int], only_new: bool = True):
        self.synced_ids = synced_ids
        self.only_new = only_new

    def matches(self, submission: Submission) -> bool:
        if not self.only_new:
            return True
        return submission.id not in self.synced_ids


class FilterPipeline:
    """
    Orchestrates a sequence of filters on Codeforces submissions.
    """

    def __init__(self, filters: Optional[List[BaseFilter]] = None, limit: Optional[int] = None):
        self.filters: List[BaseFilter] = filters or []
        self.limit = limit

    def add_filter(self, filter_obj: BaseFilter) -> "FilterPipeline":
        self.filters.append(filter_obj)
        return self

    def apply(self, submissions: Iterable[Submission]) -> List[Submission]:
        result = []
        for sub in submissions:
            if all(f.matches(sub) for f in self.filters):
                result.append(sub)
                if self.limit and len(result) >= self.limit:
                    break
        return result

    @classmethod
    def from_sync_filter(
        cls,
        sync_filter: SyncFilter,
        synced_ids: Optional[Set[int]] = None
    ) -> "FilterPipeline":
        """Factory method to construct a FilterPipeline from a SyncFilter dataclass."""
        filters: List[BaseFilter] = []

        # 1. Verdict filter
        if sync_filter.verdict_mode != VerdictMode.ALL or sync_filter.custom_verdict:
            filters.append(VerdictFilter(sync_filter.verdict_mode, sync_filter.custom_verdict))

        # 2. Date range filter
        if sync_filter.after_date or sync_filter.before_date:
            filters.append(DateRangeFilter(sync_filter.after_date, sync_filter.before_date))

        # 3. Contest filter
        if sync_filter.contest_id is not None:
            filters.append(ContestFilter(sync_filter.contest_id))

        # 4. Problem index & tag filter
        if sync_filter.problem_index or sync_filter.problem_tag:
            filters.append(ProblemFilter(sync_filter.problem_index, sync_filter.problem_tag))

        # 5. Language filter
        if sync_filter.language:
            filters.append(LanguageFilter(sync_filter.language))

        # 6. Already synced filter
        if sync_filter.only_new and synced_ids:
            filters.append(AlreadySyncedFilter(synced_ids, only_new=True))

        return cls(filters=filters, limit=sync_filter.limit)
