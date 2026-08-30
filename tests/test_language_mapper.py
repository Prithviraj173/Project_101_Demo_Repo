import unittest
from cf_sync.core.language_mapper import LanguageMapper, LanguageDefinition, default_language_mapper


class TestLanguageMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = LanguageMapper()

    def test_known_cpp_variants(self):
        self.assertEqual(self.mapper.get_extension("GNU C++17"), "cpp")
        self.assertEqual(self.mapper.get_extension("GNU C++20"), "cpp")
        self.assertEqual(self.mapper.get_extension("Clang++20 Diagnostics"), "cpp")
        self.assertEqual(self.mapper.get_comment_prefix("GNU C++17"), "//")

    def test_python_and_pypy(self):
        self.assertEqual(self.mapper.get_extension("Python 3"), "py")
        self.assertEqual(self.mapper.get_extension("PyPy 3-64"), "py")
        self.assertEqual(self.mapper.get_comment_prefix("Python 3"), "#")

    def test_java_kotlin_rust_go(self):
        self.assertEqual(self.mapper.get_extension("Java 21"), "java")
        self.assertEqual(self.mapper.get_extension("Kotlin 1.9"), "kt")
        self.assertEqual(self.mapper.get_extension("Rust 2021"), "rs")
        self.assertEqual(self.mapper.get_extension("Go"), "go")
        self.assertEqual(self.mapper.get_extension("C# 10"), "cs")
        self.assertEqual(self.mapper.get_extension("TypeScript 4.8"), "ts")
        self.assertEqual(self.mapper.get_extension("JavaScript (Node.js)"), "js")

    def test_haskell_and_ocaml_comment_prefixes(self):
        self.assertEqual(self.mapper.get_extension("GHC Haskell"), "hs")
        self.assertEqual(self.mapper.get_comment_prefix("GHC Haskell"), "--")
        self.assertEqual(self.mapper.get_extension("OCaml"), "ml")
        self.assertEqual(self.mapper.get_comment_prefix("OCaml"), "(*")

    def test_custom_language_registration(self):
        self.mapper.register_language("Brainf**k", "bf", ";;", "Brainfuck")
        self.assertEqual(self.mapper.get_extension("Brainf**k"), "bf")
        self.assertEqual(self.mapper.get_comment_prefix("Brainf**k"), ";;")

    def test_fallback_unmapped_language(self):
        ext, comment = self.mapper.resolve("UnknownLanguageX123")
        self.assertEqual(ext, "txt")
        self.assertEqual(comment, "//")


if __name__ == "__main__":
    unittest.main()
