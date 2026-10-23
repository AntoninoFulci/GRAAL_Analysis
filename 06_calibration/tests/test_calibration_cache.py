"""Small actual ROOT producer and content-cache boundary regressions."""
from argparse import Namespace
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from calibration import calibration_cache as cache
from calibration.tests.test_build_strip_energy_flux import make_complete_fixture, _calibration_args, SCRIPT


def native_builder(args):
    # A separate interpreter matches the workflow driver boundary.
    argv = [sys.executable, '-B', str(SCRIPT)]
    for key, value in vars(args).items():
        if key in ('cache_root', 'cache_scope') or value is None:
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            argv.extend(['--' + key.replace('_', '-'), str(item)])
    result = subprocess.run(argv, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.returncode


def args_for(tmp_path):
    pre, flux, manifest, _ = make_complete_fixture(tmp_path)
    args = Namespace(**vars(_calibration_args(pre, flux, manifest, tmp_path / 'campaign-a/common/flux_calibrated.root')))
    args.target = None
    args.cache_root = tmp_path / 'artifacts/06_calibration'
    args.cache_scope = 'production'  # fixture has no diagnostic provenance; all paths remain test-local
    return args


def receipt(args):
    return json.loads((args.output_dir / cache.RECEIPT_NAME).read_text())


def test_real_root_two_campaigns_and_relocation_reuse_original_qa(tmp_path):
    args = args_for(tmp_path)
    assert cache.run_cached_calibration(args, native_builder, driver=SCRIPT) == 0
    first = receipt(args)
    original_qa = (args.output_dir / cache.QA_NAME).read_bytes()
    original_root = (args.output_dir / cache.ROOT_NAME).read_bytes()
    relocated = tmp_path / 'relocated'
    shutil.copytree(args.preanalysis_dir, relocated / 'pre')
    shutil.copyfile(args.flux, relocated / 'flux.root')
    shutil.copyfile(args.manifest, relocated / 'manifest.csv')
    args.preanalysis_dir, args.flux, args.manifest = relocated / 'pre', relocated / 'flux.root', relocated / 'manifest.csv'
    args.output_dir = tmp_path / 'campaign-b/common'
    def forbidden(_):
        pytest.fail('identical relocated inputs rescanned ROOT')
    assert cache.run_cached_calibration(args, forbidden, driver=SCRIPT) == 0
    second = receipt(args)
    assert second['reused'] and second['key'] == first['key']
    assert second['producer_inputs'] == first['producer_inputs']
    assert second['resolved_inputs'] != first['resolved_inputs']
    assert (args.output_dir / cache.QA_NAME).read_bytes() == original_qa
    assert (args.output_dir / cache.ROOT_NAME).read_bytes() == original_root
    assert str(tmp_path / 'pre') in original_qa.decode()  # do not forge historical source labels
    # Independent fresh native calibration gives the same scientific arrays;
    # ROOT UUID/time bytes differ and are intentionally not a numerical oracle.
    uncached = Namespace(**{**vars(args), 'output_dir': tmp_path / 'fresh/common'})
    native_builder(uncached)
    import numpy as np
    import uproot
    with uproot.open(args.output_dir / cache.ROOT_NAME) as reused, uproot.open(uncached.output_dir / cache.ROOT_NAME) as fresh:
        assert reused.keys() == fresh.keys()
        for name in reused.keys():
            if getattr(reused[name], 'classname', '').startswith('TH1'):
                np.testing.assert_array_equal(reused[name].values(flow=True), fresh[name].values(flow=True))
                np.testing.assert_array_equal(reused[name].errors(flow=True), fresh[name].errors(flow=True))
                np.testing.assert_array_equal(reused[name].axis().edges(), fresh[name].axis().edges())


@pytest.mark.parametrize('change', ['manifest', 'flux', 'h80_bytes', 'cohort', 'threads', 'samples', 'binning', 'schema', 'implementation'])
def test_each_scientific_dependency_invalidates(tmp_path, monkeypatch, change):
    args = args_for(tmp_path)
    before = cache.calibration_signature(args, driver=SCRIPT)
    if change in ('manifest', 'flux'):
        path = args.manifest if change == 'manifest' else args.flux
        with path.open('ab') as stream:
            stream.write(b'\n')
    elif change == 'h80_bytes':
        with next(args.preanalysis_dir.glob('*.root')).open('ab') as stream:
            stream.write(b'changed')
    elif change == 'cohort':
        next(args.preanalysis_dir.glob('*.root')).unlink()
    elif change == 'threads':
        args.threads += 1
    elif change == 'samples':
        args.samples_per_run_strip += 1
    elif change == 'binning':
        args.binning = ['proof:1.0,1.1,1.5']
    elif change == 'schema':
        monkeypatch.setattr(cache, 'CACHE_SCHEMA', cache.CACHE_SCHEMA + 1)
    else:
        original = cache.implementation_identity
        monkeypatch.setattr(cache, 'implementation_identity', lambda driver: original(driver) + [{'source': 'change', 'sha256': 'f'*64}])
    assert cache.content_key(cache.calibration_signature(args, driver=SCRIPT)) != cache.content_key(before)


@pytest.mark.parametrize('name', [cache.ROOT_NAME, cache.QA_NAME])
def test_tampered_pair_rebuild_failure_preserves_campaign(tmp_path, name):
    args = args_for(tmp_path)
    assert cache.run_cached_calibration(args, native_builder, driver=SCRIPT) == 0
    first = receipt(args)
    preserved = {p.name: p.read_bytes() for p in args.output_dir.iterdir()}
    (Path(first['bundle']) / name).write_bytes(b'tampered')
    called = []
    def fail(staged):
        called.append(staged.output_dir)
        (staged.output_dir / cache.ROOT_NAME).write_bytes(b'partial')
        raise RuntimeError('injected writer error')
    with pytest.raises(RuntimeError, match='injected'):
        cache.run_cached_calibration(args, fail, driver=SCRIPT)
    assert called
    assert {p.name: p.read_bytes() for p in args.output_dir.iterdir()} == preserved
    assert cache.run_cached_calibration(args, native_builder, driver=SCRIPT) == 0
    assert not receipt(args)['reused']


def test_missing_qa_and_changed_options_do_not_reuse(tmp_path):
    args = args_for(tmp_path)
    cache.run_cached_calibration(args, native_builder, driver=SCRIPT)
    first = receipt(args)
    (Path(first['bundle']) / cache.QA_NAME).unlink()
    cache.run_cached_calibration(args, native_builder, driver=SCRIPT)
    assert not receipt(args)['reused']
    args.max_mad_gev += .001
    cache.run_cached_calibration(args, native_builder, driver=SCRIPT)
    assert receipt(args)['key'] != first['key']
    assert Path(first['bundle']).is_dir()


@pytest.mark.parametrize('change', ['source', 'input'])
def test_change_during_scan_rejected_without_publication(tmp_path, monkeypatch, change):
    args = args_for(tmp_path)
    original = cache.implementation_identity
    def build(staged):
        result = native_builder(staged)
        if change == 'source':
            monkeypatch.setattr(cache, 'implementation_identity', lambda driver: original(driver) + [{'source': 'mutated'}])
        else:
            args.manifest.write_text(args.manifest.read_text() + '\n')
        return result
    with pytest.raises(ValueError, match='changed during scan'):
        cache.run_cached_calibration(args, build, driver=SCRIPT)
    assert not args.output_dir.exists()
    assert not list(args.cache_root.glob('*/bundle.json'))


@pytest.mark.parametrize('marker', ['manifest', 'root'])
def test_diagnostic_markers_forbidden_in_production(tmp_path, marker):
    args = args_for(tmp_path)
    if marker == 'manifest':
        (args.preanalysis_dir / 'manifest.json').write_text('{"diagnostic_only": true}')
    else:
        import ROOT
        path = next(args.preanalysis_dir.glob('*.root'))
        f = ROOT.TFile.Open(str(path), 'UPDATE')
        ROOT.TNamed('sample_provenance', '{"diagnostic_only": true}').Write()
        f.Close()
    with pytest.raises(ValueError, match='diagnostic sample'):
        cache.calibration_signature(args, driver=SCRIPT)
    args.cache_scope = 'diagnostic'
    assert cache.calibration_signature(args, driver=SCRIPT)['scope'] == 'diagnostic'


def test_age_and_output_path_not_key_inputs_policy_not_calibration_dependency(tmp_path):
    import os
    args = args_for(tmp_path)
    signature = cache.calibration_signature(args, driver=SCRIPT)
    for p in args.preanalysis_dir.glob('*.root'):
        os.utime(p, (1, 1))
    args.output_dir = tmp_path / 'other-campaign/common'
    args.progress_every_events = 500
    assert cache.calibration_signature(args, driver=SCRIPT) == signature
    assert not any('quality' in key for key in signature)
    args.cache_scope = 'diagnostic'
    assert cache.calibration_signature(args, driver=SCRIPT) != signature


def test_nonzero_builder_does_not_publish_partial_bundle(tmp_path):
    args = args_for(tmp_path)
    def failed(staged):
        (staged.output_dir / cache.ROOT_NAME).write_bytes(b'partial')
        return 1
    with pytest.raises(RuntimeError, match='failed with exit 1'):
        cache.run_cached_calibration(args, failed, driver=SCRIPT)
    assert not args.output_dir.exists()
    assert not [p for p in args.cache_root.iterdir() if p.is_dir()]


def test_qa_cohort_mismatch_is_not_certified(tmp_path):
    args = args_for(tmp_path)
    def wrong_cohort(staged):
        native_builder(staged)
        qa_path = staged.output_dir / cache.QA_NAME
        qa = json.loads(qa_path.read_text())
        qa['inputs']['h80'] = qa['inputs']['h80'][:-1]
        qa_path.write_text(json.dumps(qa))
        return 0
    with pytest.raises(ValueError, match='cohort mismatch'):
        cache.run_cached_calibration(args, wrong_cohort, driver=SCRIPT)
    assert not args.output_dir.exists()
    assert not [p for p in args.cache_root.iterdir() if p.is_dir()]


def test_competing_campaigns_publish_once_under_key_lock(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    args = args_for(tmp_path)
    cache.calibration_signature(args, driver=SCRIPT)  # initialize PyROOT on main thread
    other = Namespace(**{**vars(args), 'output_dir': tmp_path / 'concurrent/common'})
    calls = []
    def build(staged):
        calls.append(staged.output_dir)
        return native_builder(staged)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(cache.run_cached_calibration, item, build, driver=SCRIPT) for item in (args, other)]
        assert [f.result() for f in futures] == [0, 0]
    assert len(calls) == 1
    assert sorted([receipt(args)['reused'], receipt(other)['reused']]) == [False, True]
    assert receipt(args)['key'] == receipt(other)['key']


def test_failed_campaign_copy_restores_valid_pair(tmp_path, monkeypatch):
    args = args_for(tmp_path)
    cache.run_cached_calibration(args, native_builder, driver=SCRIPT)
    preserved = {p.name: p.read_bytes() for p in args.output_dir.iterdir()}
    original = cache.shutil.copyfile
    def failed(source, target, **kwargs):
        if Path(source).name == cache.QA_NAME:
            raise OSError('injected pair copy failure')
        return original(source, target, **kwargs)
    monkeypatch.setattr(cache.shutil, 'copyfile', failed)
    with pytest.raises(OSError, match='pair copy failure'):
        cache.run_cached_calibration(args, native_builder, driver=SCRIPT)
    assert {p.name: p.read_bytes() for p in args.output_dir.iterdir()} == preserved


def test_installed_source_and_driver_relocation_preserve_content_identity(tmp_path, monkeypatch):
    import calibration
    import graal_common
    before = cache.implementation_identity(SCRIPT)
    for name, package in (('calibration', calibration), ('graal_common', graal_common)):
        original = Path(package.__file__).resolve().parent
        moved = tmp_path / 'relocated-installation' / name
        shutil.copytree(original, moved, ignore=shutil.ignore_patterns('__pycache__', 'tests'))
        monkeypatch.setattr(package, '__file__', str(moved / '__init__.py'))
    driver = tmp_path / 'relocated-checkout/06_calibration/build_strip_energy_flux.py'
    driver.parent.mkdir(parents=True)
    shutil.copyfile(SCRIPT, driver)
    assert cache.implementation_identity(driver) == before


@pytest.mark.parametrize('kind', ['file', 'directory'])
def test_external_cohort_links_reuse_after_original_paths_disappear(tmp_path, kind):
    args = args_for(tmp_path)
    farm = tmp_path / 'farm'
    args.preanalysis_dir.rename(farm)
    if kind == 'directory':
        args.preanalysis_dir.symlink_to(farm, target_is_directory=True)
    else:
        args.preanalysis_dir.mkdir()
        for path in farm.glob('*.root'):
            (args.preanalysis_dir / path.name).symlink_to(path)
    original_inputs = {str(p): p.read_bytes() for p in [*farm.glob('*.root'), args.flux, args.manifest]}
    cache.run_cached_calibration(args, native_builder, driver=SCRIPT)
    first = receipt(args)
    qa = (args.output_dir / cache.QA_NAME).read_bytes()
    root = (args.output_dir / cache.ROOT_NAME).read_bytes()
    record_path = Path(first['bundle']) / 'bundle.json'
    record = json.loads(record_path.read_text())
    assert [row['resolved_path'] for row in record['producer_h80']] == [str(p) for p in sorted(farm.glob('*.root'))]
    # The mapping must authenticate both logical labels and resolved QA sources.
    for field, value in [('path', 'renamed.root'), ('resolved_path', str(farm / 'wrong.root')),
                         ('sha256', '0' * 64), ('size', 0)]:
        changed = json.loads(json.dumps(record))
        changed['producer_h80'][0][field] = value
        record_path.write_text(json.dumps(changed))
        with pytest.raises(ValueError, match='cohort mismatch'):
            cache._validate_bundle(Path(first['bundle']), first['signature'])
    record_path.write_text(json.dumps(record))
    assert {str(p): p.read_bytes() for p in [*farm.glob('*.root'), args.flux, args.manifest]} == original_inputs
    moved = tmp_path / 'moved-farm'
    farm.rename(moved)  # Original QA paths and input symlinks are now unavailable.
    args.preanalysis_dir = moved
    args.output_dir = tmp_path / 'campaign-b/common'
    def forbidden(_):
        pytest.fail('relocated linked cohort was rescanned')
    cache.run_cached_calibration(args, forbidden, driver=SCRIPT)
    assert receipt(args)['reused'] and receipt(args)['key'] == first['key']
    assert (args.output_dir / cache.QA_NAME).read_bytes() == qa
    assert (args.output_dir / cache.ROOT_NAME).read_bytes() == root
    # Failure to republish a reused linked bundle cannot replace the campaign.
    preserved = {p.name: p.read_bytes() for p in args.output_dir.iterdir()}
    (Path(first['bundle']) / cache.QA_NAME).write_bytes(b'tampered')
    with pytest.raises(RuntimeError, match='failed with exit'):
        cache.run_cached_calibration(args, lambda _: 1, driver=SCRIPT)
    assert {p.name: p.read_bytes() for p in args.output_dir.iterdir()} == preserved
    assert {p.name: p.read_bytes() for p in moved.glob('*.root')} == {Path(p).name: b for p, b in original_inputs.items() if Path(p).parent == farm}


@pytest.mark.parametrize('destination', ['output_dir', 'cache_root'])
def test_cache_rejects_publication_over_individually_linked_inputs(tmp_path, destination):
    args = args_for(tmp_path)
    farm = tmp_path / 'farm'; farm.mkdir()
    original = next(args.preanalysis_dir.glob('*.root'))
    target = farm / original.name
    original.rename(target); original.symlink_to(target)
    before = target.read_bytes()
    setattr(args, destination, farm)
    with pytest.raises(ValueError, match='overlaps inputs'):
        cache.run_cached_calibration(args, lambda _: pytest.fail('builder called'), driver=SCRIPT)
    assert target.read_bytes() == before


def test_existing_bundle_without_source_mapping_remains_valid(tmp_path):
    args = args_for(tmp_path)
    cache.run_cached_calibration(args, native_builder, driver=SCRIPT)
    first = receipt(args)
    path = Path(first['bundle']) / 'bundle.json'
    record = json.loads(path.read_text())
    del record['producer_h80']
    path.write_text(json.dumps(record))
    cache.run_cached_calibration(args, lambda _: pytest.fail('legacy valid bundle rebuilt'), driver=SCRIPT)
    assert receipt(args)['reused']


@pytest.mark.parametrize('destination', ['output_dir', 'cache_root'])
def test_cache_preserves_input_directory_link_inside_publication_target(tmp_path, destination):
    args = args_for(tmp_path)
    target = tmp_path / 'publication'; target.mkdir()
    link = target / 'preanalysis'
    link.symlink_to(args.preanalysis_dir, target_is_directory=True)
    args.preanalysis_dir = link
    setattr(args, destination, target)
    with pytest.raises(ValueError, match='overlaps inputs'):
        cache.run_cached_calibration(args, lambda _: pytest.fail('builder called'), driver=SCRIPT)
    assert link.is_symlink()
    assert len(list(link.glob('*.root'))) == 2
