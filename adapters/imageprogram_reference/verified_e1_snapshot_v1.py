"""Immutable, digest-pinned inputs for independent ART-1 E1 G2 Arena scoring.

Every original file is read once through bounded no-follow descriptors.
Replay, provenance checks and terminal scoring must operate only on these
private temporary copies. No SourceArtwork originals enter this snapshot.
"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from adapters.imageprogram_reference.drawing_review import (
    MAX_PRIVATE_REPLAY_BYTES,
    MAX_PUBLIC_FRAME_BYTES,
    MAX_PUBLIC_METADATA_BYTES,
    MAX_PUBLIC_TRANSITIONS_BYTES,
    MAX_REPLAY_SNAPSHOT_BYTES,
    DrawingReviewError,
    _public_snapshot,
    json_object_bytes,
    sha256_bytes,
)
from adapters.imageprogram_reference.reference_target_v1 import FirstContactScoreError

MODES = ("noop", "feedback_off", "feedback_on")
MAX_TOTAL_INPUT_BYTES = 3 * MAX_REPLAY_SNAPSHOT_BYTES + 20 * MAX_PUBLIC_METADATA_BYTES
MAX_MANIFEST_ENTRIES = 2048


@dataclass(frozen=True)
class FrozenE1Inputs:
    """Paths below a TemporaryDirectory, never to an original episode."""
    public_dir: Path
    sessions_dir: Path
    manifest_digests: dict[str, str]
    input_digests: dict[str, str]


def _safe_root(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise FirstContactScoreError("snapshot input must be a non-symlink directory")


def _top_file(root: Path, name: str, limit: int = MAX_PUBLIC_METADATA_BYTES) -> bytes:
    """Snapshot a single allowlisted top-level filename with Linux no-follow."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise FirstContactScoreError("unsafe E1 top-level filename")
    folder = file_fd = None
    try:
        folder = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        file_fd = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder
        )
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise FirstContactScoreError("E1 sidecar is not a unique regular file")
        if info.st_size > limit:
            raise FirstContactScoreError("E1 sidecar exceeds size limit")
        with os.fdopen(os.dup(file_fd), "rb") as handle:
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise FirstContactScoreError("E1 sidecar exceeds read limit")
        return data
    except OSError as exc:
        raise FirstContactScoreError("cannot safely read E1 sidecar") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if folder is not None:
            os.close(folder)


def _copy_episode(source: Path, target: Path) -> str:
    _safe_root(source)
    try:
        manifest_bytes = _public_snapshot(
            source, "manifest.json", MAX_PUBLIC_METADATA_BYTES, manifest=True
        )
        manifest = json_object_bytes(manifest_bytes, "manifest.json")
        if manifest.get("format") != "imageprogram-episode-1":
            raise FirstContactScoreError("unrecognized canonical Episode format")
        files = manifest.get("files")
        sites = manifest.get("sites_files")
        if (not isinstance(files, dict) or not files
                or len(files) > MAX_MANIFEST_ENTRIES
                or not isinstance(sites, list)):
            raise FirstContactScoreError("invalid Episode manifest inventory")
        if not all(isinstance(k, str) for k in files):
            raise FirstContactScoreError("non-string artifact key")
        if sites != [name for name in files if not name.startswith("private/")]:
            raise FirstContactScoreError("Episode public/private inventory mismatch")
        required = {
            "request.json", "program.json", "result.json",
            "transitions.jsonl", "frames/000000.png", "final.png",
        }
        if not required.issubset(files):
            raise FirstContactScoreError("incomplete P1 Episode")
        if manifest.get("result_sha256") != files["result.json"]:
            raise FirstContactScoreError("result SHA not manifest bound")
        target.mkdir()
        total = len(manifest_bytes)
        for name, digest in files.items():
            private = name.startswith("private/")
            limit = (
                MAX_PRIVATE_REPLAY_BYTES if private else
                MAX_PUBLIC_FRAME_BYTES if name.endswith(".png") else
                MAX_PUBLIC_TRANSITIONS_BYTES if name == "transitions.jsonl" else
                MAX_PUBLIC_METADATA_BYTES
            )
            data = _public_snapshot(source, name, limit, private=private)
            if not isinstance(digest, str) or sha256_bytes(data) != digest:
                raise FirstContactScoreError("Episode manifest file hash mismatch: " + name)
            total += len(data)
            if total > MAX_REPLAY_SNAPSHOT_BYTES:
                raise FirstContactScoreError("Episode snapshot exceeds byte budget")
            dest = target.joinpath(*Path(name).parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        (target / "manifest.json").write_bytes(manifest_bytes)
        return sha256_bytes(manifest_bytes)
    except (DrawingReviewError, OSError, KeyError) as exc:
        raise FirstContactScoreError("invalid or unsafe original P1 Episode") from exc


@contextmanager
def snapshot_e1_inputs(public_dir: Path, sessions_dir: Path) -> Iterator[FrozenE1Inputs]:
    """Freeze all three paired Episodes and all referenced public sidecars.

    Consumer code must not reopen public_dir or sessions_dir during scoring.
    Temp checkpoint data is automatically deleted; published provenance is
    hashes only, never a source path, hidden original, or checkpoint.
    """
    public_dir, sessions_dir = Path(public_dir), Path(sessions_dir)
    _safe_root(public_dir)
    _safe_root(sessions_dir)
    try:
        if {entry.name for entry in public_dir.iterdir()} != {
            "task.json", "reference_roi.png"
        }:
            raise FirstContactScoreError("public ROI must contain exactly two files")
        with tempfile.TemporaryDirectory(prefix="arena-e1-pinned-") as tmp:
            dest = Path(tmp)
            public = dest / "public"
            sessions = dest / "sessions"
            public.mkdir()
            sessions.mkdir()
            task = _top_file(public_dir, "task.json", 16384)
            reference = _top_file(public_dir, "reference_roi.png", 1024 * 1024)
            (public / "task.json").write_bytes(task)
            (public / "reference_roi.png").write_bytes(reference)
            digests = {
                "public_task": sha256_bytes(task),
                "public_reference_png": sha256_bytes(reference),
            }
            names = ["summary.json"]
            for mode in MODES:
                names.extend((mode + "_receipt.json", mode + "_replay.json"))
            size = len(task) + len(reference)
            for name in names:
                contents = _top_file(sessions_dir, name)
                size += len(contents)
                if size > MAX_TOTAL_INPUT_BYTES:
                    raise FirstContactScoreError("E1 comparison exceeds input budget")
                (sessions / name).write_bytes(contents)
                digests[name] = sha256_bytes(contents)
                json_object_bytes(contents, name)
            manifests = {}
            for mode in MODES:
                episode_name = mode + "_episode"
                original = sessions_dir / episode_name
                manifests[mode] = _copy_episode(original, sessions / episode_name)
            yield FrozenE1Inputs(public, sessions, manifests, digests)
    except (DrawingReviewError, OSError, ValueError) as exc:
        if isinstance(exc, FirstContactScoreError):
            raise
        raise FirstContactScoreError("E1 input snapshot verification failed") from exc
