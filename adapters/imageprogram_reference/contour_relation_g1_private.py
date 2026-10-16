"""GRADE ONLY: source-author synthetic G-only relation answers, NOT blinded art labels."""
# For question 'is relation a->b a continuation?' and optional second branch a->c.
# Unknown examples are scored for representation/abstention only, not as path truth.
EXPECTED_G_ONLY = {
    "gdev-00": {"a:b": "positive"},
    "gdev-01": {"a:b": "positive"},
    "gdev-02": {"a:b": "positive"},
    "gdev-03": {"a:b": "negative"},
    "gdev-04": {"a:b": "negative"},
    "gdev-05": {"a:b": "negative"},
    "gdev-06": {"a:b": "unknown", "a:c": "unknown"},
    "gdev-07": {"a:b": "unknown"},
}
