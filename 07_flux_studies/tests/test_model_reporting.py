"""Model comparisons must use matched targets and display the hybrid."""
import numpy as np


def test_comparisons_report_intersection_and_default_control():
    from flux_studies.study_calibrated_neighbors import _summary
    def prediction(run, method, error):
        return dict(run=run, period='p', state='POL1', role='test', method=method,
                    relative_l1=error, relative_integral_error=error,
                    shape_l1=error)
    rows = [prediction(1, 'linear', .2), prediction(2, 'linear', .8),
            prediction(1, 'ridge_hybrid', .1), prediction(1, 'ridge_default_hybrid', .3)]
    summary = _summary(dict(predictions=rows, block_size=1, status='exploratory', exclusions=[]))
    comparison = next(c for c in summary['comparisons'] if c['method']=='ridge_hybrid' and c['reference']=='linear')
    assert comparison['n'] == 1
    assert comparison['reference_mean_relative_l1'] == .2
    assert comparison['method_mean_relative_l1'] == .1
    control = next(c for c in summary['comparisons'] if c['method']=='ridge_hybrid' and c['reference']=='ridge_default_hybrid')
    assert control['n'] == 1
    assert control['method_better_fraction'] == 1


def test_overlay_contains_all_model_families_and_hybrids():
    from flux_studies.neighbor_plots import _overlay
    import matplotlib.pyplot as plt
    energy = np.linspace(.5, 2, 128)
    rows=[]
    for method in ['linear', 'ridge', 'ridge_hybrid', 'kernel_ridge', 'kernel_ridge_hybrid', 'extra_trees', 'extra_trees_hybrid']:
        rows.append(dict(method=method, truth=np.ones(128), estimate=np.ones(128)*1.1,
                         lower95=None,upper95=None,lower68=None,upper68=None,
                         run=7,period='p',state='POL1',donors=[6,8],count=100,gap=30))
    figure = _overlay(rows,energy)
    labels=' '.join(line.get_label() for ax in figure.axes for line in ax.lines)
    assert 'Kernel' in labels
    assert 'Extra' in labels
    assert labels.count('hybrid') >= 3
    plt.close(figure)
