"""Only new blind packet integrity contract checks, not full Arena matrix."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("blind", Path(__file__).with_name("contour_l1_review.py"))
blind = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blind)
SCOPE = json.loads(Path(__file__).with_name("cc02_l1_review_scope.json").read_text())


def sample():
    rows = []
    for i in range(27):
        task_id = f"obs-{i:02d}"
        req = next((r for r in SCOPE["tasks"] if r["task_id"] == task_id), None)
        ids = list(dict.fromkeys(x for pair in req["pairs"] for x in pair)) if req else []
        nodes = [{"node_id": name, "endpoint_a": [0.0, 0.0], "endpoint_b": [1.0, 0.0],
                  "tangent": [1.0, 0.0], "pixels": 2, "mean_l8": 0.0, "region": "focus"}
                 for name in ids]
        arms = [{"support_xy": [[0, 0], [1, 0]]} for _ in nodes]
        row = {"task_id": task_id, "fragments": nodes, "p02_arms": arms,
               "fragment_sha256": blind.digest(nodes), "focus": [0, 0, 2, 2],
               "raster_sha256": "0" * 64, "family": "dev", "case_id": task_id}
        rows.append(row)
    scope = copy.deepcopy(SCOPE)
    for t in scope["tasks"]:
        t["fragment_sha256"] = rows[int(t["task_id"].split("-")[1])]["fragment_sha256"]
    obs = {"protocol": "arena-g1-observed-p02-v1", "stage": "observe",
           "original_confirmation": "NOT_RUN", "source": {"heads": scope["source_heads"]},
           "rows": rows}
    scope["observation_sha256"] = blind.digest(obs)
    return obs, scope


class BlindL1Tests(unittest.TestCase):
    def packet(self):
        return blind.make_packet(*sample())

    def test_exact_ten_pairs_and_no_model_or_private_truth(self):
        p = self.packet()
        self.assertEqual([len(t["pairs"]) for t in p["tasks"]], [3, 6, 1])
        self.assertEqual(p["l2_intent"], "NOT_EVALUABLE")
        encoded = json.dumps(p).lower()
        for keyword in ("g0_edges", "g1_relations", "source_stroke", "target_region", "true_path"):
            self.assertNotIn(keyword, encoded)

    def test_observation_hash_tamper_rejected(self):
        obs, scope = sample()
        obs["rows"][1]["case_id"] = "mutated"
        with self.assertRaisesRegex(ValueError, "observation-or-scope-drift"):
            blind.make_packet(obs, scope)

    def test_fragment_hash_and_missing_pair_rejected(self):
        obs, scope = sample()
        obs["rows"][2]["fragments"][0]["pixels"] += 1
        scope["observation_sha256"] = blind.digest(obs)
        with self.assertRaisesRegex(ValueError, "fragment-digest-drift"):
            blind.make_packet(obs, scope)
        obs, scope = sample()
        scope["tasks"][1]["pairs"].pop()
        with self.assertRaisesRegex(ValueError, "pair-universe-drift"):
            blind.make_packet(obs, scope)

    def test_blank_review_is_not_success(self):
        p = self.packet()
        merged = blind.combine(p, blind.blank_response(p, "a"), blind.blank_response(p, "b"))
        self.assertEqual(merged["counts"], {"PENDING": 10})
        self.assertEqual(merged["g0_g1_scores"], "NOT_RUN")

    def test_two_reviewers_agree_only_if_visible_and_same_l1(self):
        p = self.packet()
        a, b = blind.blank_response(p, "a"), blind.blank_response(p, "b")
        for reviewer in (a, b):
            reviewer["l0"] = dict.fromkeys(reviewer["l0"], "supported")
            reviewer["l1"] = dict.fromkeys(reviewer["l1"], "same_visible_curve")
        r = blind.combine(p, a, b)
        self.assertEqual(r["counts"], {"CONSENSUS": 10})
        b["l1"][next(iter(b["l1"]))] = "different_visible_curve"
        r = blind.combine(p, a, b)
        self.assertEqual(r["counts"], {"DISPUTED": 1, "CONSENSUS": 9})
        a["l0"][next(iter(a["l0"]))] = "uncertain"
        self.assertGreater(blind.combine(p, a, b)["counts"]["UNRESOLVED_L0"], 0)

    def test_review_pair_universe_and_reviewer_uniqueness(self):
        p = self.packet()
        a, b = blind.blank_response(p, "a"), blind.blank_response(p, "b")
        b["reviewer_id"] = "a"
        with self.assertRaisesRegex(ValueError, "reviewers-not-independent"):
            blind.combine(p, a, b)
        b["reviewer_id"] = "b"
        b["l1"].pop(next(iter(b["l1"])))
        with self.assertRaisesRegex(ValueError, "invalid-b-response"):
            blind.combine(p, a, b)

    def test_reject_l2_claim_and_source_label_injection(self):
        p = self.packet()
        a, b = blind.blank_response(p, "a"), blind.blank_response(p, "b")
        a["l2_intent"] = "continue"
        with self.assertRaisesRegex(ValueError, "invalid-a-response"):
            blind.combine(p, a, b)
        a["l2_intent"] = "not_evaluable"
        a["l1"][next(iter(a["l1"]))] = "ground_truth_positive"
        with self.assertRaisesRegex(ValueError, "invalid-a-response"):
            blind.combine(p, a, b)


if __name__ == "__main__":
    unittest.main()
