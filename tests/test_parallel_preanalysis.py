from pathlib import Path
import shutil

import pytest
import ROOT
import uproot
import awkward as ak

from scripts import run_preanalysis


def test_merge_preserves_compression_to_avoid_recompressing_every_event(tmp_path, monkeypatch):
    from array import array

    shard = tmp_path / 'part.root'
    source = ROOT.TFile(str(shard), 'RECREATE')
    compression = source.GetCompressionSettings()
    tree = ROOT.TTree('h80', 'h80')
    value = array('i', [7])
    tree.Branch('value', value, 'value/I')
    tree.Fill()
    tree.Write()
    source.Close()
    native_merger = ROOT.TFileMerger

    class CheckedMerger:
        def __init__(self, *args):
            self.native = native_merger(*args)

        def __getattr__(self, name):
            return getattr(self.native, name)

        def Merge(self):
            assert not self.native.HasCompressionChange(), 'ROOT would recompress all tree baskets'
            return self.native.Merge()

    monkeypatch.setattr(ROOT, 'TFileMerger', CheckedMerger)
    output = tmp_path / 'merged.root'
    run_preanalysis._merge(output, [{'shard': str(shard), 'written': 1, 'skipped_no_tagger': 2}], {})
    result = ROOT.TFile.Open(str(output))
    try:
        assert result.GetCompressionSettings() == compression
        assert result.Get('h80').GetEntries() == 1
        assert result.Get('preanalysis_skipped_no_tagger').GetVal() == 2
    finally:
        result.Close()


def test_merge_disables_inherited_root_pool(tmp_path, monkeypatch):
    class CheckedMerger:
        def __init__(self, *args):
            assert not ROOT.IsImplicitMTEnabled()

        def OutputFile(self, *args):
            return False

    monkeypatch.setattr(ROOT, 'TFileMerger', CheckedMerger)
    ROOT.EnableImplicitMT(2)
    try:
        with pytest.raises(RuntimeError, match='Cannot create'):
            run_preanalysis._merge(tmp_path / 'output.root', [], {})
    finally:
        ROOT.DisableImplicitMT()


@pytest.mark.parametrize('only_untagged', [False, True])
def test_raw_parallel_equivalence_and_skip_counts(tmp_path, only_untagged):
    repo = Path(__file__).resolve().parents[1]
    import os
    original_path = Path(os.environ.get('GRAAL_RAW_SAMPLE', str(repo / 'test_data/raw/1998_uv/run1321.root')))
    if not original_path.exists():
        pytest.skip('local raw sample unavailable')
    raw = tmp_path / 'raw' / '1998_uv'
    raw.mkdir(parents=True)
    source_file = ROOT.TFile.Open(str(original_path))
    source = source_file.Get('h70')
    subset = ROOT.TFile(str(raw / 'run1321.root'), 'RECREATE')
    clone = source.CloneTree(0)
    for entry in ([21, 21] if only_untagged else [21, *range(48)]):
        source.GetEntry(entry)
        clone.Fill()
    clone.Write()
    subset.Close()
    source_file.Close()
    shutil.copyfile(raw / 'run1321.root', raw / 'run1322.root')
    outputs = []
    for cpus in (1, 2):
        out = tmp_path / f'h80-{cpus}'
        run_preanalysis.run(raw.parent, out, cpus=cpus)
        with uproot.open(out / 'pre_analisi_1998_uv.root') as file:
            tree = file['h80']
            outputs.append(ak.to_list(tree.arrays()))
            assert file['preanalysis_skipped_no_tagger'].member('fVal') > 0
            assert 'preanalysis_provenance' in file
        from scripts.artifact_manifest import validate_current_preanalysis
        validate_current_preanalysis([out / 'pre_analisi_1998_uv.root'])
        from event_selector.select_events import run as select
        select(out, tmp_path / f'h85-{cpus}', threads=cpus, pattern='pre_*.root')
        with uproot.open(tmp_path / f'h85-{cpus}' / 'analisi_1998_uv.root') as file:
            assert 'preanalysis_provenance' in file
        assert (out / 'preanalysis_manifest.json').exists()
    assert outputs[0] == outputs[1]
    assert len(outputs[0]) < 98
    if only_untagged:
        assert outputs[0] == []


def test_failed_raw_preserves_destination(tmp_path):
    raw = tmp_path / 'raw' / '1998_uv'
    raw.mkdir(parents=True)
    (raw / 'run1321.root').write_text('not ROOT')
    out = tmp_path / 'output'
    with pytest.raises((RuntimeError, ValueError)):
        run_preanalysis.run(raw.parent, out, cpus=2)
    assert not out.exists()


def test_preanalysis_refuses_existing_output(tmp_path):
    raw = tmp_path / 'raw' / '1998_uv'
    raw.mkdir(parents=True)
    (raw / 'run1321.root').touch()
    out = tmp_path / 'out'
    out.mkdir()
    sentinel = out / 'keep'
    sentinel.write_text('keep')
    with pytest.raises(FileExistsError):
        run_preanalysis.run(raw.parent, out, cpus=1)
    assert sentinel.read_text() == 'keep'


@pytest.mark.parametrize('changed', ['raw', 'cut'])
def test_new_inputs_during_processing_abort_publication(tmp_path, monkeypatch, changed):
    raw = tmp_path / 'raw' / '1998_uv'
    raw.mkdir(parents=True)
    (raw / 'run1321.root').write_bytes(b'raw')
    cuts = tmp_path / 'cuts'
    cuts.mkdir()
    (cuts / 'original.cpp').write_text('// cut')
    def convert(task):
        if changed == 'raw':
            (raw / 'run1322.root').write_bytes(b'new raw')
        else:
            (cuts / 'new.cpp').write_text('// new cut')
        return {'source': str(task[0]), 'shard': str(task[1]), 'input': 0,
                'written': 0, 'skipped_no_tagger': 0, 'input_run_states': []}
    monkeypatch.setattr(run_preanalysis, '_convert', convert)
    monkeypatch.setattr(run_preanalysis, '_merge', lambda *args: None)
    out = tmp_path / 'out'
    with pytest.raises(RuntimeError, match='changed'):
        run_preanalysis.run(raw.parent, out, cuts_dir=cuts)
    assert not out.exists()
