import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from calibration.common_inputs import load_common_inputs, resolve_reference, common_counts_path
from calibration.calibration_qa import sha256_file

ROOT = Path(__file__).resolve().parents[2]


def test_canonical_common_inputs_validate_without_loading_optional_local_counts(tmp_path):
    common = load_common_inputs(ROOT)
    assert common['inputs']['run_catalog'] == ROOT / 'config/run_manifest.csv'
    assert common['inputs']['run_quality'] == ROOT / 'config/run_quality_exclusions.json'
    assert common['inputs']['raw_flux'] == ROOT / 'data/00_external/flux.root'
    with pytest.raises(ValueError, match='diagnostic'):
        common_counts_path(common, 'local_1998uv_1999vis', production=True)


@pytest.mark.parametrize('path', ['/absolute', '../escape', 'sub/../../escape'])
def test_reference_cannot_escape_declared_root(tmp_path, path):
    with pytest.raises(ValueError):
        resolve_reference(dict(root='checkout', path=path), checkout=tmp_path, cache=tmp_path)


def test_common_identity_mismatch_and_duplicate_keys_rejected(tmp_path):
    data = json.loads((ROOT / 'config/common_inputs.json').read_text())
    data['inputs']['raw_flux']['sha256'] = '0'*64
    path = tmp_path / 'common.json'; path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='identity mismatch'):
        load_common_inputs(ROOT, path=path)
    path.write_text('{"schema_version":1,"schema_version":1}')
    with pytest.raises(ValueError, match='duplicate'):
        load_common_inputs(ROOT, path=path)


def test_scanner_never_overwrites_manual_catalog(tmp_path):
    catalog = tmp_path / 'catalog.csv'
    shutil.copyfile(ROOT / 'config/run_manifest.csv', catalog)
    digest = sha256_file(catalog)
    result = subprocess.run([sys.executable, '-B', str(ROOT / '06_calibration/build_run_manifest.py'),
        '--input-dir', str(tmp_path), '--output', str(catalog)], capture_output=True, text=True)
    assert result.returncode == 1 and 'new candidate' in result.stderr
    assert sha256_file(catalog) == digest


@pytest.mark.parametrize('kind', ['file', 'directory'])
def test_external_data_links_are_authenticated_for_flux_and_optional_counts(tmp_path, kind):
    from calibration.common_inputs import verified_reference
    checkout, farm = tmp_path / 'checkout', tmp_path / 'farm'
    farm.mkdir()
    (checkout / 'data').mkdir(parents=True)
    target = farm / 'counts.json'
    target.write_text('{"schema_version": 1, "diagnostic_only": true}')
    if kind == 'file':
        (checkout / 'data/counts.json').symlink_to(target)
        relative = 'data/counts.json'
    else:
        (checkout / 'data/farm').symlink_to(farm, target_is_directory=True)
        relative = 'data/farm/counts.json'
    ref = dict(root='checkout', path=relative, sha256=sha256_file(target), diagnostic_only=True)
    cache = checkout / 'results/_cache'
    original = target.read_bytes()
    assert verified_reference(ref, checkout=checkout, cache=cache) == target
    common = dict(checkout=checkout, cache=cache, bundles={'inclusive_counts': {'farm': ref}})
    assert common_counts_path(common, 'farm') == target
    with pytest.raises(ValueError, match='diagnostic'):
        common_counts_path(common, 'farm', production=True)
    with pytest.raises(ValueError, match='identity mismatch'):
        verified_reference({**ref, 'sha256': '0' * 64}, checkout=checkout, cache=cache)
    assert target.read_bytes() == original


@pytest.mark.parametrize('root,relative', [('cache', 'linked'), ('checkout', 'config/linked')])
def test_external_links_do_not_relax_cache_or_configuration_containment(tmp_path, root, relative):
    checkout, cache = tmp_path / 'checkout', tmp_path / 'cache'
    external = tmp_path / 'external'; external.mkdir()
    base = cache if root == 'cache' else checkout
    link = base / relative; link.parent.mkdir(parents=True)
    link.symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match='escapes'):
        resolve_reference(dict(root=root, path=relative + '/source'), checkout=checkout, cache=cache)
