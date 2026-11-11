"""Publish verified target CSV/configuration; keep plot data in results."""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil

from graal_common.io.filesystem import atomic_output_directory


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def publish_support(products, output):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_name('.'+output.name+'.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if output.is_dir() and not any(output.iterdir()):
            output.rmdir()
        for staging in output.parent.glob('.'+output.name+'.*'):
            if staging.is_dir():
                shutil.rmtree(staging)
        return _publish_support(products, output)


def _publish_support(products, output):
    products, output = Path(products).resolve(), Path(output).resolve()
    checksums = json.loads((products/'checksums.json').read_text())
    required = {'run_plots.npz', 'target_runs.csv', 'target_periods.csv',
                'metadata.json', 'geant4_candidates.json'}
    if not required <= set(checksums):
        raise ValueError('missing required product checksums')
    if any(Path(name).name != name for name in checksums):
        raise ValueError('invalid product filename')
    if any(_sha256(products/name) != value for name, value in checksums.items()):
        raise ValueError('product checksum mismatch')
    metadata = json.loads((products/'metadata.json').read_text())
    if any(row['coverage_status'] != 'complete' for row in metadata['periods'].values()):
        raise ValueError('cannot publish incomplete period coverage as final conditions')
    if output.exists():
        publication = json.loads((output/'publication.json').read_text())
        if (publication['source_checksums'] != checksums
                or (output/publication['source_products']).resolve() != products
                or any(_sha256(output/name) != value for name, value in publication['output_checksums'].items())):
            raise ValueError('existing publication differs from verified products')
        return output
    archive = os.path.relpath(products/'run_plots.npz', output)
    with atomic_output_directory(output, overwrite=False) as out:
        for name in ('target_runs.csv', 'target_periods.csv'):
            with (products/name).open() as stream:
                rows = list(csv.DictReader(stream))
            for row in rows:
                row['plot_archive'] = archive
            with (out/name).open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        candidates = json.loads((products/'geant4_candidates.json').read_text())
        for period in candidates['periods'].values():
            period['photon_beam_proxy']['profile_file'] = archive
        (out/'geant4_candidates.json').write_text(json.dumps(candidates, indent=2, allow_nan=False)+'\n')
        publication = dict(schema=1, source_products=os.path.relpath(products, output),
                           source_checksums=checksums,
                           metadata_file=os.path.relpath(products/'metadata.json', output),
                           catalog=metadata['catalog'], code_hashes=metadata['code_hashes'],
                           output_checksums={p.name: _sha256(p) for p in out.iterdir() if p.is_file()},
                           note='Relative paths resolve from this configuration directory. Geometry proposals remain explicit approximations; no GEANT4 source modified.')
        (out/'publication.json').write_text(json.dumps(publication, indent=2, allow_nan=False)+'\n')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('products', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(publish_support(args.products, args.output))


if __name__ == '__main__':
    main()
