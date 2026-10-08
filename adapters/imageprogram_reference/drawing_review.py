"""Read-only, hash-checked drawing session review packs for ImageProgram episodes.

Arena does not interpret the painter's program or verify physics itself. Replay must
be attested by ImageProgram's own runner before the session can be packaged.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

FORMAT = 'arena-drawing-review-v0'
LABEL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$')
PUBLIC_TOP = {'request.json', 'program.json', 'initial_observation.json',
              'transitions.jsonl', 'result.json', 'final.png', 'rejected_action.json'}


class DrawingReviewError(ValueError):
    """Invalid episode, provenance, or public/private boundary."""


def sha256(path: Path) -> str:
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise DrawingReviewError(f'invalid JSON: {path.name}') from exc
    if not isinstance(value, dict):
        raise DrawingReviewError(f'{path.name} must be a JSON object')
    return value


def safe_public_path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or '\\' in name:
        raise DrawingReviewError('invalid public artifact path')
    relative = Path(name)
    if (relative.is_absolute() or '..' in relative.parts or '.' in relative.parts
            or any(part.startswith('.') for part in relative.parts)):
        raise DrawingReviewError('unsafe public artifact path')
    if name not in PUBLIC_TOP and not (len(relative.parts) == 2
                                        and relative.parts[0] == 'frames'
                                        and re.fullmatch(r'\d{6}\.png', relative.name)):
        raise DrawingReviewError('non-public or unrecognized artifact path')
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink() or not path.is_file():
        raise DrawingReviewError(f'missing, symlinked, or escaping artifact: {name}')
    return path


def validate_session(label: str, episode: Path, replay_report: Path) -> dict:
    if not LABEL.fullmatch(label):
        raise DrawingReviewError('label must be a short ASCII slug')
    episode = Path(episode).resolve()
    manifest = read_json(episode / 'manifest.json')
    if manifest.get('format') != 'imageprogram-episode-1':
        raise DrawingReviewError('unsupported ImageProgram episode format')
    files = manifest.get('files')
    public = manifest.get('sites_files')
    if not isinstance(files, dict) or not isinstance(public, list):
        raise DrawingReviewError('invalid manifest files/sites_files')
    expected_public = [name for name in files if not name.startswith('private/')]
    if public != expected_public or len(set(public)) != len(public):
        raise DrawingReviewError('public/private artifact manifest boundary invalid')
    required = {'request.json', 'program.json', 'result.json', 'initial_observation.json',
                'transitions.jsonl', 'frames/000000.png', 'final.png'}
    if not required.issubset(public):
        raise DrawingReviewError('incomplete public episode')
    for name in public:
        path = safe_public_path(episode, name)
        if not isinstance(files[name], str) or sha256(path) != files[name]:
            raise DrawingReviewError(f'artifact digest mismatch: {name}')
    if manifest.get('result_sha256') != files['result.json']:
        raise DrawingReviewError('result digest mismatch')

    result = read_json(episode / 'result.json')
    request = read_json(episode / 'request.json')
    n = result.get('accepted_actions')
    if type(n) is not int or n < 2 or n > 1_000_000:
        raise DrawingReviewError('requires a completed multi-action episode')
    middle = n // 2
    frame_names = ['frames/000000.png', f'frames/{middle:06d}.png', 'final.png']
    if any(name not in public for name in frame_names):
        raise DrawingReviewError('initial/mid/final frames missing from manifest')
    if result.get('request_id') != request.get('request_id'):
        raise DrawingReviewError('request/result ID mismatch')
    if not isinstance(result.get('versions'), dict) or not result['versions']:
        raise DrawingReviewError('runtime versions missing')
    replay = read_json(Path(replay_report))
    if replay.get('verified') is not True:
        raise DrawingReviewError('ImageProgram replay is not verified')
    # A replay report is only an attestation from ImageProgram. Do not claim
    # that an independent Arena physics replay has taken place.
    return {
        'label': label, 'episode': episode, 'replay_report': Path(replay_report).resolve(),
        'frame_names': frame_names,
        'record': {
            'label': label, 'source_format': manifest['format'],
            'request_id': result['request_id'], 'seed': request.get('seed'),
            'body': request.get('body'), 'goal': request.get('goal'),
            'status': result.get('status'), 'stop_reason': result.get('stop_reason'),
            'accepted_actions': n, 'costs': result.get('costs'),
            'versions': result['versions'], 'replay_attested_by_source': True,
            'provenance': 'scripted_or_other_source_must_be_verified_separately',
            'episode_manifest_sha256': sha256(episode / 'manifest.json'),
            'replay_attestation_sha256': sha256(Path(replay_report)),
        },
    }


def create_review_pack(sessions: list[tuple[str, Path, Path]], out: Path) -> dict:
    if not sessions or len(sessions) > 16:
        raise DrawingReviewError('provide 1..16 sessions')
    labels = [item[0] for item in sessions]
    if len(labels) != len(set(labels)):
        raise DrawingReviewError('session labels must be unique')
    validated = [validate_session(*session) for session in sessions]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    records = []
    for session in validated:
        label = session['label']
        images = {}
        for key, filename in zip(('initial', 'intermediate', 'final'), session['frame_names'], strict=True):
            target = out / f'{label}-{key}.png'
            shutil.copyfile(session['episode'] / filename, target)
            images[key] = {'file': target.name, 'sha256': sha256(target), 'source_sha256': sha256(session['episode'] / filename)}
        records.append({**session['record'], 'images': images})
    pack = {'format': FORMAT, 'sessions': records,
            'claims': {'visualized_real_source_episode': True,
                       'independent_arena_replay': False,
                       'learned_policy_or_skill': False}}
    (out / 'review.json').write_text(json.dumps(pack, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    cards = []
    for rec in records:
        pictures = ''.join(f'<figure><img alt="{key}" src="{rec["images"][key]["file"]}"><figcaption>{key}</figcaption></figure>' for key in ('initial','intermediate','final'))
        cards.append(f'<section><h2>{html.escape(rec["label"])}</h2><p>status: {html.escape(str(rec["status"]))} · actions: {rec["accepted_actions"]} · source replay attested</p><div class="frames">{pictures}</div></section>')
    page = ('<!doctype html><html lang="ja"><meta charset="utf-8"><title>Drawing Sessions</title>'
            '<style>body{font:16px system-ui;margin:2rem;max-width:1100px}section{margin:2rem 0}.frames{display:flex;gap:1rem;flex-wrap:wrap}figure{margin:0;max-width:30%}img{width:100%;image-rendering:auto;border:1px solid #aaa}figcaption{text-align:center}small{color:#666}</style>'
            '<h1>Drawing Session Review Pack</h1><small>Recorded episode frames; not evidence of autonomous learning.</small>'
            + ''.join(cards) + '</html>')
    (out / 'index.html').write_text(page, encoding='utf-8')
    return pack


def main() -> int:
    parser = argparse.ArgumentParser(description='Review actual ImageProgram drawing episodes')
    parser.add_argument('--session', nargs=3, metavar=('LABEL', 'EPISODE', 'REPLAY_JSON'), action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    pack = create_review_pack([(label, Path(ep), Path(rep)) for label, ep, rep in args.session], args.out)
    print(json.dumps({'format': FORMAT, 'sessions': len(pack['sessions']), 'review': str(args.out / 'index.html')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
