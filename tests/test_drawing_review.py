import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.imageprogram_reference.drawing_review import (
    DrawingReviewError,
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
