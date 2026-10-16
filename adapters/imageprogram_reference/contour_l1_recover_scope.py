"""Rebuild a review scope from a new source-exact observation, with full case audit.

Never equate a new timing-bearing observation JSON to the original SHA. The archived
GitHub evidence is used only here for a stage-isolated case-fingerprint comparison,
not delivered to human reviewers as ground truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path

EVIDENCE_GIT_BLOB_SHA1 = "7427a2e8d51773916e11bdd19da818e9a2f79167"
EXPECTED_ORIGINAL_OBSERVATION = "01d4cb52b2cc62f86c06730b9bc00982e03209ad14b2c7b519f0d1d1796b0af0"
RECOVERY_VERSION = "cc02-l1-recovered-observation-scope-v1"
OBS_VERSION = "arena-g1-observed-p02-v1"
SCOPE_VERSION = "cc02-blind-l0-l1-review-v1"


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def git_blob_sha1(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def checked_evidence(path):
    raw = path.read_bytes()
    if git_blob_sha1(raw) != EVIDENCE_GIT_BLOB_SHA1:
        raise ValueError("historical-evidence-git-blob-drift")
    return json.loads(raw)


def recover_scope(observation, frozen_scope, evidence):
    """Fail closed unless all 27 recorded case fingerprints match historic evidence."""
    if (observation.get("protocol") != OBS_VERSION
            or observation.get("stage") != "observe"
            or observation.get("original_confirmation") != "NOT_RUN"
            or observation.get("input_scope") != "actual-p02-arms-from-existing-synthetic-raster-bank"):
        raise ValueError("unexpected-observation-protocol")
    if (frozen_scope.get("protocol") != SCOPE_VERSION
            or frozen_scope.get("observation_sha256") != EXPECTED_ORIGINAL_OBSERVATION
            or evidence.get("protocol") != "cc02-g1-python312-observed-p02-evidence-v1"
            or evidence.get("artifacts", {}).get("observation", {}).get("canonical_sha256")
            != EXPECTED_ORIGINAL_OBSERVATION):
        raise ValueError("unexpected-frozen-provenance")
    expected_source = evidence["source"]["prediction_source"]
    if (observation.get("source") != expected_source
            or observation["source"].get("heads") != frozen_scope["source_heads"]):
        raise ValueError("exact-historical-code-identity-mismatch")
    historical = evidence.get("all_case_reviews", [])
    rows = observation.get("rows", [])
    if (len(rows) != 27 or len(historical) != 27
            or len({r.get("task_id") for r in rows}) != 27
            or evidence["results"]["scenes"] != 27
            or evidence["results"]["observed_fragments"] != 32
            or evidence["results"]["all_observed_pairs"] != 37
            or evidence["results"]["unknown_pairs"] != 10):
        raise ValueError("scene-or-historical-universe-drift")
    total_nodes = total_pairs = 0
    mismatches = []
    for i, (row, original) in enumerate(zip(rows, historical)):
        n = len(row.get("fragments", []))
        total_nodes += n
        total_pairs += n * (n - 1) // 2
        if (row.get("task_id") != f"obs-{i:02d}"
                or row["task_id"] != original["task_id"]
                or row.get("family") != original["family"]
                or row.get("case_id") != original["case_id"]
                or row.get("p02_status") != original["p02_status"]
                or row.get("fragment_sha256") != original["fragment_sha256"]
                or digest(row.get("fragments")) != original["fragment_sha256"]
                or n != original["nodes"]
                or len(row.get("p02_arms", [])) != n
                or n * (n - 1) // 2 != original["pair_count"]):
            mismatches.append(row.get("task_id", f"index-{i}"))
    if mismatches or total_nodes != 32 or total_pairs != 37:
        raise ValueError("historical-case-fingerprint-drift:" + ",".join(mismatches))
    unknowns = {
        x["task_id"]: sum(x["counts"]["g0"].get(k, 0)
                          for k in ("unknown_possible", "unknown_other"))
        for x in historical
    }
    if {k: v for k, v in unknowns.items() if v} != {
            "obs-02": 3, "obs-10": 6, "obs-11": 1}:
        raise ValueError("unknown-pair-universe-drift")
    for req in frozen_scope["tasks"]:
        row = rows[int(req["task_id"].split("-")[-1])]
        ids = [fragment["node_id"] for fragment in row["fragments"]]
        if (row["fragment_sha256"] != req["fragment_sha256"]
                or [list(p) for p in combinations(ids, 2)] != req["pairs"]):
            raise ValueError("target-review-pair-drift")
    new_sha = digest(observation)
    recovered = dict(frozen_scope)
    recovered["observation_sha256"] = new_sha
    recovered["reconstruction"] = {
        "method": RECOVERY_VERSION,
        "original_observation_sha256": EXPECTED_ORIGINAL_OBSERVATION,
        "source_evidence_git_blob_sha1": EVIDENCE_GIT_BLOB_SHA1,
        "case_fingerprints_compared": 27,
        "identical_code_and_case_fingerprints": True,
        "new_digest_is_not_original_receipt": True,
        "original_confirmation": "NOT_RUN",
    }
    return recovered


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--frozen-scope", type=Path, required=True)
    parser.add_argument("--historical-evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    observation = json.loads(args.observation.read_text(encoding="utf-8"))
    scope = json.loads(args.frozen_scope.read_text(encoding="utf-8"))
    archive = checked_evidence(args.historical_evidence)
    result = recover_scope(observation, scope, archive)
    write_new(args.out, result)
    print("REBUILT_OBSERVATION_SHA256", result["observation_sha256"])
    print("RECOVERED_SCOPE_SHA256", digest(result))


if __name__ == "__main__":
    main()
