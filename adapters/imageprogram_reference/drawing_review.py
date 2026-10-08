"""Read-only, hash-checked drawing session review packs for ImageProgram episodes.

Arena does not interpret the painter's program or verify physics itself. Replay must
be attested by ImageProgram's own runner before the session can be packaged.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import stat
from pathlib import Path

FORMAT = 'arena-drawing-review-v0'
MAX_PUBLIC_FRAME_BYTES = 64 * 1024 * 1024
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
    if relative.as_posix() != name:
        raise DrawingReviewError('non-canonical public artifact path')
    if (relative.is_absolute() or '..' in relative.parts or '.' in relative.parts
            or any(part.startswith('.') for part in relative.parts)):
        raise DrawingReviewError('unsafe public artifact path')
    if name not in PUBLIC_TOP and not (len(relative.parts) == 2
                                        and relative.parts[0] == 'frames'
                                        and re.fullmatch(r'\d{6}\.png', relative.name)):
        raise DrawingReviewError('non-public or unrecognized artifact path')
    # An in-tree 'frames' symlink to 'private/frames' resolves inside root.
    # Check *every* prefix, not only the leaf or final resolved location.
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise DrawingReviewError(f'symlinked public artifact component: {name}')
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise DrawingReviewError(f'missing or escaping artifact: {name}')
    # A hard link to any hidden file has the same inode and cannot be detected
    # by is_symlink(). Fail closed on multiply linked public inputs.
    if path.stat().st_nlink != 1:
        raise DrawingReviewError(f'hard-linked public artifact: {name}')
    return path



def verified_frame_snapshot(root: Path, name: str, expected_sha256: str) -> bytes:
    """Snapshot *verified* public frame bytes before exposing them in the Review Pack.

    The prior episode check and replay may take a long time. Never copy a
    pathname re-opened after replay: another process could substitute a
    symlink to a private artifact, including on the parent frames directory.
    Open every component relative to an already opened directory fd using
    O_NOFOLLOW. Verify inode type and hard-link count, then the actual bytes
    read from that stable fd *before* writing public output.
    """
    # Enforce the same public-only filename allowlist as the manifest validator.
    # This check alone is NOT relied on for race safety.
    safe_public_path(root, name)
    relative = Path(name)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    directory_fd = None
    source_fd = None
    try:
        directory_fd = os.open(root, directory_flags)
        for component in relative.parts[:-1]:
            child_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = child_fd
        source_fd = os.open(relative.name, file_flags, dir_fd=directory_fd)
        info = os.fstat(source_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise DrawingReviewError(f'unsafe public frame inode: {name}')
        if info.st_size > MAX_PUBLIC_FRAME_BYTES:
            raise DrawingReviewError(f'public frame too large: {name}')
        with os.fdopen(source_fd, 'rb') as source:
            source_fd = None  # fd is now owned by the file object
            data = source.read(MAX_PUBLIC_FRAME_BYTES + 1)
    except OSError as exc:
        raise DrawingReviewError(f'cannot safely open public frame: {name}') from exc
    finally:
        if source_fd is not None:
            os.close(source_fd)
        if directory_fd is not None:
            os.close(directory_fd)

    if len(data) > MAX_PUBLIC_FRAME_BYTES:
        raise DrawingReviewError(f'public frame too large: {name}')
    actual = 'sha256:' + hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise DrawingReviewError(f'public frame changed since validation: {name}')
    return data


def source_replay(episode: Path) -> dict:
    """Re-run exactly this episode with the version-pinned ImageProgram engine."""
    try:
        from imageprogram.experiments.runner import replay
    except ImportError as exc:
        raise DrawingReviewError(
            'ImageProgram must be installed to verify source replay'
        ) from exc
    result = replay(episode)
    if not isinstance(result, dict):
        raise DrawingReviewError('source replay returned an invalid report')
    return result


def canonical_json_hash(path: Path, *, omit_request_id: bool = False) -> str:
    """Semantic identity without cosmetic formatting or administrative run IDs."""
    payload = read_json(path)
    if omit_request_id:
        payload = {key: value for key, value in payload.items() if key != 'request_id'}
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')
    return 'sha256:' + hashlib.sha256(canonical).hexdigest()



def canonical_jsonl_hash(path: Path) -> str:
    """Semantic identity of ordered JSONL records, not their byte formatting.

    Boundaries are preserved with a newline after each canonical JSON object;
    string newlines are escaped by JSON encoding. The original file digest is
    retained separately for manifest integrity and artifact provenance.
    """
    digest = hashlib.sha256()
    try:
        with path.open(encoding='utf-8') as source:
            for line_number, line in enumerate(source, start=1):
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError('expected JSON object')
                    canonical = json.dumps(
                        record, ensure_ascii=False, sort_keys=True,
                        separators=(',', ':'), allow_nan=False,
                    ).encode('utf-8')
                except (ValueError, UnicodeError) as exc:
                    raise DrawingReviewError(
                        f'invalid transition JSONL record at line {line_number}'
                    ) from exc
                digest.update(canonical)
                digest.update(b'\n')
    except OSError as exc:
        raise DrawingReviewError('cannot read transition JSONL') from exc
    return 'sha256:' + digest.hexdigest()


def validate_session(label: str, episode: Path, replay_report: Path) -> dict:
    if not LABEL.fullmatch(label):
        raise DrawingReviewError('label must be a short ASCII slug')
    episode = Path(episode)
    if episode.is_symlink():
        raise DrawingReviewError('episode root must not be a symlink')
    episode = episode.resolve()
    if (episode / 'manifest.json').is_symlink():
        raise DrawingReviewError('manifest must not be a symlink')
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
    terminal_frame = f'frames/{n:06d}.png'
    frame_names = ['frames/000000.png', f'frames/{middle:06d}.png', 'final.png']
    if any(name not in public for name in (*frame_names, terminal_frame)):
        raise DrawingReviewError('initial/mid/terminal/final frames missing from manifest')
    if files['final.png'] != files[terminal_frame]:
        raise DrawingReviewError('final.png does not match terminal numbered frame')
    if result.get('status') not in {'program_exhausted', 'budget_exhausted', 'failed'}:
        raise DrawingReviewError('missing or invalid terminal execution status')
    if result.get('request_id') != request.get('request_id'):
        raise DrawingReviewError('request/result ID mismatch')
    if not isinstance(result.get('versions'), dict) or not result['versions']:
        raise DrawingReviewError('runtime versions missing')
    if not isinstance(result.get('initial_state_hash'), str) or not result['initial_state_hash']:
        raise DrawingReviewError('initial state identity missing')
    if not isinstance(result.get('final_state_hash'), str) or not result['final_state_hash']:
        raise DrawingReviewError('final state identity missing')
    if Path(replay_report).is_symlink():
        raise DrawingReviewError('replay attestation must not be a symlink')
    replay = read_json(Path(replay_report))
    if replay.get('verified') is not True:
        raise DrawingReviewError('ImageProgram replay is not verified')
    if (replay.get('transitions') != n
            or replay.get('final_state_hash') != result.get('final_state_hash')
            or replay.get('status') != result.get('status')
            or replay.get('goal_evaluated') is not False):
        raise DrawingReviewError('replay attestation does not match this episode')
    # The supplied JSON alone cannot bind an episode's input files. Replay the
    # selected episode again using ImageProgram's real execution engine. Its
    # replay() checks request, program, state transitions, frames and versions.
    fresh = source_replay(episode)
    if (fresh.get('verified') is not True
            or fresh.get('transitions') != n
            or fresh.get('final_state_hash') != result['final_state_hash']
            or fresh.get('status') != result['status']
            or fresh.get('goal_evaluated') is not False):
        raise DrawingReviewError('fresh source replay disagrees with this episode')
    # A replay report is only an attestation from ImageProgram. Do not claim
    # that an independent Arena physics replay has taken place.
    return {
        'label': label, 'episode': episode, 'replay_report': Path(replay_report).resolve(),
        'frame_names': frame_names,
        'frame_hashes': [files[name] for name in frame_names],
        'record': {
            'label': label, 'source_format': manifest['format'],
            'request_id': result['request_id'], 'seed': request.get('seed'),
            'body': request.get('body'), 'goal': request.get('goal'),
            'initial_state_hash': result['initial_state_hash'],
            'final_state_hash': result['final_state_hash'],
            'source_request_sha256': files['request.json'],
            'source_program_sha256': files['program.json'],
            'source_request_semantic_hash': canonical_json_hash(
                episode / 'request.json', omit_request_id=True
            ),
            'source_program_semantic_hash': canonical_json_hash(episode / 'program.json'),
            'source_transition_sha256': files['transitions.jsonl'],
            'source_transition_semantic_hash': canonical_jsonl_hash(
                episode / 'transitions.jsonl'
            ),
            'source_initial_frame_sha256': files['frames/000000.png'],
            'fresh_source_replay_verified': True,
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
    if len({item['episode'] for item in validated}) != len(validated):
        raise DrawingReviewError('duplicate episode path across session labels')
    # Identical deterministic source runs are not independent comparisons, even
    # when copied to different folders or re-run with new wall-time metadata.
    identities = [
        (item['record']['source_request_semantic_hash'],
         item['record']['source_program_semantic_hash'],
         item['record']['initial_state_hash'],
         item['record']['final_state_hash'],
         item['record']['source_transition_semantic_hash'],
         item['record']['source_initial_frame_sha256'])
        for item in validated
    ]
    if len(set(identities)) != len(identities):
        raise DrawingReviewError('duplicate episode identity across sessions')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    records = []
    for session in validated:
        label = session['label']
        images = {}
        for key, filename, expected in zip(
            ('initial', 'intermediate', 'final'),
            session['frame_names'], session['frame_hashes'], strict=True
        ):
            # Reopen safely by file descriptors, then validate the bytes actually
            # read against the original manifest *before* any public write.
            snapshot = verified_frame_snapshot(session['episode'], filename, expected)
            target = out / f'{label}-{key}.png'
            with target.open('xb') as destination:
                destination.write(snapshot)
            images[key] = {
                'file': target.name,
                'sha256': expected,
                'source_sha256': expected,
            }
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
