"""GRADE ONLY: source-author synthetic G-only relation answers, NOT blinded art labels."""
# For question 'is relation a->b a continuation?' and optional second branch a->c.
# Unknown examples are scored for representation/abstention only, not as path truth.
EXPECTED_G_ONLY = {
    "slanted-positive": {"a:b": "positive"},
    "curved-positive": {"a:b": "positive"},
    "straight-positive": {"a:b": "positive"},
    "parallel-negative": {"a:b": "negative"},
    "crossing-negative": {"a:b": "negative"},
    "side-negative": {"a:b": "negative"},
    "competing-unknown": {"a:b": "unknown", "a:c": "unknown"},
    "junction-zero-unknown": {"a:b": "unknown"},
}
