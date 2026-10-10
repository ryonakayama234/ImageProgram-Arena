"""Unit controls for the Gate 0 audit; these are mocks, not real source episodes."""

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from adapters.imageprogram_reference.validate_gate0 import Gate0Failure, audit


# Valid one-pixel PNG; still only a synthetic fixture, never real-episode evidence.
MOCK_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9W3IftYAAAAASUVORK5CYII="
)


class Gate0AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.c2 = self.root / 'c2'
        self.review = self.root / 'review'
        (self.c2 / 'public').mkdir(parents=True)
        (self.c2 / 'private').mkdir(parents=True)
        self.review.mkdir()
        self.sha = 'a' * 40
        outcomes = {}
        sessions = []
        for i, label in enumerate(('analytic', 'manual')):
            end = f'final-{i}'
            outcomes[label] = {
                'status': 'program_exhausted', 'replay_verified': True,
                'initial_state_hash': 'start', 'final_state_hash': end,
                'newly_darkened_pixels': 10 + i, 'goal_evaluated_by_p1': False,
                'learned': False, 'protection_added_ink': {'face': 0.0, 'eye': 0.0},
                'accepted_actions': 10 + i, 'costs': {'motor_commands': 10 + i},
                're_observation': {'observation_id': str(i)},
            }
            self.write(self.c2 / 'private' / f'{label}_replay.json', {
                'verified': True, 'final_state_hash': end,
                'goal_evaluated': False, 'transitions': 10 + i,
            })
            images = {}
            for kind in ('initial', 'intermediate', 'final'):
                filename = f'{label}-{kind}.png'
                (self.review / filename).write_bytes(MOCK_PNG)
                digest = 'sha256:' + hashlib.sha256(MOCK_PNG).hexdigest()
                images[kind] = {
                    'file': filename, 'sha256': digest, 'source_sha256': digest,
                }
            sessions.append({
                'label': label, 'fresh_source_replay_verified': True,
                'replay_attested_by_source': True,
                'status': 'program_exhausted', 'accepted_actions': 10 + i,
                'initial_state_hash': 'start', 'final_state_hash': end,
                'source_request_semantic_hash': 'same-request',
                'source_program_semantic_hash': f'program-{i}',
                'images': images,
            })
        self.summary = {
            'same_preparation_state': True, 'candidate_count': 2,
            'frozen_character_witness_modified': False, 'episodes': outcomes,
        }
        self.pack = {'sessions': sessions, 'claims': {
            'visualized_real_source_episode': True,
            'learned_policy_or_skill': False, 'independent_arena_replay': False,
        }}
        self.persist()

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def persist(self):
        self.write(self.c2 / 'public' / 'summary.json', self.summary)
        self.write(self.review / 'review.json', self.pack)

    def run_audit(self):
        return audit(self.c2, self.review, self.sha, 'b' * 40)

    def test_valid_mock_contract_is_only_automated_pass(self):
        self.assertEqual(self.run_audit()['status'], 'AUTOMATED_PASS_VISUAL_REVIEW_PENDING')

    def test_reject_same_final_state(self):
        self.pack['sessions'][1]['final_state_hash'] = 'final-0'
        self.summary['episodes']['manual']['final_state_hash'] = 'final-0'
        self.write(self.c2 / 'private' / 'manual_replay.json', {
            'verified': True, 'final_state_hash': 'final-0',
            'goal_evaluated': False, 'transitions': 11,
        })
        self.persist()
        with self.assertRaisesRegex(Gate0Failure, 'identical final states'):
            self.run_audit()

    def test_reject_wrong_comparison_budget_identity(self):
        self.pack['sessions'][1]['source_request_semantic_hash'] = 'different-request'
        self.persist()
        with self.assertRaisesRegex(Gate0Failure, 'changed task/body/budget'):
            self.run_audit()

    def test_reject_missing_fresh_replay(self):
        self.pack['sessions'][0]['fresh_source_replay_verified'] = False
        self.persist()
        with self.assertRaisesRegex(Gate0Failure, 'freshly replay'):
            self.run_audit()

    def test_reject_protection_violations(self):
        self.summary['episodes']['analytic']['protection_added_ink']['eye'] = 1.0
        self.persist()
        with self.assertRaisesRegex(Gate0Failure, 'protection violation'):
            self.run_audit()

    def test_reject_no_actual_ink(self):
        self.summary['episodes']['manual']['newly_darkened_pixels'] = 0
        self.persist()
        with self.assertRaisesRegex(Gate0Failure, 'no actual ink'):
            self.run_audit()

    def test_reject_semantically_identical_program(self):
        self.pack['sessions'][1]['source_program_semantic_hash'] = 'program-0'
        self.persist()
        with self.assertRaisesRegex(Gate0Failure, 'semantically identical'):
            self.run_audit()

    def test_reject_tampered_review_frame_bytes(self):
        (self.review / 'analytic-final.png').write_bytes(b'fake-image')
        with self.assertRaisesRegex(Gate0Failure, 'invalid PNG review frame'):
            self.run_audit()

    def test_reject_frame_digest_mismatch(self):
        self.pack['sessions'][0]['images']['final']['sha256'] = 'sha256:' + '0' * 64
        self.persist()
        with self.assertRaisesRegex(Gate0Failure, 'review frame digest mismatch'):
            self.run_audit()

    def test_reject_review_path_traversal(self):
        self.pack['sessions'][0]['images']['initial']['file'] = '../other.png'
        self.persist()
        with self.assertRaisesRegex(Gate0Failure, 'invalid review frame path'):
            self.run_audit()

    def test_reject_preparation_in_continuation_cost(self):
        self.summary['episodes']['analytic']['costs']['motor_commands'] = 114
        self.persist()
        with self.assertRaisesRegex(Gate0Failure, 'continuation cost'):
            self.run_audit()


if __name__ == '__main__':
    unittest.main()
