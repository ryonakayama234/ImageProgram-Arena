import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.imageprogram_reference.drawing_review import (
    DrawingReviewError,
    canonical_jsonl_hash,
    create_review_pack,
)


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def write(root, filename, data):
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def jsonb(obj):
    return (json.dumps(obj) + '\n').encode()


def fixture(root):
    ep = root / 'episode'
    ep.mkdir()
    paths = {
        'request.json': jsonb({'request_id': 'draw1', 'seed': 17, 'body': {'tools': ['pen']}, 'goal': {'prompt': 'one'}}),
        'result.json': jsonb({'request_id': 'draw1', 'accepted_actions': 4, 'status': 'program_exhausted', 'stop_reason': 'done', 'initial_state_hash': 'state-initial-test', 'final_state_hash': 'state-final-test', 'versions': {'world': 'v0'}, 'costs': {'motor_commands': 4}}),
        'program.json': b'{}\n', 'initial_observation.json': b'{}\n', 'transitions.jsonl': b'{}\n',
        'frames/000000.png': b'\x89PNG\r\n\x1a\nA',
        'frames/000001.png': b'\x89PNG\r\n\x1a\nB',
        'frames/000002.png': b'\x89PNG\r\n\x1a\nC',
        'frames/000003.png': b'\x89PNG\r\n\x1a\nD',
        'frames/000004.png': b'\x89PNG\r\n\x1a\nE',
        'final.png': b'\x89PNG\r\n\x1a\nE',
        'private/initial.npz': b'secret',
        'private/final.npz': b'secret2',
    }
    for key, data in paths.items():
        write(ep, key, data)
    manifest = {
        'format': 'imageprogram-episode-1',
        'files': {key: digest(data) for key, data in paths.items()},
        'sites_files': [key for key in paths if not key.startswith('private/')],
        'result_sha256': digest(paths['result.json']),
    }
    write(ep, 'manifest.json', jsonb(manifest))
    rp = write(root, 'replay.json', jsonb({'verified': True, 'transitions': 4, 'final_state_hash': 'state-final-test', 'status': 'program_exhausted', 'goal_evaluated': False}))
    return ep, rp


def fake_source_replay(episode):
    # Isolated consumer test fixture, not an ImageProgram World replay.
    result = json.loads((Path(episode) / 'result.json').read_text())
    return {
        'verified': True, 'transitions': result['accepted_actions'],
        'final_state_hash': result['final_state_hash'],
        'status': result['status'], 'goal_evaluated': False,
    }


class DrawingReviewTests(unittest.TestCase):
    def setUp(self):
        patcher = patch(
            'adapters.imageprogram_reference.drawing_review.source_replay',
            side_effect=fake_source_replay,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_create_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            pack = create_review_pack([('first', episode, replay)], root / 'pack')
            self.assertEqual(len(pack['sessions']), 1)
            self.assertFalse(pack['claims']['learned_policy_or_skill'])
            self.assertEqual((root / 'pack' / 'first-intermediate.png').read_bytes(),
                             (episode / 'frames/000002.png').read_bytes())
            self.assertNotIn('secret', (root / 'pack' / 'review.json').read_text())
            self.assertTrue((root / 'pack' / 'index.html').exists())

    def test_frame_swapped_to_private_symlink_after_replay_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            private = (episode / 'private' / 'final.npz').read_bytes()

            def swap_during_source_replay(selected):
                report = fake_source_replay(selected)
                frame = episode / 'frames' / '000002.png'
                frame.unlink()
                frame.symlink_to('../private/final.npz')
                return report

            with patch(
                'adapters.imageprogram_reference.drawing_review.source_replay',
                side_effect=swap_during_source_replay,
            ), self.assertRaises(DrawingReviewError):
                create_review_pack([('first', episode, replay)], root / 'pack')
            output = root / 'pack'
            if output.exists():
                self.assertFalse(any(p.read_bytes() == private for p in
                                     output.glob('*.png')))

    def test_parent_frames_symlink_swap_after_replay_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            private = episode / 'private'
            (private / 'frames').parent.mkdir(exist_ok=True)

            def swap_during_source_replay(selected):
                report = fake_source_replay(selected)
                shutil.move(str(episode / 'frames'), str(private / 'frames'))
                (episode / 'frames').symlink_to('private/frames', target_is_directory=True)
                return report

            with patch(
                'adapters.imageprogram_reference.drawing_review.source_replay',
                side_effect=swap_during_source_replay,
            ), self.assertRaises(DrawingReviewError):
                create_review_pack([('first', episode, replay)], root / 'pack')

    def test_modified_regular_frame_after_replay_fails_digest_before_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)

            def overwrite_during_source_replay(selected):
                report = fake_source_replay(selected)
                write(episode, 'final.png', b'changed-after-source-replay')
                return report

            with patch(
                'adapters.imageprogram_reference.drawing_review.source_replay',
                side_effect=overwrite_during_source_replay,
            ), self.assertRaisesRegex(DrawingReviewError, 'changed since validation'):
                create_review_pack([('first', episode, replay)], root / 'pack')
            self.assertFalse((root / 'pack' / 'first-final.png').exists())

    def test_swap_between_path_check_and_fd_open_cannot_export_private(self):
        # Force the swap at the last gap: after safe_public_path succeeds
        # during the secure snapshot but before os.open(O_NOFOLLOW).
        from adapters.imageprogram_reference.drawing_review import safe_public_path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            attacked = [False]

            def raced_check(source_root, filename):
                path = safe_public_path(source_root, filename)
                if (filename == 'frames/000002.png'
                        and (root / 'pack').exists() and not attacked[0]):
                    attacked[0] = True
                    path.unlink()
                    path.symlink_to('../private/final.npz')
                return path

            with patch(
                'adapters.imageprogram_reference.drawing_review.safe_public_path',
                side_effect=raced_check,
            ), self.assertRaises(DrawingReviewError):
                create_review_pack([('first', episode, replay)], root / 'pack')
            self.assertTrue(attacked[0])
            self.assertFalse((root / 'pack' / 'first-intermediate.png').exists())

    def test_metadata_symlink_swap_between_check_and_open_cannot_export_secrets(self):
        from adapters.imageprogram_reference.drawing_review import safe_public_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            private = write(episode, 'private/poison.json', jsonb({
                'request_id': 'draw1', 'seed': 'TOP_SECRET',
                'body': {'secret': 'CANARY'}, 'goal': {'secret': 'CANARY'},
            }))
            attacked = [False]

            def raced_public_check(source_root, filename):
                path = safe_public_path(source_root, filename)
                if filename == 'request.json' and not attacked[0]:
                    attacked[0] = True
                    path.unlink()
                    path.symlink_to('private/poison.json')
                return path

            with patch(
                'adapters.imageprogram_reference.drawing_review.safe_public_path',
                side_effect=raced_public_check,
            ), self.assertRaises(DrawingReviewError):
                create_review_pack([('first', episode, replay)], root / 'pack')
            self.assertTrue(attacked[0])
            self.assertFalse((root / 'pack').exists())
            self.assertIn(b'CANARY', private.read_bytes())

    def test_metadata_changed_during_source_replay_uses_verified_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)

            def poison_during_replay(selected):
                report = fake_source_replay(selected)
                request = json.loads((episode / 'request.json').read_text())
                request['seed'] = 'PRIVATE_AFTER_CHECK'
                request['body'] = {'secret': 'CANARY'}
                write(episode, 'request.json', jsonb(request))
                return report

            with patch(
                'adapters.imageprogram_reference.drawing_review.source_replay',
                side_effect=poison_during_replay,
            ):
                pack = create_review_pack([('first', episode, replay)], root / 'pack')
            record = pack['sessions'][0]
            self.assertEqual(record['seed'], 17)
            self.assertNotIn('CANARY', (root / 'pack' / 'review.json').read_text())
            self.assertNotIn('PRIVATE_AFTER_CHECK',
                             (root / 'pack' / 'review.json').read_text())

    def test_oversized_public_frame_fails_before_unbounded_hashing(self):
        from adapters.imageprogram_reference.drawing_review import MAX_PUBLIC_FRAME_BYTES
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            with (episode / 'frames' / '000002.png').open('r+b') as frame:
                frame.truncate(MAX_PUBLIC_FRAME_BYTES + 1)
            with self.assertRaisesRegex(DrawingReviewError, 'too large'):
                create_review_pack([('first', episode, replay)], root / 'pack')
            self.assertFalse((root / 'pack').exists())

    def test_oversized_public_json_fails_before_unbounded_parsing(self):
        from adapters.imageprogram_reference.drawing_review import MAX_PUBLIC_METADATA_BYTES
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            with (episode / 'request.json').open('r+b') as request:
                request.truncate(MAX_PUBLIC_METADATA_BYTES + 1)
            with self.assertRaisesRegex(DrawingReviewError, 'too large'):
                create_review_pack([('first', episode, replay)], root / 'pack')
            self.assertFalse((root / 'pack').exists())

    def test_replay_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            write(root, 'replay.json', jsonb({'verified': False}))
            with self.assertRaisesRegex(DrawingReviewError, 'replay'):
                create_review_pack([('first', episode, replay)], root / 'pack')
            self.assertFalse((root / 'pack').exists())

    def test_tampered_png_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            write(episode, 'final.png', b'bad')
            with self.assertRaisesRegex(DrawingReviewError, 'digest'):
                create_review_pack([('first', episode, replay)], root / 'pack')

    def test_private_file_leak_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            manifest = json.loads((episode / 'manifest.json').read_text())
            manifest['sites_files'].append('private/final.npz')
            write(episode, 'manifest.json', jsonb(manifest))
            with self.assertRaisesRegex(DrawingReviewError, 'public/private'):
                create_review_pack([('first', episode, replay)], root / 'pack')

    def test_final_must_match_terminal_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            write(episode, 'final.png', b'stale-final-image')
            manifest = json.loads((episode / 'manifest.json').read_text())
            manifest['files']['final.png'] = digest((episode / 'final.png').read_bytes())
            write(episode, 'manifest.json', jsonb(manifest))
            with self.assertRaisesRegex(DrawingReviewError, 'terminal numbered frame'):
                create_review_pack([('first', episode, replay)], root / 'pack')

    def test_status_must_be_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            result = json.loads((episode / 'result.json').read_text())
            result.pop('status')
            write(episode, 'result.json', jsonb(result))
            manifest = json.loads((episode / 'manifest.json').read_text())
            manifest['files']['result.json'] = digest((episode / 'result.json').read_bytes())
            manifest['result_sha256'] = manifest['files']['result.json']
            write(episode, 'manifest.json', jsonb(manifest))
            with self.assertRaisesRegex(DrawingReviewError, 'terminal execution status'):
                create_review_pack([('first', episode, replay)], root / 'pack')

    def test_hard_link_to_private_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            frame = episode / 'frames' / '000002.png'
            frame.unlink()
            frame.hardlink_to(episode / 'private' / 'final.npz')
            manifest = json.loads((episode / 'manifest.json').read_text())
            manifest['files']['frames/000002.png'] = digest(frame.read_bytes())
            write(episode, 'manifest.json', jsonb(manifest))
            with self.assertRaisesRegex(DrawingReviewError, 'hard-linked'):
                create_review_pack([('first', episode, replay)], root / 'pack')

    def test_request_id_relabel_cannot_make_episode_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            duplicate = root / 'copied'
            shutil.copytree(episode, duplicate)
            request = json.loads((duplicate / 'request.json').read_text())
            request['request_id'] = 'new-label-only'
            result = json.loads((duplicate / 'result.json').read_text())
            result['request_id'] = 'new-label-only'
            write(duplicate, 'request.json', jsonb(request))
            write(duplicate, 'result.json', jsonb(result))
            manifest = json.loads((duplicate / 'manifest.json').read_text())
            for name in ('request.json', 'result.json'):
                manifest['files'][name] = digest((duplicate / name).read_bytes())
            manifest['result_sha256'] = manifest['files']['result.json']
            write(duplicate, 'manifest.json', jsonb(manifest))
            with self.assertRaisesRegex(DrawingReviewError, 'duplicate episode identity'):
                create_review_pack([('baseline', episode, replay), ('variant', duplicate, replay)],
                                   root / 'pack')

    def test_json_whitespace_cannot_make_copied_episode_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            duplicate = root / 'copied'
            shutil.copytree(episode, duplicate)
            write(duplicate, 'program.json', b'{ } \n')
            manifest = json.loads((duplicate / 'manifest.json').read_text())
            manifest['files']['program.json'] = digest((duplicate / 'program.json').read_bytes())
            write(duplicate, 'manifest.json', jsonb(manifest))
            with self.assertRaisesRegex(DrawingReviewError, 'duplicate episode identity'):
                create_review_pack([('baseline', episode, replay), ('variant', duplicate, replay)],
                                   root / 'pack')

    def test_transition_jsonl_formatting_cannot_make_duplicate_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            duplicate = root / 'copied'
            shutil.copytree(episode, duplicate)
            # This changes file bytes but not the ordered transition record.
            write(duplicate, 'transitions.jsonl', b'{   }  \n')
            manifest = json.loads((duplicate / 'manifest.json').read_text())
            manifest['files']['transitions.jsonl'] = digest(
                (duplicate / 'transitions.jsonl').read_bytes()
            )
            write(duplicate, 'manifest.json', jsonb(manifest))
            with self.assertRaisesRegex(DrawingReviewError, 'duplicate episode identity'):
                create_review_pack([('baseline', episode, replay),
                                    ('variant', duplicate, replay)], root / 'pack')
            self.assertFalse((root / 'pack').exists())

    def test_transition_jsonl_key_order_cannot_make_duplicate_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            write(episode, 'transitions.jsonl', b'{"step": 1, "action": "stroke"}\n')
            source_manifest = json.loads((episode / 'manifest.json').read_text())
            source_manifest['files']['transitions.jsonl'] = digest(
                (episode / 'transitions.jsonl').read_bytes()
            )
            write(episode, 'manifest.json', jsonb(source_manifest))
            duplicate = root / 'copied'
            shutil.copytree(episode, duplicate)
            write(duplicate, 'transitions.jsonl', b'{ "action":"stroke", "step":1 }\n')
            manifest = json.loads((duplicate / 'manifest.json').read_text())
            manifest['files']['transitions.jsonl'] = digest(
                (duplicate / 'transitions.jsonl').read_bytes()
            )
            write(duplicate, 'manifest.json', jsonb(manifest))
            with self.assertRaisesRegex(DrawingReviewError, 'duplicate episode identity'):
                create_review_pack([('baseline', episode, replay),
                                    ('variant', duplicate, replay)], root / 'pack')

    def test_canonical_jsonl_preserves_transition_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            forward = write(root, 'forward.jsonl', b'{"step":1}\n{"step":2}\n')
            reverse = write(root, 'reverse.jsonl', b'{"step":2}\n{"step":1}\n')
            self.assertNotEqual(canonical_jsonl_hash(forward), canonical_jsonl_hash(reverse))

    def test_invalid_jsonl_record_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            invalid = write(root, 'bad.jsonl', b'{"step":1}\n   \n')
            with self.assertRaisesRegex(DrawingReviewError, 'JSONL record at line 2'):
                canonical_jsonl_hash(invalid)

    def test_report_cannot_replace_fresh_source_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            with patch(
                'adapters.imageprogram_reference.drawing_review.source_replay',
                return_value={'verified': False},
            ), self.assertRaisesRegex(DrawingReviewError, 'fresh source replay'):
                create_review_pack([('first', episode, replay)], root / 'pack')

    def test_noncanonical_frame_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            for alias in ('frames//000002.png', 'frames/./000002.png'):
                manifest = json.loads((episode / 'manifest.json').read_text())
                manifest['files'][alias] = manifest['files']['frames/000002.png']
                manifest['sites_files'].append(alias)
                write(episode, 'manifest.json', jsonb(manifest))
                with self.subTest(alias=alias), self.assertRaisesRegex(
                    DrawingReviewError, 'non-canonical'
                ):
                    create_review_pack([('first', episode, replay)], root / 'pack')
                self.assertFalse((root / 'pack').exists())
                # Restore the source manifest between subtests.
                manifest['files'].pop(alias)
                manifest['sites_files'].remove(alias)
                write(episode, 'manifest.json', jsonb(manifest))

    def test_parent_folder_symlink_to_private_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            (episode / 'private' / 'frames').parent.mkdir(exist_ok=True)
            shutil.move(str(episode / 'frames'), str(episode / 'private' / 'frames'))
            (episode / 'frames').symlink_to('private/frames', target_is_directory=True)
            with self.assertRaisesRegex(DrawingReviewError, 'symlink'):
                create_review_pack([('first', episode, replay)], root / 'pack')
            self.assertFalse((root / 'pack').exists())

    def test_duplicate_episode_different_labels_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            with self.assertRaisesRegex(DrawingReviewError, 'duplicate episode'):
                create_review_pack([('baseline', episode, replay), ('variant', episode, replay)],
                                   root / 'pack')
            self.assertFalse((root / 'pack').exists())

    def test_copied_episode_is_not_independent_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            duplicate = root / 'copied'
            shutil.copytree(episode, duplicate)
            with self.assertRaisesRegex(DrawingReviewError, 'duplicate episode identity'):
                create_review_pack([('baseline', episode, replay), ('variant', duplicate, replay)],
                                   root / 'pack')

    def test_swapped_replay_attestation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            write(root, 'replay.json', jsonb({
                'verified': True, 'transitions': 4, 'final_state_hash': 'other-session',
                'status': 'program_exhausted', 'goal_evaluated': False}))
            with self.assertRaisesRegex(DrawingReviewError, 'attestation'):
                create_review_pack([('first', episode, replay)], root / 'pack')
            self.assertFalse((root / 'pack').exists())

    def test_symlink_and_duplicate_labels_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            episode, replay = fixture(root)
            with self.assertRaisesRegex(DrawingReviewError, 'unique'):
                create_review_pack([('first', episode, replay), ('first', episode, replay)], root / 'pack')
            (episode / 'final.png').unlink()
            (episode / 'final.png').symlink_to('frames/000004.png')
            with self.assertRaisesRegex(DrawingReviewError, 'symlink'):
                create_review_pack([('first', episode, replay)], root / 'pack')


if __name__ == '__main__':
    unittest.main()
