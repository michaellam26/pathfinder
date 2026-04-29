"""Tests for shared.ats_matcher (PRJ-002 / PR 1).

Covers normalization, synonym expansion, and coverage computation.
"""
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from shared.ats_matcher import (
    _stem,
    normalize,
    expand_synonyms,
    compute_coverage,
)


class TestStem(unittest.TestCase):
    """The plural-only stem rule. All inputs assumed already lowercased."""

    def test_short_token_unchanged(self):
        # len <= 3 → never stem (avoids "is" → "i", etc.)
        self.assertEqual(_stem("ai"), "ai")
        self.assertEqual(_stem("ml"), "ml")
        self.assertEqual(_stem("api"), "api")

    def test_simple_plural_drops_s(self):
        self.assertEqual(_stem("models"), "model")
        self.assertEqual(_stem("teams"), "team")
        self.assertEqual(_stem("services"), "service")

    def test_ies_becomes_y(self):
        self.assertEqual(_stem("libraries"), "library")
        self.assertEqual(_stem("industries"), "industry")
        self.assertEqual(_stem("companies"), "company")

    def test_ses_xes_ches_shes_strip_es(self):
        self.assertEqual(_stem("classes"), "class")
        self.assertEqual(_stem("databases"), "database")
        self.assertEqual(_stem("boxes"), "box")
        self.assertEqual(_stem("churches"), "church")
        self.assertEqual(_stem("dishes"), "dish")

    def test_ss_preserved(self):
        self.assertEqual(_stem("chess"), "chess")
        self.assertEqual(_stem("class"), "class")

    def test_non_plural_preserved(self):
        self.assertEqual(_stem("kubernetes"), "kubernete")  # accepted lossy: 's' looks plural
        # ↑ This is a known limitation of the rule-based stem — synonyms cover
        #   the kubernetes ↔ k8s case at the matcher level, so this doesn't
        #   actually break end-to-end matching.
        self.assertEqual(_stem("python"), "python")
        self.assertEqual(_stem("gemini"), "gemini")

    def test_non_alpha_terminal_unchanged(self):
        # If last char isn't alphabetic, leave alone (catches K8s after lowercase
        # would normalize to "k8s" which ends in 's' — but caller stems the full
        # token "k8s" and we want to preserve numbers/symbols-adjacent endings).
        self.assertEqual(_stem("c++"), "c++")
        self.assertEqual(_stem("gpt-4"), "gpt-4")


class TestNormalize(unittest.TestCase):
    def test_empty_inputs(self):
        self.assertEqual(normalize(""), "")
        self.assertEqual(normalize(None), "")
        self.assertEqual(normalize("   "), "")

    def test_lowercases(self):
        self.assertEqual(normalize("PyTorch"), "pytorch")
        # "kubernetes" → "kubernete" because the matcher treats trailing -s as
        # plural; synonyms (k8s ↔ kubernetes) cover the round-trip in practice.
        self.assertEqual(normalize("KUBERNETES"), "kubernete")

    def test_special_tokens_preserved(self):
        self.assertEqual(normalize("C++"), "c++")
        self.assertEqual(normalize("C#"), "c#")
        self.assertEqual(normalize("K8s"), "k8s")
        self.assertEqual(normalize("GPT-4"), "gpt-4")
        self.assertEqual(normalize("Node.js"), "node.js")

    def test_strips_surrounding_punctuation(self):
        # Trailing period (sentence end) should not be part of token.
        self.assertEqual(normalize("Test."), "test")
        # Comma between tokens
        self.assertEqual(normalize("Python, Java"), "python java")

    def test_multi_word_phrase(self):
        self.assertEqual(normalize("Machine Learning"), "machine learning")
        self.assertEqual(normalize("Large language models"), "large language model")

    def test_mixed_realistic_sentence(self):
        text = "Built LLM-powered services using PyTorch and K8s on AWS."
        out = normalize(text)
        # Each token normalized + space-joined
        self.assertIn("llm-powered", out)
        self.assertIn("pytorch", out)
        self.assertIn("k8s", out)
        self.assertIn("aws", out)


class TestExpandSynonyms(unittest.TestCase):
    def test_keyword_in_group_returns_full_group(self):
        # "GenAI" is in the genai/generative ai group
        result = expand_synonyms("GenAI")
        self.assertIn("genai", result)
        self.assertIn("generative ai", result)
        self.assertIn("gen ai", result)

    def test_keyword_not_in_any_group_returns_self(self):
        result = expand_synonyms("Snowflake")
        self.assertEqual(result, {"snowflake"})

    def test_case_insensitive_lookup(self):
        upper = expand_synonyms("PYTORCH")
        lower = expand_synonyms("pytorch")
        self.assertEqual(upper, lower)
        self.assertIn("torch", upper)

    def test_empty_input_empty_set(self):
        self.assertEqual(expand_synonyms(""), set())
        self.assertEqual(expand_synonyms(None), set())

    def test_plural_in_input_collapses_via_stem(self):
        # "LLMs" → stems to "llm" → finds the LLM group
        result = expand_synonyms("LLMs")
        self.assertIn("llm", result)
        self.assertIn("large language model", result)

    def test_multi_word_synonym(self):
        # "google cloud" should expand back to gcp / google cloud platform
        result = expand_synonyms("google cloud")
        self.assertIn("gcp", result)
        self.assertIn("google cloud platform", result)


class TestComputeCoverageBasic(unittest.TestCase):
    def test_none_keywords_returns_none_percent(self):
        out = compute_coverage(None, "any resume text")
        self.assertIsNone(out["percent"])
        self.assertEqual(out["keyword_count"], 0)

    def test_empty_keywords_returns_none_percent(self):
        out = compute_coverage([], "any resume text")
        self.assertIsNone(out["percent"])
        self.assertEqual(out["keyword_count"], 0)

    def test_blank_only_keywords_returns_none_percent(self):
        out = compute_coverage(["", "  ", None], "resume")
        self.assertIsNone(out["percent"])
        self.assertEqual(out["keyword_count"], 0)

    def test_all_matched_100_percent(self):
        keywords = ["PyTorch", "Kubernetes", "AWS"]
        resume = "Engineered PyTorch models on Kubernetes and AWS."
        out = compute_coverage(keywords, resume)
        self.assertEqual(out["percent"], 100.0)
        self.assertEqual(set(out["matched"]), {"PyTorch", "Kubernetes", "AWS"})
        self.assertEqual(out["missing"], [])
        self.assertEqual(out["keyword_count"], 3)

    def test_all_missing_zero_percent(self):
        keywords = ["Rust", "Erlang", "Haskell"]
        resume = "Built JavaScript apps."
        out = compute_coverage(keywords, resume)
        self.assertEqual(out["percent"], 0.0)
        self.assertEqual(out["matched"], [])
        self.assertEqual(set(out["missing"]), {"Rust", "Erlang", "Haskell"})

    def test_mixed_partial_coverage(self):
        keywords = ["Python", "PyTorch", "Rust"]
        resume = "Used Python and PyTorch daily."
        out = compute_coverage(keywords, resume)
        self.assertEqual(out["percent"], 66.7)  # 2/3 = 66.67 → rounded
        self.assertEqual(set(out["matched"]), {"Python", "PyTorch"})
        self.assertEqual(out["missing"], ["Rust"])


class TestComputeCoverageNormalization(unittest.TestCase):
    def test_case_insensitive(self):
        out = compute_coverage(["PYTHON"], "i love python.")
        self.assertEqual(out["percent"], 100.0)

    def test_plural_keyword_matches_singular_in_resume(self):
        out = compute_coverage(["models"], "shipped one model to production")
        self.assertEqual(out["percent"], 100.0)

    def test_singular_keyword_matches_plural_in_resume(self):
        out = compute_coverage(["model"], "trained dozens of models")
        self.assertEqual(out["percent"], 100.0)

    def test_special_chars_in_keyword(self):
        out = compute_coverage(["C++", "K8s", "GPT-4"],
                               "Built C++ services on K8s using GPT-4 prompts.")
        self.assertEqual(out["percent"], 100.0)

    def test_multi_word_keyword(self):
        out = compute_coverage(["machine learning"],
                               "Senior Machine Learning Engineer at Acme.")
        self.assertEqual(out["percent"], 100.0)

    def test_token_boundary_no_substring_false_positive(self):
        # "java" should NOT match inside "javascript" because we tokenize first.
        out = compute_coverage(["java"], "Built apps in JavaScript.")
        self.assertEqual(out["percent"], 0.0)
        self.assertEqual(out["missing"], ["java"])

    def test_punctuation_around_keyword(self):
        out = compute_coverage(["Python"], "Stack: Python, Go, Rust.")
        self.assertEqual(out["percent"], 100.0)


class TestComputeCoverageSynonyms(unittest.TestCase):
    def test_pytorch_keyword_matches_torch_in_resume(self):
        out = compute_coverage(["PyTorch"], "Used Torch extensively.")
        self.assertEqual(out["percent"], 100.0)

    def test_llm_keyword_matches_large_language_model_in_resume(self):
        out = compute_coverage(["LLM"], "Tuned large language models.")
        self.assertEqual(out["percent"], 100.0)

    def test_genai_keyword_matches_generative_ai_in_resume(self):
        out = compute_coverage(["GenAI"], "Specialized in Generative AI products.")
        self.assertEqual(out["percent"], 100.0)

    def test_k8s_keyword_matches_kubernetes_in_resume(self):
        out = compute_coverage(["K8s"], "Operated Kubernetes clusters.")
        self.assertEqual(out["percent"], 100.0)

    def test_gcp_keyword_matches_google_cloud_in_resume(self):
        out = compute_coverage(["GCP"], "Deployed on Google Cloud.")
        self.assertEqual(out["percent"], 100.0)


class TestComputeCoverageDedup(unittest.TestCase):
    def test_duplicate_keywords_deduplicated(self):
        # "PyTorch" and "pytorch" collapse to one entry.
        out = compute_coverage(
            ["PyTorch", "pytorch", "PYTORCH"],
            "Used PyTorch heavily.",
        )
        self.assertEqual(out["keyword_count"], 1)
        self.assertEqual(out["matched"], ["PyTorch"])  # first occurrence wins

    def test_blank_keywords_skipped_not_counted(self):
        out = compute_coverage(["PyTorch", "", "  ", None, "Rust"],
                               "Used PyTorch.")
        self.assertEqual(out["keyword_count"], 2)  # PyTorch + Rust only

    def test_whitespace_in_keyword_stripped(self):
        out = compute_coverage(["  PyTorch  "], "Used PyTorch.")
        self.assertEqual(out["matched"], ["PyTorch"])  # trimmed display


class TestComputeCoverageEmptyResume(unittest.TestCase):
    def test_empty_resume_all_missing(self):
        out = compute_coverage(["Python", "PyTorch"], "")
        self.assertEqual(out["percent"], 0.0)
        self.assertEqual(set(out["missing"]), {"Python", "PyTorch"})

    def test_none_resume_treated_as_empty(self):
        out = compute_coverage(["Python"], None)
        self.assertEqual(out["percent"], 0.0)


class TestComputeCoverageReturnShape(unittest.TestCase):
    """Lock the return-dict shape so downstream callers (Excel writer,
    optimizer) can rely on it."""

    def test_all_keys_present(self):
        out = compute_coverage(["x"], "y")
        self.assertEqual(set(out.keys()), {"percent", "matched", "missing", "keyword_count"})

    def test_percent_rounded_to_one_decimal(self):
        # 1 of 3 = 33.333... → 33.3
        out = compute_coverage(["Python", "Rust", "Erlang"], "I write Python.")
        self.assertEqual(out["percent"], 33.3)

    def test_matched_missing_are_lists_not_sets(self):
        out = compute_coverage(["Python"], "Python rules.")
        self.assertIsInstance(out["matched"], list)
        self.assertIsInstance(out["missing"], list)


class TestATSCoverageResultPydanticRoundtrip(unittest.TestCase):
    """Verify the matcher output round-trips through the schemas.ATSCoverageResult Pydantic model."""

    def test_roundtrip(self):
        from shared.schemas import ATSCoverageResult
        out = compute_coverage(["Python", "Rust"], "Wrote Python.")
        # Validate it parses cleanly into the schema.
        validated = ATSCoverageResult(**out)
        self.assertEqual(validated.percent, 50.0)
        self.assertEqual(validated.matched, ["Python"])
        self.assertEqual(validated.missing, ["Rust"])
        self.assertEqual(validated.keyword_count, 2)

    def test_none_percent_roundtrip(self):
        from shared.schemas import ATSCoverageResult
        out = compute_coverage([], "anything")
        validated = ATSCoverageResult(**out)
        self.assertIsNone(validated.percent)
        self.assertEqual(validated.keyword_count, 0)


class TestJobDetailsSchemaHasATSKeywords(unittest.TestCase):
    """REQ-100: JobDetails must accept and round-trip ats_keywords."""

    def test_default_empty_list_when_omitted(self):
        # Old cached JDs without the field still validate.
        from agents.job_agent import JobDetails
        jd = JobDetails(
            job_title="x", company="y", location="z", salary_range="",
            requirements=["a"], additional_qualifications=[],
            key_responsibilities=["b"], is_ai_tpm=True,
        )
        self.assertEqual(jd.ats_keywords, [])

    def test_field_round_trips(self):
        from agents.job_agent import JobDetails
        jd = JobDetails(
            job_title="x", company="y", location="z", salary_range="",
            requirements=["a"], additional_qualifications=[],
            key_responsibilities=["b"], is_ai_tpm=True,
            ats_keywords=["PyTorch", "Kubernetes", "LLM"],
        )
        self.assertEqual(jd.ats_keywords, ["PyTorch", "Kubernetes", "LLM"])

    def test_json_roundtrip(self):
        from agents.job_agent import JobDetails
        import json
        payload = {
            "job_title": "AI TPM", "company": "Acme", "location": "Remote",
            "salary_range": "", "requirements": ["a"],
            "additional_qualifications": [], "key_responsibilities": ["b"],
            "is_ai_tpm": True, "ats_keywords": ["PyTorch", "RAG"],
        }
        jd = JobDetails(**payload)
        round = json.loads(jd.model_dump_json())
        self.assertEqual(round["ats_keywords"], ["PyTorch", "RAG"])


if __name__ == "__main__":
    unittest.main()
