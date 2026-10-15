"""Arena-only CC-02 pair admission and prospective confirmation seal tests."""
import unittest
from dataclasses import replace

import numpy as np

from adapters.imageprogram_reference.contextual_contour_cc02_pilot import (
    confirmation_seal,
)
from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
    create_confirmation_pair,
    create_controls,
    create_development_pair,
    validate_pair,
)


class ContextualContourCC02AdmissionTests(unittest.TestCase):
    def test_pair_admission_and_isolated_oracle(self):
        for factory, split in (
            (create_development_pair, "development"),
            (create_confirmation_pair, "confirmation"),
        ):
            for i in range(6):
                pair = factory(i)
                receipt = validate_pair(pair)
                self.assertEqual(receipt["split"], split)
                self.assertNotEqual(*receipt["public_sha256"])
                self.assertEqual({private.expected_action for _, private in pair},
                                 {"continue", "stop"})
                for public, private in pair:
                    self.assertEqual(len(public), 6)
                    self.assertNotIn("expected_action", public)
                    self.assertNotIn("family", public)
                    self.assertNotIn("target_region", public)
                    self.assertEqual(private.split, split)

    def test_confirmation_not_a_rotation_of_development(self):
        development = create_development_pair(0)
        confirmation = create_confirmation_pair(0)
        dev_focus = development[0][0]["pixels_l8"][12:59, 6:55]
        conf_focus = confirmation[0][0]["pixels_l8"][12:59, 6:55]
        self.assertFalse(np.array_equal(dev_focus, conf_focus))
        seal = confirmation_seal()
        self.assertEqual(seal["status"], "sealed-NOT-SCORED")
        self.assertIsNone(seal["model_scores"])
        self.assertEqual(
            seal["manifest_sha256"],
            "ce2f33f187dcb5155b3e66c85f03dd7650e3a946889064cfaeb694db4b86fd36",
        )

    def test_public_tampering_or_metadata_leak_rejected(self):
        a, b = create_development_pair(0)
        leaked = dict(b[0])
        leaked["expected_action"] = b[1].expected_action
        with self.assertRaisesRegex(ValueError, "public-contract"):
            validate_pair((a, (leaked, b[1])))
        changed = dict(b[0])
        changed["pixels_l8"] = b[0]["pixels_l8"].copy()
        changed["pixels_l8"][25, 25] = 0
        with self.assertRaisesRegex(ValueError, "raster-hash-invalid"):
            validate_pair((a, (changed, b[1])))
        wrong_label = replace(b[1], expected_action="continue")
        with self.assertRaisesRegex(ValueError, "invalid-oracle-pair"):
            validate_pair((a, (b[0], wrong_label)))

    def test_controls_are_not_binary_pair_successes(self):
        controls = create_controls()
        self.assertEqual(len(controls), 3)
        self.assertEqual(
            [private.expected_action for _, private in controls],
            ["hold", "stop", "stop"],
        )
        self.assertEqual({private.split for _, private in controls}, {"control"})


if __name__ == "__main__":
    unittest.main()
