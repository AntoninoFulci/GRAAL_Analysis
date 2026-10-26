"""Wheel execution must use installed Python and an explicit native checkout."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

import pytest

from graal_workflow import artifact_manifest, execution, models, paths, planning, resources


REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def installed_workflow(tmp_path_factory):
    scratch = tmp_path_factory.mktemp("workflow-wheel")
    source = scratch / "source"
    source.mkdir()
    shutil.copy2(REPO / "pyproject.toml", source / "pyproject.toml")
    shutil.copy2(REPO / "setup.cfg", source / "setup.cfg")
    manifest = tomllib.loads((source / "pyproject.toml").read_text())
    for relative in manifest["tool"]["setuptools"]["package-dir"].values():
        for original in (REPO / relative).rglob("*.py"):
            if "__pycache__" in original.parts:
                continue
            destination = source / original.relative_to(REPO)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, destination)
    for package, patterns in manifest["tool"]["setuptools"].get("package-data", {}).items():
        relative = manifest["tool"]["setuptools"]["package-dir"][package]
        for pattern in patterns:
            for original in (REPO / relative).glob(pattern):
                destination = source / original.relative_to(REPO)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, destination)
    wheels = scratch / "wheels"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    commands = [
        [sys.executable, "-B", "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-cache-dir", "--wheel-dir", str(wheels), str(source)],
    ]
    build = subprocess.run(commands[0], cwd=scratch, env=env, capture_output=True, text=True)
    (scratch / "build.log").write_text(build.stdout + build.stderr)
    assert build.returncode == 0, build.stdout + build.stderr
    target = scratch / "site-packages"
    commands.append([sys.executable, "-B", "-m", "pip", "install", "--no-deps", "--no-compile", "--no-cache-dir", "--target", str(target), str(next(wheels.glob("*.whl")))])
    install = subprocess.run(commands[-1], cwd=scratch, env=env, capture_output=True, text=True)
    (scratch / "install.log").write_text(install.stdout + install.stderr)
    assert install.returncode == 0, install.stdout + install.stderr
    commands.append([sys.executable, "-B", "-c",
                     "import sys; from setuptools.build_meta import build_sdist; build_sdist(sys.argv[1])",
                     str(scratch / "sdist")])
    sdist = subprocess.run(commands[-1], cwd=source, env=env, capture_output=True, text=True)
    (scratch / "sdist.log").write_text(sdist.stdout + sdist.stderr)
    assert sdist.returncode == 0, sdist.stdout + sdist.stderr
    import tarfile
    with tarfile.open(next((scratch / "sdist").glob("*.tar.gz"))) as archive:
        assert any(name.endswith("/setup.cfg") for name in archive.getnames())
        assert any(name.endswith("/graal_workflow/cli.py") for name in archive.getnames())
        assert any(name.endswith("/06_calibration/native/strip_energy_rdf.hxx") for name in archive.getnames())
    assert not (source / "build").exists()
    assert (source / "results_test/packaging/build").is_dir()
    (scratch / "commands.json").write_text(json.dumps(commands, indent=2))
    # Retain external runtime dependencies such as PyROOT, excluding this checkout.
    external = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if p and not Path(p).resolve().is_relative_to(REPO)]
    env["PYTHONPATH"] = os.pathsep.join([str(target), *external])
    return scratch, target, env


def _installed(installed_workflow, code, *arguments):
    scratch, target, env = installed_workflow
    bootstrap = """
import sys
from pathlib import Path
sys.meta_path[:] = [finder for finder in sys.meta_path if not getattr(finder, '__module__', '').startswith('__editable__')]
import graal_workflow
assert Path(graal_workflow.__file__).resolve().is_relative_to(Path(sys.argv[1])), graal_workflow.__file__
"""
    result = subprocess.run([sys.executable, "-B", "-c", bootstrap + code, str(target), str(REPO), *map(str, arguments)],
                            cwd="/private/tmp" if Path("/private/tmp").is_dir() else "/tmp",
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_wheel_plans_equal_checkout_and_root_is_explicit(installed_workflow):
    result = _installed(installed_workflow, """
import dataclasses, json
from graal_workflow import cli, paths, planning, models, resources
try:
    paths.resolve_repo_root(None)
except models.PipelineError as error:
    assert '--repo-root' in str(error)
else:
    raise AssertionError('wheel guessed its repository root')
root = paths.resolve_repo_root(Path(sys.argv[2]))
records = []
for mode in ('test_data', 'production'):
    args = cli.build_parser().parse_args(['--mode', mode, '--repo-root', str(root), '--force-selected', '--force-mc', '--force-bdt'])
    assert args.force_selected and args.force_mc and args.force_bdt
    config = paths.mode_config(mode, root)
    locations = paths.build_paths(config, root / ('results' if mode == 'production' else 'results_test') / 'campaign with spaces')
    for bins in (8, 12, 16):
        stages = planning.build_pipeline_plan(config, locations, models.PreflightResult('/root with spaces/bin/root'), python_executable='/python path/bin/python', phi_bins=bins)
        stages = resources.configure_resources(stages, cpus=4, seed=123, extraction_workers=2)
        records.append([dataclasses.asdict(stage) for stage in stages])
print(json.dumps(records, default=str))
""")
    expected = []
    from dataclasses import asdict
    for mode in ("test_data", "production"):
        config = paths.mode_config(mode, REPO)
        locations = paths.build_paths(config, REPO / ("results" if mode == "production" else "results_test") / "campaign with spaces")
        for bins in (8, 12, 16):
            stages = planning.build_pipeline_plan(config, locations, models.PreflightResult("/root with spaces/bin/root"), python_executable="/python path/bin/python", phi_bins=bins)
            expected.append([asdict(stage) for stage in resources.configure_resources(stages, cpus=4, seed=123, extraction_workers=2)])
    assert json.loads(result.stdout) == json.loads(json.dumps(expected, default=str))


def test_wheel_module_script_and_console_help_from_external_cwd(installed_workflow):
    scratch, target, env = installed_workflow
    for argv in ([sys.executable, "-B", "-m", "graal_workflow", "--help"],
                 [sys.executable, "-B", str(REPO / "scripts/run_pipeline.py"), "--help"],
                 [str(target / "bin/graal-workflow"), "--help"]):
        result = subprocess.run(argv, cwd="/tmp", env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "--repo-root" in result.stdout
    plot_help = subprocess.run([sys.executable, "-B", str(REPO / "scripts/plot_campaign.py"), "--help"],
                               cwd="/tmp", env=env, capture_output=True, text=True)
    assert plot_help.returncode == 0, plot_help.stdout + plot_help.stderr
    assert "--published-csv" in plot_help.stdout
    invalid = subprocess.run([sys.executable, "-B", "-m", "graal_workflow", "--mode", "test_data", "--repo-root", str(scratch)], cwd="/tmp", env=env, capture_output=True, text=True)
    assert invalid.returncode == 1
    assert "invalid repository root" in invalid.stderr and "run_manifest.csv" in invalid.stderr
    absent = subprocess.run([sys.executable, "-B", "-m", "graal_workflow", "--mode", "test_data"], cwd="/tmp", env=env, capture_output=True, text=True)
    assert absent.returncode == 1 and "requires --repo-root" in absent.stderr


def test_source_inventory_rejects_missing_native_and_empty_python(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="source inventory is empty"):
        artifact_manifest.source_fingerprint(())
    locations = paths.build_paths(paths.mode_config("test_data", tmp_path))
    with pytest.raises(models.PipelineError, match="native source inventory is empty"):
        execution._source_files(locations, "03_mc_simulation")
    import graal_workflow
    monkeypatch.setattr(graal_workflow, "__file__", str(tmp_path / "absent/__init__.py"))
    with pytest.raises(ValueError, match="source inventory is empty"):
        resources.installed_package_sources("graal_workflow")


def test_reconstruction_rejects_empty_source_inventory(tmp_path, monkeypatch):
    import reconstruction
    from reconstruction.runtime.reco_core import RecoConfig, _snapshot_inputs
    monkeypatch.setattr(reconstruction, "__file__", str(tmp_path / "missing/__init__.py"))
    with pytest.raises(ValueError, match="source inventory is empty"):
        _snapshot_inputs(RecoConfig(tmp_path, tmp_path / "output.root"))


def test_installed_fingerprints_cover_every_workflow_module(installed_workflow):
    result = _installed(installed_workflow, """
from graal_workflow import execution, paths, artifact_manifest
root = paths.resolve_repo_root(Path(sys.argv[2]))
locations = paths.build_paths(paths.mode_config('test_data', root))
sources = execution._source_files(locations, '02_event_selector')
workflow = tuple((Path(sys.argv[1]) / 'graal_workflow').glob('*.py'))
assert set(workflow).issubset(sources)
assert all(Path(p).is_relative_to(Path(sys.argv[1])) for p in sources)
initial = artifact_manifest.source_fingerprint(sources)
for module in workflow:
    original = module.read_bytes()
    try:
        module.write_bytes(original + b'\\n# fingerprint mutation check\\n')
        assert artifact_manifest.source_fingerprint(sources) != initial, module
    finally:
        module.write_bytes(original)
print(f'{len(workflow)} installed workflow modules invalidate selected cache')
""")
    assert "10 installed workflow modules" in result.stdout


def test_wheel_executes_native_and_reconstruction_with_real_provenance(installed_workflow):
    scratch, target, env = installed_workflow
    result = _installed(installed_workflow, r'''
from array import array
from dataclasses import replace
import json
import shutil
import ROOT
from graal_workflow import paths, planning, models, resources, execution
from graal_common.physics.channels import get_channel
from reconstruction.runtime.provenance import KEY
root = paths.resolve_repo_root(Path(sys.argv[2]))
proof = Path(sys.argv[3]) / 'artifacts'
proof.mkdir()
# This test runs MC and reconstruction, not pre-analysis or selection. Supply
# a tiny inventory fixture instead of requiring the separately managed cohort.
import numpy as np
import uproot
from graal_workflow.artifact_manifest import validate_preanalysis
preanalysis = proof / 'preanalysis'
preanalysis.mkdir()
for profile in ('uv', 'vis'):
    path = preanalysis / f'pre_analisi_{profile}.root'
    with uproot.recreate(path) as fixture:
        fixture['h80'] = {'gammas': np.zeros((1, 0), dtype=np.float64),
                         'fcharged_theta': np.zeros((1, 0), dtype=np.float64),
                         'RunNumber': np.array([42], dtype=np.int32),
                         'Polarization': np.array([1], dtype=np.int32),
                         'Xstrip': np.array([1], dtype=np.float32)}
    validate_preanalysis((path,))
# Exercise production cache certification exclusively inside this test sandbox.
config = replace(paths.mode_config('production', root), preanalysis_dir=preanalysis, mc_events=12)
locations = replace(paths.build_paths(config), output_root=proof / 'campaign', artifact_root=proof / 'cache')
paths.prepare_output_dirs(locations)
mc = locations.mc_dir('uv') / get_channel('eta_pi0').mc_filename
stage = models.Stage('uv:generate:eta_pi0', (shutil.which('root'), '-l', '-b', '-q', planning.root_macro_call(root / '03_mc_simulation/generators/generate_eta_pi0_dataset.C', 12, 1.1, 1.5, mc)), kind='generate', profile='uv', channel='eta_pi0', seed_key='uv:generate:eta_pi0')
group = models.ArtifactGroup('mc', 'uv', (stage,), mc, channel='eta_pi0', energy_range=(1.1, 1.5))
stages = resources.configure_resources((group,), cpus=1, seed=123)
execution.execute_cached_plan(stages, config, locations, runner=resources.bounded_runner)
first = mc.stat().st_mtime_ns
renamed = replace(group, stages=(replace(stage, name='human-readable MC label'),))
renamed_stages = resources.configure_resources((renamed,), cpus=1, seed=123)
assert renamed_stages[0].stages[0].argv == stages[0].stages[0].argv
execution.execute_cached_plan(renamed_stages, config, locations, runner=resources.bounded_runner)
assert mc.stat().st_mtime_ns == first
execution.execute_cached_plan(stages, config, locations, force_mc=True, runner=resources.bounded_runner)
assert mc.stat().st_mtime_ns != first
manifest = json.loads((locations.output_root / 'pipeline_artifacts.json').read_text())
identities = [Path(row['path']) for row in manifest['source_files']]
assert any(p.is_relative_to(Path(sys.argv[1]) / 'graal_workflow') for p in identities)
assert root / '03_mc_simulation/generators/generate_eta_pi0_dataset.C' in identities
assert root / '03_mc_simulation/generators/smearing.h' in identities
# Turn the twelve generated events into a tiny selected-tree fixture.
selected = proof / 'selected'
selected.mkdir()
source = ROOT.TFile.Open(str(mc))
output = ROOT.TFile(str(selected / 'events.root'), 'RECREATE')
tree = ROOT.TTree('h85', 'native generated diagnostic fixture')
beam = ROOT.TLorentzVector()
tree.Branch('beam', 'TLorentzVector', beam, 32000, 0)
vectors = {name: ROOT.std.vector('TLorentzVector')() for name in ('gammas', 'protons', 'neutrons')}
for name, value in vectors.items():
    tree.Branch(name, value, 32000, 0)
scalars = {'RunNumber': array('i', [42]), 'Polarization': array('i', [1]), 'Xstrip': array('f', [1])}
for name, value in scalars.items():
    tree.Branch(name, value, f"{name}/{'F' if name == 'Xstrip' else 'I'}")
for event in source.Get('mc'):
    beam.SetPxPyPzE(event.beam.Px(), event.beam.Py(), event.beam.Pz(), event.beam.E())
    vectors['gammas'].clear()
    for name in ('eta_gamma1', 'eta_gamma2', 'pi0_gamma1', 'pi0_gamma2'):
        vectors['gammas'].push_back(getattr(event, name))
    vectors['protons'].clear()
    vectors['protons'].push_back(event.proton)
    tree.Fill()
tree.Write()
output.Close()
source.Close()
reconstructed = proof / 'reconstructed.root'
reco_stage = models.Stage('uv:reconstruct_chi2', (sys.executable, '-B', '-m', 'reconstruction.reconstruct_eta_pi0_chi2', '--input-dir', str(selected), '--output-file', str(reconstructed), '--profile', 'uv'))
execution.execute_plan((reco_stage,), locations, runner=resources.bounded_runner)
result = ROOT.TFile.Open(str(reconstructed))
metadata = json.loads(result.Get(KEY).GetTitle())
assert metadata['schema'] == 2 and metadata['selection_algorithm'] == 'pairing_missing_mass'
assert metadata['source_files']
assert all(Path(row['path']).is_relative_to(Path(sys.argv[1])) for row in metadata['source_files'])
assert any('/reconstruction/runtime/reco_core.py' in row['path'] for row in metadata['source_files'])
assert metadata['source_revision'] == 'unknown'
entries = result.Get('reco_eta_pi0_chi2').GetEntries()
assert entries > 0
result.Close()
(Path(sys.argv[3]) / 'provenance-proof.json').write_text(json.dumps({'native_input_events': 12, 'reconstructed_events': entries, 'workflow_sources': manifest['source_files'], 'reconstruction': metadata}, indent=2))
print(f'Wheel proof: native events=12; reconstructed={entries}; workflow sources={len(identities)}; reconstruction sources={len(metadata["source_files"])}; cache=RUN/SKIP/forced RUN')
''', scratch)
    (scratch / "proof.log").write_text(result.stdout + result.stderr)
    assert "cache=RUN/SKIP/forced RUN" in result.stdout


@pytest.mark.parametrize('mode', ['production', 'test_data'])
@pytest.mark.parametrize('flux_mode', ['audit', 'study'])
def test_fresh_flux_plan_inventories_static_inputs_before_calibration(tmp_path, mode, flux_mode):
    from dataclasses import replace
    config = paths.mode_config(mode, REPO)
    locations = replace(paths.build_paths(config), output_root=tmp_path / 'campaign', artifact_root=tmp_path / 'artifacts')
    stages = planning.build_pipeline_plan(config, locations, models.PreflightResult('root'), flux_study=flux_mode)
    generated_qa = locations.calibrated_flux.with_suffix('.qa.json')
    assert not generated_qa.exists()
    source_files = execution._stage_sources(locations, stages)
    assert generated_qa not in source_files
    assert locations.manifest in source_files
    assert artifact_manifest.inventory(source_files)
    paths.prepare_output_dirs(locations)
    dispatched = []
    def runner(argv, **kwargs):
        dispatched.append(argv)
        if len(dispatched) == 1:
            assert argv == stages[0].argv
            locations.calibrated_flux.parent.mkdir(parents=True, exist_ok=True)
            generated_qa.write_text('{}')
        else:
            assert generated_qa.exists()
        return subprocess.CompletedProcess(argv, 0)
    execution.execute_cached_plan(stages[:2], config, locations, runner=runner)
    assert dispatched == [stage.argv for stage in stages[:2]]


def test_missing_static_metadata_is_rejected_before_dispatch(tmp_path):
    from dataclasses import replace
    config = paths.mode_config('test_data', REPO)
    locations = replace(paths.build_paths(config), output_root=tmp_path / 'campaign')
    missing = tmp_path / 'missing-acquisition.json'
    stages = planning.build_pipeline_plan(config, locations, models.PreflightResult('root'),
                                          flux_study='study', flux_study_metadata=missing)
    with pytest.raises(FileNotFoundError, match='missing-acquisition.json'):
        execution.execute_cached_plan(stages, config, locations, runner=lambda *_a, **_k: pytest.fail('dispatched before static inputs were validated'))


def test_installed_extraction_applies_explicit_policy_and_matching_provenance(installed_workflow):
    scratch, _, _ = installed_workflow
    result = _installed(installed_workflow, r'''
from dataclasses import fields
import hashlib, json
import numpy as np
import calibration.run_quality as quality_module
from calibration.run_manifest import RunRecord, write_manifest
from observable_extraction import beam_asymmetry as beam, workflow, period_workflow
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.periods import selection_audit
from observable_extraction.io.reconstructed_events import EventArrays, select_sigma_events, select_brem_control
from observable_extraction.tests.test_calibration_io import _write_rows, _row
from graal_workflow import models, paths, planning
root = Path(sys.argv[2])
work = Path(sys.argv[3]) / 'extraction-policy'
work.mkdir()
policy_path = root / 'config/run_quality_exclusions.json'
expected = quality_module.load_run_quality(policy_path)
quality_module.DEFAULT_RUN_QUALITY_PATH = work / 'forbidden-site-packages-policy.json'
config = paths.mode_config('test_data', root)
plan = planning.build_pipeline_plan(config, paths.build_paths(config), models.PreflightResult('root'))
extract = next(stage for stage in models.flatten_stages(plan) if stage.name == 'uv:extract')
assert extract.argv[extract.argv.index('--run-quality') + 1] == str(policy_path)
manifest = work / 'manifest.csv'
write_manifest([RunRecord(run, 'period', 'P', 'UV', 'P_UV', 'manual', f'uv/run{run}.root') for run in (811, 1322)], manifest)
flux = work / 'flux.csv'
_write_rows(flux, [_row(run_number=run, source_period='period') for run in (811, 1322)])
runs = np.repeat([811, 1322], 3)
values = {field.name: np.zeros(len(runs)) for field in fields(EventArrays)}
values.update(run_number=runs, xstrip=np.full(len(runs), 17), polarization=np.tile([0, 1, 2], 2), beam_energy_gev=np.full(len(runs), 1.25))
events = EventArrays(**values)
raw, bdt = work / 'raw.root', work / 'bdt.root'
raw.write_bytes(b'fixture'); bdt.write_bytes(b'fixture')
args = beam.build_parser().parse_args(['--raw', str(raw), '--raw-bdt', str(bdt), '--flux-file', str(flux), '--run-manifest', str(manifest), '--run-quality', str(policy_path), '--output-dir', str(work / 'output'), '--by-period'])
workflow._validate_energy_inputs = period_workflow._validate_energy_inputs = lambda _: None
workflow.read_reconstructed = period_workflow.read_reconstructed = lambda *_: events
period_workflow.read_run_universe = lambda *_a, **_k: ({811, 1322}, [])
original_single = period_workflow._run_single
captured = {}
class ReachedInference(Exception): pass
def inspect_single(args, **kwargs):
    metadata = kwargs['metadata']
    assert metadata['run_quality'] == expected
    identity = next(row for row in metadata['input_identities'] if row['path'] == str(policy_path))
    assert identity['sha256'] == expected['sha256']
    captured['metadata'] = metadata
    return original_single(args, **kwargs)
period_workflow._run_single = inspect_single
def inspect_inference(**kwargs):
    assert kwargs['events'].run_number.tolist() == [811, 811]
    assert {key[0] for key in kwargs['exposures']} == {811}
    raise ReachedInference
workflow.extract_sample = inspect_inference
try:
    beam.run(args)
except ReachedInference:
    pass
else:
    raise AssertionError('did not reach real extraction selection boundary')
assert captured['metadata']['samples']['raw_bdt']['quality_excluded'] == 3
assert captured['metadata']['samples']['raw_bdt']['selected'] == 2
# The same frozen policy is accepted by control and audit readers without defaults.
exposures = load_exposures(flux, manifest_path=manifest, run_quality=expected)
assert select_brem_control(events, exposures, run_quality=expected).run_number.tolist() == [811]
assert selection_audit(events, exposures, (1.1, 1.5), run_quality=expected)['quality_excluded'] == 3
# Non-period entry also reaches inference with the declared policy.
period_workflow._run_single = original_single
args.by_period = False
try:
    beam.run(args)
except ReachedInference:
    pass
else:
    raise AssertionError('single extraction did not reach inference')
(work / 'policy-proof.json').write_text(json.dumps(captured, indent=2))
print('Installed extraction: explicit checkout policy applied to exposure/event/control/audit readers; recorded path and SHA-256 match')
''', scratch)
    (scratch / 'extraction-policy.log').write_text(result.stdout + result.stderr)


def test_wheel_common_config_and_calibration_fingerprint_from_external_cwd(installed_workflow):
    result = _installed(installed_workflow, """
import calibration
from calibration.common_inputs import load_common_inputs
from calibration.calibration_cache import implementation_identity, content_key
from calibration.run_quality import load_run_quality
from graal_workflow import paths, planning, models
root = paths.resolve_repo_root(Path(sys.argv[2]))
common = load_common_inputs(root)
assert Path(calibration.__file__).is_relative_to(Path(sys.argv[1]))
assert common['inputs']['run_quality'] == root / 'config/run_quality_exclusions.json'
locations = paths.build_paths(paths.mode_config('production', root))
assert locations.quality_path == common['inputs']['run_quality']
assert load_run_quality(locations.quality_path)['sha256'] == '52533f31d2ef0fb946ff60947712e516ecc94b8a98091a2ac51bcfbcf61ccc35'
plan = models.flatten_stages(planning.build_pipeline_plan(paths.mode_config('production', root), locations, models.PreflightResult('root')))
for stage in plan:
    if stage.kind == 'extract':
        assert stage.argv[stage.argv.index('--run-quality') + 1] == str(locations.quality_path)
driver = root / '06_calibration/build_strip_energy_flux.py'
initial = implementation_identity(driver)
assert all(not Path(row['source']).is_absolute() for row in initial)
installed = Path(calibration.__file__).parent / 'strip_energy_flux.py'
original = installed.read_bytes()
try:
    installed.write_bytes(original + b'\\n# installed mutation\\n')
    assert implementation_identity(driver) != initial
finally:
    installed.write_bytes(original)
print('wheel common config, exact policy, installed calibration identity verified')
""")
    assert 'exact policy' in result.stdout


def test_wheel_calibration_native_resource_executes_outside_checkout(installed_workflow):
    from calibration.tests.test_build_strip_energy_flux import write_h80
    scratch, _, _ = installed_workflow
    fixture = scratch / 'native-h80'
    fixture.mkdir()
    write_h80(fixture / 'h80.root', [(7, 1, strip, 0.75 + strip / 256)
                                   for strip in range(1, 129)])
    result = _installed(installed_workflow, """
import importlib, importlib.util, json
from importlib.resources import files
import calibration, ROOT
from calibration import strip_energy_root as owner
from calibration.calibration_cache import implementation_identity, content_key
installed = Path(sys.argv[1])
assert Path(owner.__file__).is_relative_to(installed)
resource = files('calibration').joinpath('native/strip_energy_rdf.hxx')
assert resource.read_bytes().startswith(b'\\n#include <ROOT/RDataFrame.hxx>')
lookup, qa = owner.read_h80_lookup(Path(sys.argv[3]), run_numbers=[7],
    samples_per_run_strip=256, threads=1, progress_every_events=0)
assert len(lookup) == 128 and qa['entries'] == 128
cells, bins = owner.read_calibration_cells(Path(sys.argv[3]), run_numbers=[7], threads=4)
assert len(cells) == 128 and len(bins) == 128
assert cells[0].energy_mean_gev == 0.75 + 1/256
def forbidden(*args):
    raise AssertionError('native helpers redeclared')
ROOT.gInterpreter.Declare = forbidden
for name in ('wheel_calibration_alias_a', 'wheel_calibration_alias_b'):
    spec = importlib.util.spec_from_file_location(name, owner.__file__)
    alias = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(alias)
    alias._declare_rdataframe_helpers(ROOT)
importlib.reload(owner)._declare_rdataframe_helpers(ROOT)
driver = Path(sys.argv[2]) / '06_calibration/build_strip_energy_flux.py'
sources = implementation_identity(driver)
assert sources and all(row['sha256'] for row in sources)
native = [row for row in sources if row['source'] == 'calibration/native/strip_energy_rdf.hxx']
assert len(native) == 1
header = Path(str(resource))
original = header.read_bytes()
try:
    header.write_bytes(original + b'\\n// installed native fingerprint mutation\\n')
    assert content_key({'implementation': sources}) != content_key({'implementation': implementation_identity(driver)})
finally:
    header.write_bytes(original)
proof = {'events': qa['entries'], 'lookup_rows': len(lookup), 'cells': len(cells),
         'energy_bins': len(bins), 'source_files': sources,
         'native_resource': str(resource), 'native_header': native}
(Path(sys.argv[4]) / 'calibration-native-proof.json').write_text(json.dumps(proof, indent=2))
print('installed native h80: 128 events; aliases/reload safe; header cache invalidation verified')
""", fixture, scratch)
    assert 'header cache invalidation verified' in result.stdout


def test_python310_toml_fallback_collects_with_conditional_test_dependency(tmp_path):
    # Force only the absent-stdlib branch on the current interpreter. Vendored
    # tomli is a real parser; this does not claim a Python 3.10 runtime test.
    code = r'''
import runpy, sys
from pathlib import Path
from pip._vendor import tomli
from pip._vendor.packaging.requirements import Requirement
sys.modules['tomllib'] = None
sys.modules['tomli'] = tomli
module = runpy.run_path(sys.argv[1])
assert module['tomllib'] is tomli
config = tomli.loads(Path(sys.argv[2]).read_text())
assert config['project']['requires-python'] == '>=3.10'
requirement = next(Requirement(item) for item in config['project']['optional-dependencies']['test'] if Requirement(item).name == 'tomli')
assert requirement.marker.evaluate({'python_version': '3.10'})
assert not requirement.marker.evaluate({'python_version': '3.11'})
assert config['tool']['setuptools']['package-dir']['calibration'] == '06_calibration'
print('Python 3.10 fallback branch and conditional test dependency verified on current interpreter')
'''
    result = subprocess.run([sys.executable, '-B', '-c', code, str(Path(__file__).resolve()),
                             str(REPO / 'pyproject.toml')], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'fallback branch' in result.stdout
