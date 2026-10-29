"""Execute launcher boundaries with tiny synthetic products, never scientific jobs."""
from array import array
import json
from pathlib import Path
import re
import subprocess

from graal_workflow.stage_configuration import normalize_stage_configuration
from graal_workflow import staged_workflow


def test_mc_only_executes_and_records_products_without_unrelated_inputs(tmp_path, monkeypatch):
    import ROOT
    from graal_common.physics.channels import get_channel
    generators = tmp_path / '03_mc_simulation/generators'
    generators.mkdir(parents=True)
    (generators/'generate_eta_pi0_dataset.C').write_text('// synthetic driver; subprocess is replaced in this test\n')
    for name in ('generator_runtime.h', 'smearing.h', 'beam_window.h'):
        (generators/name).write_text('// synthetic header\n')
    cfg = normalize_stage_configuration({
        'schema_version': 1,
        'campaign': {'mode': 'test_data', 'repo_root': str(tmp_path), 'output_dir': str(tmp_path/'results_test/mc-only')},
        'execution': {'cpus': 1},
        'profiles': {'uv': {'enabled': True}, 'vis': {'enabled': False}},
        'stages': {
            **{name: {'enabled': False} for name in ('preanalysis', 'calibration', 'flux_study', 'comparison')},
            **{name: {'common': {'enabled': False}} for name in ('selection', 'bdt', 'reconstruction', 'extraction', 'plots')},
            'monte_carlo': {'common': {'enabled': True, 'events_per_channel': 3, 'channels': ['eta_pi0']}},
        },
    })
    observed = []
    def runner(argv, **kwargs):
        observed.append(argv)
        if '.C(' in argv[-1]:
            output = Path(re.search(r'"([^\"]+\.root)"', argv[-1]).group(1))
            target = ROOT.TFile(str(output), 'RECREATE')
            tree = ROOT.TTree('mc', 'mc')
            buffers = []
            for name in ('beam', 'proton', 'target', *get_channel('eta_pi0').photon_branches):
                buffer = array('d', [1.])
                buffers.append(buffer)
                tree.Branch(name, buffer, f'{name}/D')
            tree.Fill()
            tree.Write()
            ROOT.TParameter('double')('beam_min_gev', 1.1).Write()
            ROOT.TParameter('double')('beam_max_gev', 1.5).Write()
            target.Close()
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(staged_workflow, 'bounded_runner', runner)
    monkeypatch.setattr(staged_workflow.shutil, 'which', lambda _: '/synthetic/root')
    assert staged_workflow.run_stage_configuration(cfg, assume_yes=True) == 0
    assert len(observed) == 2
    output = tmp_path/'results_test/mc-only'
    metadata = json.loads((output/'metadata/stage_artifacts.json').read_text())
    assert metadata['inputs'] == {}
    assert metadata['outputs']['mc.uv']
    assert metadata['outcomes'][0]['action'] == 'RUN'
    assert Path(metadata['outputs']['mc.uv'][0]['path']).is_file()
    assert not (tmp_path/'data').exists()
