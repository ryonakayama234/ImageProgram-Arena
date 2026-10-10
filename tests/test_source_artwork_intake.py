"""A02 local-only source intake: synthetic fixtures and fail-closed boundaries."""
import io
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.source_artwork import (
    SourceIntakeError, ingest_local_source,
)

try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipUnless(Image is not None, "Pillow needed for image decoding")
class SourceArtworkIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / "source.png"
        self.image_bytes = self._png("RGB", (8, 5))
        self.image.write_bytes(self.image_bytes)

    def _png(self, mode, size):
        img = Image.new(mode, size, (1, 2, 3) if mode == "RGB" else (1, 2, 3, 128))
        buff = io.BytesIO()
        img.save(buff, format="PNG")
        return buff.getvalue()

    def ingest(self, **kwargs):
        defaults = {
            "editable_bbox": (1, 1, 4, 4),
            "source_family": "family-A",
            "rights": "local-study-only",
        }
        defaults.update(kwargs)
        return ingest_local_source(self.image, **defaults)

    def test_png_deterministic_and_no_raw_source_or_path(self):
        a = self.ingest()
        b = self.ingest()
        self.assertEqual(a, b)
        self.assertEqual(a["source"]["width_px"], 8)
        self.assertEqual(a["source"]["height_px"], 5)
        self.assertNotEqual(a["source"]["source_bytes_sha256"],
                            a["source"]["normalized_pixels_sha256"])
        self.assertEqual(a["roi"]["editable_bbox"], [1, 1, 4, 4])
        self.assertEqual(a["access_class"], "management_private")
        self.assertFalse(a["claims"]["runtime_task_bound"])
        self.assertNotIn(str(self.root), str(a))
        self.assertNotIn("pixel_data", str(a))

    def test_rgba_normalization_is_stable_and_white_composited(self):
        self.image.write_bytes(self._png("RGBA", (8, 5)))
        a = self.ingest()
        self.assertEqual(a["source"]["source_mode"], "RGBA")
        self.assertEqual(a["source"]["alpha_background_rgb"], [255, 255, 255])
        self.assertEqual(a, self.ingest())

    def test_jpeg_dimensions_and_exif_orientation(self):
        im = Image.new("RGB", (8, 5), (20, 30, 40))
        exif = Image.Exif()
        exif[274] = 6
        im.save(self.image, "JPEG", exif=exif)
        a = self.ingest()
        self.assertEqual((a["source"]["width_px"], a["source"]["height_px"]), (5, 8))
        self.assertEqual(a["source"]["exif_orientation_original"], 6)

    def test_protected_overlaps_editable_rejected(self):
        with self.assertRaisesRegex(SourceIntakeError, "overlap"):
            self.ingest(protected_bboxes=((3, 3, 5, 5),))

    def test_protected_disjoint_ok(self):
        a = self.ingest(protected_bboxes=((5, 1, 8, 4),))
        self.assertEqual(a["roi"]["protected_bboxes"], [[5, 1, 8, 4]])

    def test_degenerate_out_of_bounds_non_int_and_bool_rejected(self):
        for bbox in ((2, 2, 2, 3), (-1, 0, 3, 3), (0, 0, 9, 4),
                     (True, 0, 4, 4), (1.0, 0, 4, 4)):
            with self.subTest(bbox=bbox), self.assertRaises(SourceIntakeError):
                self.ingest(editable_bbox=bbox)

    def test_bad_bytes_rejected(self):
        self.image.write_bytes(b"not-a-png")
        with self.assertRaisesRegex(SourceIntakeError, "decode"):
            self.ingest()

    def test_symlink_source_rejected(self):
        link = self.root / "alias.png"
        link.symlink_to(self.image)
        with self.assertRaisesRegex(SourceIntakeError, "non-symlink"):
            ingest_local_source(link, editable_bbox=(1, 1, 4, 4),
                                source_family="A", rights="unknown")

    def test_missing_provenance_rejected(self):
        with self.assertRaisesRegex(SourceIntakeError, "source_family"):
            self.ingest(source_family="")
        with self.assertRaisesRegex(SourceIntakeError, "rights"):
            self.ingest(rights="")

    def test_unsupported_mode_and_icc_rejected(self):
        img = Image.new("P", (8, 5))
        img.save(self.image, "PNG")
        with self.assertRaisesRegex(SourceIntakeError, "unsupported image mode"):
            self.ingest()
        im = Image.new("RGB", (8, 5))
        im.save(self.image, "PNG", icc_profile=b"unhandled-profile")
        with self.assertRaisesRegex(SourceIntakeError, "ICC profile"):
            self.ingest()

    def test_oversized_source_rejected_before_decoding(self):
        self.image.write_bytes(b"x" * (16 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(SourceIntakeError, "byte budget"):
            self.ingest()


if __name__ == "__main__":
    unittest.main()
