import hashlib
import json
import tempfile
import unittest
from pathlib import Path

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
        'result.json': jsonb({'request_id': 'draw1', 'accepted_actions': 4, 'status': 'program_exhausted', 'stop_reason': 'done', 'final_state_hash': 'state-final-test', 'versions': {'world': 'v0'}, 'costs': {'motor_commands': 4}}),
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
    rp = write(root, 'replay.json', jsonb({'verified': True}))
    return ep, rp


class DrawingReviewTests(unittest.TestCase):
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
