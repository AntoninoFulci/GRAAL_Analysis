"""Group campaign reports without rewriting scientific ROOT outputs or caches."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .models import PipelineError


def organize_campaign_reports(campaign: Path) -> None:
    """Relocate generated reports, recording byte identities and period links.

    ROOT-producing stages share their native output directory with reports.
    Publication separates those reports only after all consumers have finished.
    Reusable artifacts and original input identities remain untouched.
    """
    campaign = Path(campaign)
    moves = []
    omitted = []
    for source in sorted((campaign / 'root').rglob('*')):
        if not source.is_file() or source.suffix not in {'.pdf', '.json', '.log'}:
            continue
        if source.name == 'figure4_experimental.pdf':
            omitted.append((source, source.read_bytes()))
            continue
        relative = source.relative_to(campaign / 'root')
        if source.suffix == '.pdf':
            # Extraction reports sit next to ROOTs; published plots omit that level.
            parts = tuple(part for part in relative.parts if part != 'beam_asymmetry')
            target = campaign / 'plots' / Path(*parts)
        else:
            target = campaign / 'metadata' / relative
        content = source.read_bytes()
        published = content
        if source.name == 'index.json' and source.parent.name == 'periods':
            index = json.loads(content)
            for row in index.get('periods', []):
                if 'root' in row:
                    scientific = source.parent / row['root']
                    row['root'] = os.path.relpath(scientific, target.parent)
            published = (json.dumps(index, indent=2, allow_nan=False) + '\n').encode()
        moves.append((source, target, content, published))
    for source in sorted((campaign / 'plots').rglob('*.root')):
        target = campaign / 'root' / source.relative_to(campaign / 'plots')
        content = source.read_bytes()
        moves.append((source, target, content, content))
    if not moves and not omitted:
        return
    # Check every collision before changing any existing file. Only generated
    # histogram diagnostics may replace an earlier plot regeneration's ROOTs.
    previous = {}
    for source, target, content, published in moves:
        old = target.read_bytes() if target.exists() else None
        if old is not None and old != published and source.suffix != '.root':
            raise PipelineError(f'conflicting campaign report: {source} -> {target}')
        previous[target] = old
    manifest = campaign / 'metadata/output_layout.json'
    inventory = json.loads(manifest.read_text()) if manifest.exists() else {'schema_version': 1, 'relocations': []}
    for source, target, content, published in moves:
        record = dict(source=str(source.relative_to(campaign)),
                      destination=str(target.relative_to(campaign)),
                      sha256=hashlib.sha256(content).hexdigest())
        if published != content:
            record['published_sha256'] = hashlib.sha256(published).hexdigest()
        if previous[target] is not None and previous[target] != published:
            record['replaced_sha256'] = hashlib.sha256(previous[target]).hexdigest()
        inventory['relocations'].append(record)
    if omitted:
        inventory.setdefault('omitted_duplicates', []).extend(
            dict(source=str(source.relative_to(campaign)), sha256=hashlib.sha256(content).hexdigest())
            for source, content in omitted)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_suffix('.json.tmp')
    applied = []
    removed = []
    try:
        temporary.write_text(json.dumps(inventory, indent=2) + '\n', encoding='utf-8')
        for source, target, content, published in moves:
            target.parent.mkdir(parents=True, exist_ok=True)
            applied.append((source, target, content))
            if published != content:
                target.write_bytes(published)
                source.unlink()
            elif source.suffix == '.root':
                source.replace(target)
            elif target.exists():
                source.unlink()  # Identical copy already published by the plot stage.
            else:
                source.rename(target)
        for source, content in omitted:
            removed.append((source, content))
            source.unlink()
        temporary.replace(manifest)
    except BaseException:
        for source, content in reversed(removed):
            source.write_bytes(content)
        for source, target, content in reversed(applied):
            source.write_bytes(content)
            if previous[target] is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(previous[target])
        raise
    finally:
        temporary.unlink(missing_ok=True)
