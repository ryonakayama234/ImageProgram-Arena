"""CC-01 independently verify identical local evidence, private labels and split."""
import unittest

import numpy as np

from adapters.imageprogram_reference.contextual_contour_cc01 import create_pair, validate_pair


class ContextualContourCC01ReviewTests(unittest.TestCase):
    def test_pair_same_local_and_private_label_absent(self):
        families = {}
        for split in ("development", "rotation_probe"):
            seen = set()
            for i in range(6):
                cases = create_pair(i, split=split)
                receipt = validate_pair(cases)
                self.assertEqual(receipt["split"], split)
                self.assertNotEqual(*receipt["public_digests"])
                seen.add(receipt["template_family"])
                for public, private in cases:
                    self.assertEqual(public["pixels_l8"].shape, (72, 72))
                    self.assertNotIn("correct_action", public)
                    self.assertNotIn("source_family", public)
                    self.assertIn(private.correct_action, ("continue", "stop"))
            self.assertEqual(len(seen), 1)
            families[split] = next(iter(seen))
        self.assertNotEqual(families["development"], families["rotation_probe"])

    def test_invalid_pair_rejected(self):
        cases = create_pair(0)
        with self.assertRaises(ValueError):
            validate_pair(cases[:1])
        wrong_public = dict(cases[1][0])
        wrong_public["pixels_l8"] = np.full((72, 72), 255, dtype=np.uint8)
        with self.assertRaises(ValueError):
            validate_pair((cases[0], (wrong_public, cases[1][1])))

if __name__ == "__main__":
    unittest.main()
