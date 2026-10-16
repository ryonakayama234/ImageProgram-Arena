"""CC-02-V: independent geometry annotation / evaluation controls.

Integration test requires the branch of ImageProgram with public trace installed.
No confirmation task factory is imported or evaluated by the audit runner.
"""
import unittest

import numpy as np

from adapters.imageprogram_reference.contextual_contour_cc02_tasks import (
    create_development_pair,
)
from adapters.imageprogram_reference.contextual_contour_cc02_v_audit import (
    DEVELOPMENT_MANIFEST_SHA256,
    _sha_json,
    development_private_arc,
    run_development_audit,
)


class CC02VArcEvidenceTests(unittest.TestCase):
    def test_six_positive_arcs_are_literal_visible_public_pixels(self):
        for i in range(6):
            public, private = create_development_pair(i)[0]
            arc = development_private_arc(i, private)
            self.assertTrue(arc.target_xy)
            self.assertTrue(all(public["pixels_l8"][y, x] != 255
                                for x, y in arc.target_xy))
            self.assertEqual(arc.member_id, private.member_id)

    def test_six_negative_members_have_no_positive_target_arc(self):
        for i in range(6):
            public, private = create_development_pair(i)[1]
            arc = development_private_arc(i, private)
            self.assertEqual(arc.target_xy, ())
            self.assertTrue(arc.excluded_xy)
            self.assertTrue(all(public["pixels_l8"][y, x] != 255
                                for x, y in arc.excluded_xy))

    def test_weak_arc_retained_in_raster_but_lost_at_threshold(self):
        public, private = create_development_pair(3)[0]
        arc = development_private_arc(3, private)
        self.assertEqual({int(public["pixels_l8"][y, x])
                          for x, y in arc.target_xy}, {218})
        self.assertFalse(any(public["pixels_l8"][y, x] < 200
                             for x, y in arc.target_xy))

    def test_private_annotation_is_not_part_of_public_task(self):
        public, private = create_development_pair(4)[0]
        arc = development_private_arc(4, private)
        self.assertNotIn("target_xy", public)
        self.assertNotIn("excluded_xy", public)
        self.assertNotIn("expected_action", public)
        self.assertNotIn("member_id", public)
        self.assertNotIn("target_xy", str(sorted(public.keys())))
        self.assertNotEqual(_sha_json(arc.target_xy), public["raster_digest"])

    def test_development_only_stage_audit_remains_v2_and_sealed(self):
        result = run_development_audit()
        self.assertEqual(result["development_manifest_sha256"],
                         DEVELOPMENT_MANIFEST_SHA256)
        self.assertEqual(result["model_version"], "contextual-contour-cc01-v2")
        self.assertEqual(result["confirmation"], "NOT SCORED")
        self.assertEqual(result["real_art"], "NOT RUN")
        self.assertEqual(len(result["private_reviews"]), 12)
        self.assertEqual(len(result["controls"]), 3)
        self.assertEqual(len(result["pregrade_receipts"]), 15)
        self.assertEqual(result["summary"]["by_arm"]["B"]["correct_members"], 7)
        self.assertEqual(
            sum(result["summary"]["b_positive_earliest_blockers"].values()), 6)
        for rec in result["pregrade_receipts"]:
            self.assertEqual(len({d["candidate_set_sha256"]
                                 for d in rec["decisions"]}), 1)
            self.assertNotIn("expected_action", rec)
            self.assertNotIn("target_xy", rec)

    def test_public_scenes_remain_distinct_with_identical_focus(self):
        for i in range(6):
            (a, _), (b, _) = create_development_pair(i)
            x0, y0, x1, y1 = a["focus_box"]
            self.assertTrue(np.array_equal(
                a["pixels_l8"][y0:y1, x0:x1],
                b["pixels_l8"][y0:y1, x0:x1],
            ))
            self.assertNotEqual(a["raster_digest"], b["raster_digest"])


if __name__ == "__main__":
    unittest.main()
