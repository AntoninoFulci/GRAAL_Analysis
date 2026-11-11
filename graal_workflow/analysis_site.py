"""Export explicit campaigns into a portable static GitHub Pages report."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import quote
import zipfile

from .report_manifest import MANIFEST, file_record, read_manifest, report_files, revision


REPOSITORY = 'https://github.com/AntoninoFulci/GRAAL_Analysis'
ASSETS = Path(__file__).with_name('web_assets')
PLOTS = {'.pdf', '.png', '.jpg', '.jpeg'}


def _json(path: Path, fallback):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else fallback


def _category(path: str) -> str:
    if any(word in path for word in ('dalitz', 'massa', 'masse', 'residuo', 'reconstruction', 'coplanarity', 'missing_mass')):
        return 'Ricostruzione'
    if any(word in path for word in ('bdt_stage', 'stage1', 'feature', 'roc', 'training')):
        return 'BDT'
    if any(word in path for word in ('flux', 'calibrat', 'strip')):
        return 'Calibrazione e flusso'
    return 'Estrazione e controlli'


def _profile(path: str) -> str:
    return next((part.upper() for part in Path(path).parts if part in {'uv', 'vis'}), 'Comune')


def _thumbnail(source: Path, destination: Path) -> bool:
    if source.suffix.lower() != '.pdf':
        return False
    try:
        subprocess.run(['pdftoppm', '-f', '1', '-singlefile', '-scale-to', '1000', '-png',
                        str(source), str(destination.with_suffix(''))],
                       check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        destination.unlink(missing_ok=True)
        return False
    return destination.is_file()


def _campaign(campaign: Path, target: Path, *, historical: bool, thumbnails: bool) -> dict:
    if (campaign / MANIFEST).exists():
        record = read_manifest(campaign)
    elif historical:
        legacy = _json(campaign / 'pipeline_artifacts.json', {})
        record = {'schema_version': 1, 'campaign': campaign.name, 'status': 'historical',
                  'mode': 'unknown', 'completed_at': None,
                  'source_revision': legacy.get('source_revision', 'unknown'), 'source_dirty': None,
                  'files': [file_record(p, campaign) for p in report_files(campaign, historical=True)]}
    else:
        raise ValueError(f'completion manifest missing: {campaign}; use --historical for an explicitly uncertified archive')
    if not record['files']:
        raise ValueError(f'no reports to publish: {campaign}')
    identifier = campaign.name
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', identifier):
        raise ValueError(f'campaign directory needs a URL-safe name: {identifier}')
    destination = target / 'campaigns' / identifier
    destination.mkdir(parents=True)
    plots, downloads, seen = [], [], {}
    for entry in record['files']:
        source = campaign / entry['path']
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != entry['sha256']:
            raise ValueError(f'report changed during export: {source}')
        local = destination / 'files' / entry['path']
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(content)
        url = quote(local.relative_to(target).as_posix(), safe='/')
        if source.suffix.lower() not in PLOTS:
            downloads.append({**entry, 'url': url})
            continue
        profile = _profile(entry['path'])
        # Legacy campaigns contain identical PDFs in plots/ and beam_asymmetry/.
        key = (profile, entry['sha256'])
        if key in seen:
            seen[key]['aliases'].append(entry['path'])
            continue
        item = {**entry, 'url': url, 'profile': profile, 'category': _category(entry['path']),
                'title': source.stem.replace('_', ' '), 'aliases': [], 'preview': None}
        if source.suffix.lower() == '.pdf' and thumbnails:
            thumbnail = destination / f'preview-{len(plots):04d}.png'
            if _thumbnail(local, thumbnail):
                item['preview'] = quote(thumbnail.relative_to(target).as_posix(), safe='/')
        elif source.suffix.lower() != '.pdf':
            item['preview'] = url
        seen[key] = item
        plots.append(item)
    # Catch files added/removed while rendering, before any new site is published.
    if record['status'] == 'complete' and read_manifest(campaign) != record:
        raise ValueError(f'completion manifest changed during export: {campaign}')
    (destination / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    metadata = destination / 'files/metadata'
    configuration = _json(metadata / 'effective_configuration.json', None)
    warnings = _json(metadata / 'stage_warnings.json', [])
    if not isinstance(warnings, list):
        raise ValueError('stage warnings must be a list')
    if record['status'] == 'historical':
        warnings.insert(0, 'Archivio storico: completamento e configurazione non certificati dal nuovo manifesto.')
    return {**{k: v for k, v in record.items() if k != 'files'}, 'id': identifier,
            'plots': plots, 'downloads': downloads, 'configuration': configuration,
            'warnings': warnings, 'manifest_url': f'campaigns/{identifier}/manifest.json'}


def build_site(campaigns, output: Path, *, repo_root: Path, historical: bool = False,
               thumbnails: bool = True) -> dict:
    """Build in staging and publish only into a new output directory."""
    output, repo_root = Path(output).resolve(), Path(repo_root).resolve()
    campaigns = [Path(path).resolve() for path in campaigns]
    if not campaigns or len({p.name for p in campaigns}) != len(campaigns):
        raise ValueError('provide distinct campaign directory names')
    if output.exists():
        raise ValueError(f'output already exists; choose a new build directory: {output}')
    for source in [*campaigns, repo_root / 'wiki', ASSETS.resolve()]:
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError(f'output overlaps input: {source}')
    if any(not p.is_dir() for p in campaigns):
        raise ValueError('campaign directory missing')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.analysis-site-', dir=output.parent) as temporary:
        target = Path(temporary) / 'site'
        target.mkdir()
        reports = [_campaign(p, target, historical=historical, thumbnails=thumbnails) for p in campaigns]
        reports.sort(key=lambda r: datetime.fromisoformat(r['completed_at']) if r['completed_at'] else
                     datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        production = [r for r in reports if r['mode'] == 'production' and r['status'] == 'complete']
        docs = []
        for path in sorted((repo_root / 'wiki').glob('*.md')):
            if path.name.startswith('_'):
                continue
            text = path.read_text(encoding='utf-8')
            dest = target / 'docs' / path.name
            dest.parent.mkdir(exist_ok=True)
            dest.write_text(text, encoding='utf-8')
            docs.append({'title': text.splitlines()[0].lstrip('# '),
                         'url': f'{REPOSITORY}/blob/main/wiki/{quote(path.name)}',
                         'download': f'docs/{quote(path.name)}'})
        data = {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
                'repository': REPOSITORY, 'documentation_revision': revision(repo_root),
                'latest': production[0]['id'] if production else None, 'campaigns': reports, 'docs': docs}
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
        (target / 'index.html').write_text((ASSETS / 'index.html').read_text().replace('REPORT_DATA', payload), encoding='utf-8')
        shutil.copytree(ASSETS, target / 'assets', ignore=shutil.ignore_patterns('index.html'))
        (target / 'site.json').write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
        (target / '.nojekyll').touch()
        from .site_bundle import MAX_SITE_BYTES, validate_site
        if sum(path.stat().st_size for path in target.rglob('*') if path.is_file()) > MAX_SITE_BYTES:
            raise ValueError('site exceeds 900 MB; include fewer historical campaigns')
        validate_site(target)
        target.rename(output)
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaigns', nargs='+', type=Path, help='Explicit completed campaigns; repeat for history')
    parser.add_argument('--output', required=True, type=Path, help='New directory under results_test/<campaign>')
    parser.add_argument('--repo-root', type=Path, default=Path.cwd())
    parser.add_argument('--historical', action='store_true', help='Include uncertified historical campaigns, clearly labelled')
    parser.add_argument('--no-thumbnails', action='store_true')
    parser.add_argument('--zip', action='store_true', help='Also create sibling graal-report.zip for GitHub Pages')
    args = parser.parse_args(argv)
    try:
        archive = args.output.parent / 'graal-report.zip'
        if args.zip and archive.exists():
            raise ValueError(f'archive already exists: {archive}')
        data = build_site(args.campaigns, args.output, repo_root=args.repo_root,
                          historical=args.historical, thumbnails=not args.no_thumbnails)
        if args.zip:
            with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
                for path in sorted(args.output.rglob('*')):
                    if path.is_file():
                        bundle.write(path, path.relative_to(args.output).as_posix())
        print(f'Site: {args.output.resolve() / "index.html"} ({len(data["campaigns"])} campaigns)')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
