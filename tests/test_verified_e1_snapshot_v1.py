"""Standalone tests for the private, hash-pinned E1 snapshot boundary."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.drawing_review import sha256_bytes
from adapters.imageprogram_reference.reference_target_v1 import FirstContactScoreError
from adapters.imageprogram_reference.verified_e1_snapshot_v1 import (
    _copy_episode,
    _top_file,
    snapshot_e1_inputs,
)


def _episode(root: Path) -> Path:
    root.mkdir()
    blobs = {
        "request.json": b'{"seed":17}',
        "program.json": b'{"actions":[]}',
        "result.json": b'{"status":"program_exhausted"}',
        "transitions.jsonl": b'{"step":0}\n',
        "frames/000000.png": b"synthetic-initial-frame",
        "final.png": b"synthetic-final-frame",
        "private/checkpoint.json": b"private-temporary-replay-only",
    }
    for name, data in blobs.items():
        f = root / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    manifest = {
        "format": "imageprogram-episode-1",
        "files": {name: sha256_bytes(data) for name, data in blobs.items()},
        "sites_files": [
            name for name in blobs if not name.startswith("private/")
        ],
        "result_sha256": sha256_bytes(blobs["result.json"]),
    }
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root


def _fixture(root: Path) -> tuple[Path, Path]:
    public = root / "public"
    public.mkdir()
    (public / "task.json").write_text('{"format":"fixture"}')
    (public / "reference_roi.png").write_bytes(b"fixture-reference-png")
    sessions = root / "sessions"
    sessions.mkdir()
    (sessions / "summary.json").write_text('{"format":"fixture"}')
    for mode in ("noop", "feedback_off", "feedback_on"):
        (sessions / (mode + "_receipt.json")).write_text('{"format":"fixture"}')
        (sessions / (mode + "_replay.json")).write_text('{"verified":true}')
        _episode(sessions / (mode + "_episode"))
    return public, sessions


class FrozenE1SnapshotV1Tests(unittest.TestCase):
    def test_snapshot_copies_verifies_and_is_independent_of_mutable_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public, sessions = _fixture(root)
            with snapshot_e1_inputs(public, sessions) as frozen:
                original = sessions / "feedback_on_episode" / "final.png"
                original.write_bytes(b"changed after fixation")
                self.assertEqual(
                    (frozen.sessions_dir / "feedback_on_episode" / "final.png").read_bytes(),
                    b"synthetic-final-frame",
                )
                self.assertEqual(set(frozen.manifest_digests),
                                 {"noop", "feedback_off", "feedback_on"})
                self.assertNotIn("private/checkpoint.json",
                                 json.dumps(frozen.input_digests))
                self.assertTrue(
                    (frozen.sessions_dir / "feedback_on_episode"
                     / "private/checkpoint.json").is_file()
                )
            self.assertFalse(frozen.sessions_dir.exists())

    def test_rejects_tampered_manifest_file_before_scoring(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public, sessions = _fixture(root)
            (sessions / "noop_episode" / "final.png").write_bytes(b"wrong")
            with (
                self.assertRaises(FirstContactScoreError),
                snapshot_e1_inputs(public, sessions),
            ):
                self.fail("tampered original entered trusted snapshot")

    def test_rejects_forged_public_private_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = _episode(root / "ep")
            path = original / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["sites_files"].append("private/checkpoint.json")
            path.write_text(json.dumps(manifest))
            with self.assertRaises(FirstContactScoreError):
                _copy_episode(original, root / "snapshot")

    def test_rejects_symlink_and_hardlink_episode_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = _episode(root / "ep")
            victim = source / "final.png"
            victim.unlink()
            victim.symlink_to("frames/000000.png")
            with self.assertRaises(FirstContactScoreError):
                _copy_episode(source, root / "snap1")
            victim.unlink()
            os.link(source / "frames/000000.png", victim)
            with self.assertRaises(FirstContactScoreError):
                _copy_episode(source, root / "snap2")

    def test_rejects_traversal_in_private_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = _episode(root / "ep")
            manifest_file = source / "manifest.json"
            manifest = json.loads(manifest_file.read_text())
            manifest["files"]["private/../escape"] = sha256_bytes(b"data")
            manifest_file.write_text(json.dumps(manifest))
            with self.assertRaises(FirstContactScoreError):
                _copy_episode(source, root / "snap")

    def test_rejects_extra_public_files_and_hardlinked_sidecars(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public, sessions = _fixture(root)
            extra = public / "private_source.json"
            extra.write_text("{}")
            with (
                self.assertRaises(FirstContactScoreError),
                snapshot_e1_inputs(public, sessions),
            ):
                self.fail("unexpected public input accepted")
            extra.unlink()
            os.link(sessions / "summary.json", sessions / "shared-hardlink.json")
            with self.assertRaises(FirstContactScoreError):
                _top_file(sessions, "summary.json")

    def test_top_sidecar_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original"
            original.write_text("{}")
            (root / "summary.json").symlink_to(original)
            with self.assertRaises(FirstContactScoreError):
                _top_file(root, "summary.json")


if __name__ == "__main__":
    unittest.main()
