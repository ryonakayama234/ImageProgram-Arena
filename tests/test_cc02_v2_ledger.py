"""CC-02-V2: provenance, split isolation and false-join ledger invariants."""
import importlib.util
import unittest
from adapters.imageprogram_reference.cc02_v2_ledger import (
    ARMS,
    EXPECTED_MODEL_VERSION,
    FIXED,
    PROTOCOL,
    REQUIRED_CASES,
    canonical,
    excluded_paths,
    private_grade,
    predict,
    sha256,
    verify_receipt,
)


def fake_receipt():
    graph = {"nodes": [], "edges": [], "version": EXPECTED_MODEL_VERSION}
    graph["candidate_set_sha256"] = sha256({
        **graph, "threshold": FIXED["threshold"], "max_gap": FIXED["max_gap"]
    })
    predictions = []
    for key in sorted(REQUIRED_CASES):
        for arm in (ARMS if key.startswith("dev-") else ("B",)):
            predictions.append({
                "case_key": key, "public_sha256": "sha-placeholder",
                "graph": graph, "decision": {
                    "arm": arm, "action": "stop", "reason": "test",
                    "candidate_set_sha256": graph["candidate_set_sha256"],
                    "selected_nodes": [], "explored_edges": 0,
                    "version": EXPECTED_MODEL_VERSION,
                },
            })
    payload = {
        "protocol": PROTOCOL, "split": "development-and-controls-only",
        "model_version": EXPECTED_MODEL_VERSION, "arena_version": "test",
        "model_checkout_sha": "0" * 40, "arena_checkout_sha": "1" * 40,
        "python": "3.12", "numpy": "2.3.5", "config": FIXED,
        "predictions": predictions, "case_count": 15, "prediction_count": 39,
        "confirmation": "NOT_RUN", "real_art": "NOT_RUN",
        "private_review": "NOT_LOADED_IN_PREDICTION_PROCESS",
    }
    payload["receipt_sha256"] = sha256(payload)
    return payload


class LedgerV2ContractTests(unittest.TestCase):
    def test_canonical_hash_deterministic(self):
        self.assertEqual(canonical({"b": 2, "a": 1}),
                         canonical({"a": 1, "b": 2}))
        self.assertEqual(len(sha256({"x": 1})), 64)

    def test_valid_staged_receipt_has_fifteen_cases(self):
        data = fake_receipt()
        registry = verify_receipt(data, expected_sha=data["receipt_sha256"])
        self.assertEqual(len(registry), 39)
        self.assertEqual(len({k for k, _ in registry}), 15)

    def test_external_receipt_hash_must_match(self):
        data = fake_receipt()
        with self.assertRaisesRegex(ValueError, "receipt-integrity"):
            verify_receipt(data, expected_sha="0" * 64)
        data["predictions"][0]["decision"]["action"] = "continue"
        with self.assertRaisesRegex(ValueError, "receipt-integrity"):
            verify_receipt(data, expected_sha=data["receipt_sha256"])

    def test_no_missing_or_duplicated_predictions(self):
        data = fake_receipt()
        data["predictions"][-1] = data["predictions"][0]
        data["receipt_sha256"] = sha256({
            k: v for k, v in data.items() if k != "receipt_sha256"
        })
        with self.assertRaisesRegex(ValueError, "duplicate-or-missing"):
            verify_receipt(data, expected_sha=data["receipt_sha256"])

    def test_stored_graph_must_match_model_content_hash(self):
        data = fake_receipt()
        data["predictions"][0]["graph"]["nodes"].append({"injected": True})
        data["receipt_sha256"] = sha256({
            k: v for k, v in data.items() if k != "receipt_sha256"
        })
        with self.assertRaisesRegex(ValueError, "graph-content-sha-mismatch"):
            verify_receipt(data, expected_sha=data["receipt_sha256"])

    def test_negative_strokes_and_ambiguous_contract(self):
        from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
            create_controls, create_development_pair,
        )
        stop = create_development_pair(4)[1][1]
        forbidden = excluded_paths("dev-04-m1", stop)
        self.assertIn((59, 27 + 4 + 7), forbidden)
        self.assertIn((59, 27 + 4 + 12), forbidden)
        self.assertNotIn((59, 27 + 4), forbidden)
        ambiguous = create_controls()[0][1]
        self.assertEqual(ambiguous.expected_action, "hold")
        self.assertEqual(excluded_paths("control-0", ambiguous), set())
        neutral = create_controls()[2][1]
        self.assertIn((60, 54), excluded_paths("control-2", neutral))

    @unittest.skipUnless(importlib.util.find_spec("imageprogram") is not None,
                         "Full paired GitHub checkouts / Model install required")
    def test_real_paired_checkout_predict_then_private_grade(self):
        # Git cleanliness, 40-char commit IDs, Model version and unchanged
        # source generator are enforced inside predict/grade. Confirmation
        # must never be imported or invoked by either stage.
        import unittest.mock
        from adapters.imageprogram_reference import contextual_contour_cc02_tasks as tasks
        with unittest.mock.patch.object(tasks, "create_confirmation_pair",
                                        side_effect=AssertionError("sealed-use")):
            prediction = predict()
            digest = prediction["receipt_sha256"]
            review = private_grade(prediction, expected_sha=digest)
        self.assertEqual(prediction["prediction_count"], 39)
        self.assertEqual(review["controls_total"], 3)
        self.assertEqual(len(review["all_member_reviews"]), 39)
        self.assertEqual(len(review["continue_arc_reviews"]), 6)
        self.assertEqual(review["confirmation"], "NOT_SCORED")


if __name__ == "__main__":
    unittest.main()
