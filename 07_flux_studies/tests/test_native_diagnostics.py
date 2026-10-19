from flux_studies.native_diagnostics import clustered_coverage_intervals


def test_coverage_does_not_count_correlated_strips_or_states_as_independent():
    rows = [dict(period='p', state='POL1', method='linear', run=r,
                 coverage68=.7, coverage95=.9, integral_covered68=True,
                 integral_covered95=True) for r in range(20)]
    result = clustered_coverage_intervals(rows, {'p': {r: r // 5 for r in range(20)}})[0]
    assert result['coverage68']['observed'] == .7
    assert result['coverage68']['donor_clusters'] == 4
    assert result['coverage68']['interval95'] is None
    assert result['coverage68']['status'] == 'insufficient_clusters'
    boundary = clustered_coverage_intervals(rows, {'p': {r: r for r in range(20)}})[0]
    assert boundary['integral_covered95']['status'] == 'boundary_uninformative'
    assert boundary['integral_covered95']['nominal_inside_interval'] is None
    assert boundary['coverage68']['status'] == 'constant_cluster_coverage'
    assert boundary['coverage68']['nominal_inside_interval'] is None


def test_cluster_interval_reproducible_and_retains_missing_denominator():
    rows = [dict(period='p', state='BREM', method='linear', run=r,
                 coverage68=.5 + .04*r, coverage95=.7 + .02*r,
                 integral_covered68=r > 3, integral_covered95=r > 0) for r in range(10)]
    rows[0]['coverage68'] = None
    clusters = {'p': {r: r for r in range(10)}}
    a = clustered_coverage_intervals(rows, clusters, seed=4)
    assert a == clustered_coverage_intervals(rows, clusters, seed=4)
    assert a[0]['requested_targets'] == 10
    assert a[0]['coverage68']['evaluable_targets'] == 9
    assert len(a[0]['coverage68']['interval95']) == 2
def test_neural_plot_reports_unavailable_fit_instead_of_crashing(tmp_path):
    import json
    import numpy as np
    from flux_studies.native_diagnostics import plot_published_energy_views
    (tmp_path / 'native_calibration_axes.json').write_text('[]')
    block = tmp_path / 'block_3'
    block.mkdir()
    (block / 'predictions.csv').write_text('role,period,run,state,method\n')
    np.savez(block / 'spectra.npz', truth=np.empty((0, 128)), estimate=np.empty((0, 128)))
    (block / 'fits.json').write_text(json.dumps([dict(group=['small_period', 'P', 'UV', 'POL1'],
        models={f: dict(selected={'direct': None, 'hybrid': None}, candidates=[])
                for f in ('mlp', 'cnn1d')})]))
    plot_published_energy_views(tmp_path)
    assert (tmp_path / 'neural_learning.pdf').stat().st_size > 1000

