import unittest
from cf_sync.core.models import Problem, Submission
from cf_sync.core.path_builder import PathBuilder, sanitize_path_segment


class TestPathBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = PathBuilder(base_dir="codeforces")

    def test_standard_path_generation(self):
        sub = Submission(
            id=123456,
            contest_id=2048,
            contest_name="Educational Codeforces Round 170",
            creation_time_seconds=1700000000,
            relative_time_seconds=300,
            problem=Problem(contest_id=2048, index="A", name="Two Screens", points=500, rating=800),
            author_members=["tourist"],
            programming_language="GNU C++20",
            verdict="OK",
        )
        paths = self.builder.build_paths(sub)
        self.assertEqual(
            paths["solution_path"],
            "codeforces/2048-Educational-Codeforces-Round-170/A-Two-Screens/solution.cpp"
        )
        self.assertEqual(
            paths["metadata_path"],
            "codeforces/2048-Educational-Codeforces-Round-170/A-Two-Screens/metadata.json"
        )

    def test_path_traversal_prevention(self):
        # Malicious names attempting directory traversal
        sub = Submission(
            id=999,
            contest_id=100,
            contest_name="../../etc/passwd",
            creation_time_seconds=1700000000,
            relative_time_seconds=None,
            problem=Problem(contest_id=100, index="..", name="..\\..\\Windows\\System32"),
            author_members=["hacker"],
            programming_language="Python 3",
            verdict="OK",
        )
        paths = self.builder.build_paths(sub)
        # Verify no ../ or absolute references appear
        self.assertNotIn("..", paths["solution_path"].split("/"))
        self.assertTrue(paths["solution_path"].startswith("codeforces/"))

    def test_forbidden_character_sanitization(self):
        dirty_name = 'Problem: "A" <Special> | Quest? * [Hard]'
        clean = sanitize_path_segment(dirty_name)
        self.assertEqual(clean, "Problem-A-Special-Quest-Hard")

    def test_windows_reserved_device_names(self):
        self.assertEqual(sanitize_path_segment("CON"), "_CON")
        self.assertEqual(sanitize_path_segment("prn"), "_prn")
        self.assertEqual(sanitize_path_segment("aux"), "_aux")
        self.assertEqual(sanitize_path_segment("NUL.txt"), "_NUL.txt")
        self.assertEqual(sanitize_path_segment("COM1"), "_COM1")

    def test_gym_and_problemset_handling(self):
        sub_no_contest = Submission(
            id=555,
            contest_id=None,
            contest_name=None,
            creation_time_seconds=1700000000,
            relative_time_seconds=None,
            problem=Problem(index="100A", name="Ancient Berland"),
            author_members=["user1"],
            programming_language="Rust 2021",
            verdict="OK",
        )
        paths = self.builder.build_paths(sub_no_contest)
        self.assertEqual(paths["solution_path"], "codeforces/problemset/100A-Ancient-Berland/solution.rs")


if __name__ == "__main__":
    unittest.main()
