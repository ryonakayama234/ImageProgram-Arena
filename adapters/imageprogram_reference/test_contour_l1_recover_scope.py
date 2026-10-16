import unittest
from itertools import combinations

from contour_l1_recover_scope import (
    EVIDENCE_GIT_BLOB_SHA1, EXPECTED_ORIGINAL_OBSERVATION,
    digest, recover_scope,
)

NONEMPTY = {2:3, 10:4, 11:2, 15:3, 16:3, 17:3, 18:3, 19:4, 20:4, 25:3}
UNKNOWN = {2:3, 10:6, 11:1}


def examples():
    heads = {'model':'model_sha','arena':'arena_sha'}
    src = {'heads': heads, 'p02':'p02_sha', 'g0':'g0_sha', 'g1':'g1_sha', 'adapter':'adapter_sha'}
    rows = []
    historical=[]
    for i in range(27):
        n=NONEMPTY.get(i,0)
        nodes=[{'node_id':f'n{j:03d}', 'endpoint_a':[0,0], 'endpoint_b':[1,1], 'tangent':[1,0],
                'pixels':1, 'mean_l8':0, 'region':'focus'} for j in range(n)]
        case=f'test-case-{i}'
        status='junction-budget-exceeded' if i==24 else 'arm-budget-exceeded' if i==26 else 'ok'
        family='dev' if i<12 else 'control' if i<15 else 'technical'
        frag_hash=digest(nodes)
        rows.append({'task_id': f'obs-{i:02d}', 'family':family,'case_id':case,'p02_status':status,
                     'fragments':nodes,'fragment_sha256':frag_hash, 'p02_arms':[{'support_xy':[]} for _ in range(n)],
                     'observation_seconds':0.002})
        historical.append({'task_id':f'obs-{i:02d}', 'family':family,'case_id':case,
                           'p02_status':status,'fragment_sha256':frag_hash,'nodes':n,
                           'pair_count':n*(n-1)//2,
                           'counts':{'g0':{'unknown_other':UNKNOWN.get(i,0)}}})
    observation={'protocol':'arena-g1-observed-p02-v1','stage':'observe',
                 'original_confirmation':'NOT_RUN',
                 'input_scope':'actual-p02-arms-from-existing-synthetic-raster-bank',
                 'source':src,'rows':rows}
    scope={'protocol':'cc02-blind-l0-l1-review-v1','observation_sha256':EXPECTED_ORIGINAL_OBSERVATION,
           'source_heads':heads,'tasks':[]}
    for i in UNKNOWN:
        r=rows[i]; ids=[z['node_id'] for z in r['fragments']]
        scope['tasks'].append({'task_id':r['task_id'], 'fragment_sha256':r['fragment_sha256'],
                               'pairs':[list(p) for p in combinations(ids,2)]})
    evidence={'protocol':'cc02-g1-python312-observed-p02-evidence-v1',
              'artifacts':{'observation':{'canonical_sha256':EXPECTED_ORIGINAL_OBSERVATION}},
              'source':{'prediction_source':src},
              'results':{'scenes':27,'observed_fragments':32,'all_observed_pairs':37,'unknown_pairs':10},
              'all_case_reviews':historical}
    return observation, scope, evidence

class RecoveryTests(unittest.TestCase):
    def test_valid_all_27(self):
        obs,sc,ev=examples(); recovered=recover_scope(obs,sc,ev)
        self.assertEqual(recovered['observation_sha256'],digest(obs))
        self.assertEqual(recovered['reconstruction']['case_fingerprints_compared'],27)
        self.assertEqual(recovered['reconstruction']['source_evidence_git_blob_sha1'],EVIDENCE_GIT_BLOB_SHA1)
        self.assertEqual(recovered['reconstruction']['original_observation_sha256'],EXPECTED_ORIGINAL_OBSERVATION)
        self.assertEqual(sc['observation_sha256'],EXPECTED_ORIGINAL_OBSERVATION)
    def test_timing_field_not_equated_to_historical_receipt(self):
        obs,sc,ev=examples()
        first=recover_scope(obs,sc,ev)
        obs['rows'][10]['observation_seconds']=3.0
        second=recover_scope(obs,sc,ev)
        self.assertNotEqual(first['observation_sha256'],second['observation_sha256'])
    def test_real_semantic_fragment_change_rejected(self):
        obs,sc,ev=examples();obs['rows'][2]['fragments'][0]['pixels']=999
        with self.assertRaisesRegex(ValueError,'historical-case-fingerprint-drift'):
            recover_scope(obs,sc,ev)
    def test_changed_case_id_rejected(self):
        obs,sc,ev=examples();obs['rows'][18]['case_id']='replaced'
        with self.assertRaisesRegex(ValueError,'historical-case-fingerprint-drift'):
            recover_scope(obs,sc,ev)
    def test_missing_empty_scene_rejected(self):
        obs,sc,ev=examples();obs['rows'].pop(5)
        with self.assertRaisesRegex(ValueError,'scene-or-historical-universe-drift'):
            recover_scope(obs,sc,ev)
    def test_historical_source_mismatch(self):
        obs,sc,ev=examples();obs['source']=dict(obs['source'],g1='modified')
        with self.assertRaisesRegex(ValueError,'exact-historical-code-identity-mismatch'):
            recover_scope(obs,sc,ev)
    def test_review_pair_universe_drift(self):
        obs,sc,ev=examples();sc['tasks'][1]['pairs'].pop()
        with self.assertRaisesRegex(ValueError,'target-review-pair-drift'):
            recover_scope(obs,sc,ev)
    def test_no_original_confirmation(self):
        obs,sc,ev=examples();obs['original_confirmation']='RUN'
        with self.assertRaisesRegex(ValueError,'unexpected-observation-protocol'):
            recover_scope(obs,sc,ev)
    def test_label_balance_changed_fail(self):
        obs,sc,ev=examples();ev['all_case_reviews'][2]['counts']['g0']['unknown_other']=2
        with self.assertRaisesRegex(ValueError,'unknown-pair-universe-drift'):
            recover_scope(obs,sc,ev)

if __name__=='__main__':
    unittest.main()
