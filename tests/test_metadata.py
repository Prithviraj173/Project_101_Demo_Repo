import json
import unittest
from datetime import datetime, timezone
from cf_sync.core.metadata import MetadataGenerator
from cf_sync.core.models import Problem, Submission


class TestMetadata(unittest.TestCase):
    def setUp(self):
        self.generator = MetadataGenerator()
        self.sub = Submission(
            id=987654,
            contest_id=1900,
            contest_name="Codeforces Round 950",
            creation_time_seconds=int(datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()),
            relative_time_seconds=3600,
            problem=Problem(
                contest_id=1900,
                index="C",
                name="Sofia and the Lost Operations",
                rating=1200,
                tags=["constructive algorithms", "data structures"],
                points=1500,
            ),
            author_members=["tourist"],
            programming_language="GNU C++20",
            verdict="OK",
            pass_test_count=45,
            time_consumed_millis=180,
            memory_consumed_bytes=2097152,
            source_code="#include <iostream>\nint main(){ std::cout << 42; }",
            source_available=True,
        )

    def test_metadata_json_fields(self):
        meta_json = self.generator.generate_metadata_json(self.sub, handle="tourist")
        data = json.loads(meta_json)

        self.assertEqual(data["submissionId"], 987654)
        self.assertEqual(data["handle"], "tourist")
        self.assertEqual(data["contestId"], 1900)
        self.assertEqual(data["problem"]["index"], "C")
        self.assertEqual(data["problem"]["rating"], 1200)
        self.assertEqual(data["passedTestCount"], 45)
        self.assertEqual(data["timeConsumedMillis"], 180)
        self.assertTrue(data["sourceCodeAvailable"])
        self.assertEqual(data["problemUrl"], "https://codeforces.com/contest/1900/problem/C")

    def test_solution_file_content_with_source(self):
        content = self.generator.format_solution_file_content(self.sub, handle="tourist")
        self.assertIn("Problem: C. Sofia and the Lost Operations", content)
        self.assertIn("Handle: tourist", content)
        self.assertIn("Verdict: OK", content)
        self.assertIn("#include <iostream>", content)

    def test_generate_repository_index_markdown(self):
        md = self.generator.generate_repository_index_markdown([self.sub], handle="tourist")
        self.assertIn("# Codeforces Solutions Repository — @tourist", md)
        self.assertIn("Solutions by Rating / Difficulty", md)
        self.assertIn("Solutions by Topic / Tags", md)
        self.assertIn("1200", md)
        self.assertIn("constructive algorithms", md)


if __name__ == "__main__":
    unittest.main()
