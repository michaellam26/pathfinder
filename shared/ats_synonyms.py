"""Hand-curated synonym groups for ATS keyword matching.

Each group is a list of strings considered equivalent by the ATS matcher.
Membership is symmetric — matching ANY term in the group counts as
matching the keyword the user supplied.

Keep this list small and high-confidence. Bias toward common AI/ML and
TPM-relevant terminology. Plural forms are NOT needed here — the matcher
applies its own light plural stem before lookup.
"""

SYNONYM_GROUPS: list[list[str]] = [
    # ── AI / ML technology ───────────────────────────────────────────────
    ["genai", "generative ai", "gen ai"],
    ["llm", "large language model"],
    ["ml", "machine learning"],
    ["ai", "artificial intelligence"],
    ["nlp", "natural language processing"],
    ["cv", "computer vision"],
    ["rl", "reinforcement learning"],
    ["mlops", "ml ops", "ml operation"],
    ["rag", "retrieval augmented generation"],
    # ── Frameworks / runtimes ────────────────────────────────────────────
    ["pytorch", "torch"],
    ["tensorflow", "tf"],
    # ── Cloud ────────────────────────────────────────────────────────────
    ["k8s", "kubernetes"],
    ["gcp", "google cloud", "google cloud platform"],
    ["aws", "amazon web services"],
    ["azure", "microsoft azure"],
    # ── Languages ────────────────────────────────────────────────────────
    ["js", "javascript"],
    ["ts", "typescript"],
    # ── Data / APIs ──────────────────────────────────────────────────────
    ["sql", "structured query language"],
    # Removed Phase 4: ["api", "rest api"] was too loose — "API" alone in a
    # resume should NOT auto-match a JD asking for "REST API" specifically;
    # different specificity levels, not synonyms.
]
