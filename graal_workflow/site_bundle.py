"""Validate and unpack a report release without scientific runtime dependencies."""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import stat
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile


MAX_SITE_BYTES = 900_000_000  # Leave headroom below the GitHub Pages 1 GB limit.


class _EmbeddedIndex(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.indices = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and attrs.get('id') == 'report-data':
            self.active = True
            self.indices.append('')

    def handle_data(self, data):
        if self.active:
            self.indices[-1] += data

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False


def _relative(name: str) -> Path:
    path = PurePosixPath(name)
    if (not name or not path.parts or path.is_absolute() or '..' in path.parts or '\\' in name
            or any(ord(c) < 32 for c in name) or ':' in path.parts[0]):
        raise ValueError(f'unsafe bundle path: {name!r}')
    return Path(*path.parts)


def _url_file(root: Path, url: str) -> Path:
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise ValueError(f'expected local asset URL: {url}')
    path = root / _relative(unquote(parts.path))
    if not path.is_file():
        raise ValueError(f'missing site asset: {url}')
    return path


def validate_site(root: Path) -> None:
    for name in ('index.html', 'assets/site.js', 'assets/site.css'):
        _url_file(root, name)
    data = json.loads((root / 'site.json').read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not data.get('campaigns'):
        raise ValueError('invalid site index')
    embedded = _EmbeddedIndex()
    embedded.feed((root / 'index.html').read_text(encoding='utf-8'))
    if len(embedded.indices) != 1 or json.loads(embedded.indices[0]) != data:
        raise ValueError('browser index differs from verified site index')
    identifiers = set()
    for campaign in data['campaigns']:
        if campaign['id'] in identifiers:
            raise ValueError('duplicate campaign')
        identifiers.add(campaign['id'])
        manifest_path = _url_file(root, campaign['manifest_url'])
        record = json.loads(manifest_path.read_text(encoding='utf-8'))
        if record.get('schema_version') != 1 or record.get('status') not in {'complete', 'historical'}:
            raise ValueError('invalid campaign manifest')
        for key in ('status', 'mode', 'completed_at', 'source_revision', 'source_dirty'):
            if record[key] != campaign[key]:
                raise ValueError('campaign provenance differs from manifest')
        files = {entry['path']: entry for entry in record['files']}
        if len(files) != len(record['files']):
            raise ValueError('duplicate campaign manifest paths')
        for entry in record['files']:
            path = manifest_path.parent / 'files' / _relative(entry['path'])
            content = path.read_bytes()
            if len(content) != entry['size'] or hashlib.sha256(content).hexdigest() != entry['sha256']:
                raise ValueError(f'corrupt campaign asset: {entry["path"]}')
        for item in [*campaign['plots'], *campaign['downloads']]:
            entry = files.get(item['path'])
            if (entry is None or any(item[key] != entry[key] for key in ('path', 'sha256', 'size'))
                    or _url_file(root, item['url']) != manifest_path.parent / 'files' / _relative(entry['path'])):
                raise ValueError('asset does not belong to the displayed campaign')
            for alias in item.get('aliases', []):
                if alias not in files or files[alias]['sha256'] != entry['sha256']:
                    raise ValueError('alias differs from campaign asset')
            if item.get('preview'):
                preview = _url_file(root, item['preview'])
                if not preview.is_relative_to(manifest_path.parent):
                    raise ValueError('preview belongs to another campaign')
    if data['latest'] is not None and not any(c['id'] == data['latest'] and c['status'] == 'complete'
                                            and c['mode'] == 'production' for c in data['campaigns']):
        raise ValueError('latest must identify a completed production campaign')
    for document in data['docs']:
        _url_file(root, document['download'])


def unpack_site(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    if destination.exists():
        raise ValueError('deployment directory already exists')
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)) or sum(m.file_size for m in members) > MAX_SITE_BYTES:
            raise ValueError('duplicate assets or site exceeds 900 MB')
        normalized = set()
        for member in members:
            path = _relative(member.filename)
            if path in normalized:
                raise ValueError('aliased ZIP paths')
            normalized.add(path)
            mode = member.external_attr >> 16
            if stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ValueError('links and special files are not allowed')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.pages-', dir=destination.parent) as temporary:
            staged = Path(temporary) / 'site'
            staged.mkdir()
            for member in members:
                path = staged / _relative(member.filename)
                if member.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(bundle.read(member))
            validate_site(staged)
            staged.rename(destination)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        unpack_site(args.archive, args.output)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        parser.exit(1, f'ERROR: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
