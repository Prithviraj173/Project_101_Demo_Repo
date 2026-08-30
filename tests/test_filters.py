import unittest
from datetime import datetime, timezone
from cf_sync.core.filters import (
    AlreadySyncedFilter,
    ContestFilter,
    DateRangeFilter,
    FilterPipeline,
    LanguageFilter,
    ProblemFilter,
    VerdictFilter,
)
from cf_sync.core.models import Problem, Submission, SyncFilter, VerdictMode


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.sub_ok = Submission(
            id=101,
            contest_id=1000,
            creation_time_seconds=int(datetime(2024, 1, 15, tzinfo=timezone.utc).timestamp()),
            relative_time_seconds=None,
            problem=Problem(contest_id=1000, index="A", name="Prob A", tags=["dp", "greedy"]),
            author_members=["user1"],
            programming_language="GNU C++20",
            verdict="OK",
        )
        self.sub_wa = Submission(
            id=102,
            contest_id=1000,
            creation_time_seconds=int(datetime(2024, 1, 10, tzinfo=timezone.utc).timestamp()),
            relative_time_seconds=None,
            problem=Problem(contest_id=1000, index="B", name="Prob B", tags=["math"]),
            author_members=["user1"],
            programming_language="Python 3",
            verdict="WRONG_ANSWER",
        )
        self.sub_tle = Submission(
            id=103,
            contest_id=2000,
            creation_time_seconds=int(datetime(2024, 2, 1, tzinfo=timezone.utc).timestamp()),
            relative_time_seconds=None,
            problem=Problem(contest_id=2000, index="A", name="Prob 2A", tags=["graphs"]),
            author_members=["user1"],
            programming_language="Java 21",
            verdict="TIME_LIMIT_EXCEEDED",
        )

    def test_verdict_filters(self):
        all_subs = [self.sub_ok, self.sub_wa, self.sub_tle]

        f_accepted = VerdictFilter(VerdictMode.ACCEPTED_ONLY)
        self.assertEqual(len([s for s in all_subs if f_accepted.matches(s)]), 1)

        f_rejected = VerdictFilter(VerdictMode.REJECTED_ONLY)
        self.assertEqual(len([s for s in all_subs if f_rejected.matches(s)]), 2)

        f_custom = VerdictFilter(VerdictMode.CUSTOM, custom_verdict="TIME_LIMIT_EXCEEDED")
        self.assertEqual(len([s for s in all_subs if f_custom.matches(s)]), 1)

    def test_date_range_filter(self):
        all_subs = [self.sub_ok, self.sub_wa, self.sub_tle]
        f_date = DateRangeFilter(
            after_date=datetime(2024, 1, 12, tzinfo=timezone.utc),
            before_date=datetime(2024, 1, 20, tzinfo=timezone.utc),
        )
        res = [s for s in all_subs if f_date.matches(s)]
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].id, 101)

    def test_contest_and_problem_filters(self):
        all_subs = [self.sub_ok, self.sub_wa, self.sub_tle]

        f_contest = ContestFilter(contest_id=1000)
        self.assertEqual(len([s for s in all_subs if f_contest.matches(s)]), 2)

        f_prob = ProblemFilter(problem_index="A", problem_tag="dp")
        self.assertEqual(len([s for s in all_subs if f_prob.matches(s)]), 1)

    def test_already_synced_filter(self):
        all_subs = [self.sub_ok, self.sub_wa, self.sub_tle]
        f_synced = AlreadySyncedFilter(synced_ids={101, 103}, only_new=True)
        res = [s for s in all_subs if f_synced.matches(s)]
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].id, 102)

    def test_pipeline_factory_with_limit(self):
        all_subs = [self.sub_ok, self.sub_wa, self.sub_tle]
        sf = SyncFilter(verdict_mode=VerdictMode.ALL, limit=2)
        pipeline = FilterPipeline.from_sync_filter(sf)
        res = pipeline.apply(all_subs)
        self.assertEqual(len(res), 2)


if __name__ == "__main__":
    unittest.main()
