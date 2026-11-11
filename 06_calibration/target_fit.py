"""Approximate target edges and observed vertex spot, never beam unfolding."""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import ndtr, xlogy


Z_EDGES = np.linspace(-15., 15., 301)
PARAMETERS = ('length_cm', 'center_cm', 'effective_sigma_cm', 'background_fraction')
BOUNDS = ((1., 24.), (-5., 5.), (.03, 3.), (0., .7))


def select_vertices(data, *, dca_max_cm):
    """One independent candidate per event: exactly two eligible charges."""
    if not np.isfinite(dca_max_cm) or dca_max_cm <= 0:
        raise ValueError('dca_max_cm must be finite and positive')
    xyz = np.column_stack([data[f'{a}_cm'] for a in 'xyz'])
    mask = ((data['status'] == 0) & (data['n_charged'] == 2)
            & np.isfinite(xyz).all(axis=1) & np.isfinite(data['dca_cm'])
            & (data['dca_cm'] >= 0) & (data['dca_cm'] <= dca_max_cm))
    identities = np.column_stack([data['source_file'][mask], data['source_entry'][mask]])
    if len(np.unique(identities, axis=0)) != len(identities):
        raise ValueError('duplicate event identity in exactly-two-charge sample')
    return mask


def _bin_probabilities(parameters, edges):
    length, center, sigma, background = parameters
    low, high = center - length / 2, center + length / 2

    def primitive(t):
        return t * ndtr(t) + np.exp(-.5 * t*t) / np.sqrt(2*np.pi)

    # Exact finite-bin integration of uniform interval convolved with Gaussian.
    cdf = sigma / length * (primitive((edges-low)/sigma) - primitive((edges-high)/sigma))
    signal = np.maximum(np.diff(cdf), 0)
    signal /= signal.sum()  # likelihood conditional on declared fit window
    flat = np.diff(edges) / (edges[-1] - edges[0])
    return (1-background)*signal + background*flat


def _optimize(counts, edges, starts):
    weights = counts / counts.sum()

    def objective(p):
        return -np.dot(weights, np.log(np.maximum(_bin_probabilities(p, edges), 1e-300)))

    results = [minimize(objective, start, method='L-BFGS-B', bounds=BOUNDS,
                        options={'ftol': 1e-12, 'gtol': 1e-7, 'maxiter': 600}) for start in starts]
    valid = [r for r in results if r.success and np.isfinite(r.fun)]
    return min(valid, key=lambda r: r.fun) if valid else None


def fit_length(z, *, bootstrap=32, seed=73):
    """Fit smeared uniform cell plus flat background; uncertainty is conditional.

    Effective Gaussian width absorbs edge smearing; it is not a calibrated
    vertex error. No fit error is interpreted as a full systematic uncertainty.
    """
    z = np.asarray(z, dtype=float)
    if z.ndim != 1 or not np.isfinite(z).all():
        raise ValueError('expected finite 1D z coordinates')
    if bootstrap < 0:
        raise ValueError('bootstrap must be nonnegative')
    counts, edges = np.histogram(z, bins=Z_EDGES)
    result = dict(status='insufficient_statistics', length_cm=None, center_cm=None,
                  length_stat_error_cm=None, resolution_status='effective_fit_width_not_detector_calibration',
                  model='uniform_interval_convolved_gaussian_plus_flat_background',
                  statistical_method='multinomial_event_bootstrap_conditional_on_selection_and_fit_window',
                  bootstrap_requested=bootstrap, bootstrap_successful=0, seed=int(seed),
                  input_events=len(z), fit_events=int(counts.sum()), outside_fit_window=int(len(z)-counts.sum()),
                  edges_cm=edges.tolist(), counts=counts.tolist(), expected_counts=None,
                  parameter_bounds={k:list(v) for k,v in zip(PARAMETERS, BOUNDS)})
    if counts.sum() < 200 or np.count_nonzero(counts) < 12:
        return result
    median = np.clip(np.median(z), -4, 4)
    starts = [[length, median, .25, .03] for length in (3., 6.12, 11.1)]
    best = _optimize(counts, edges, starts)
    if best is None:
        result['status'] = 'fit_failed'
        return result
    result.update({name:float(value) for name,value in zip(PARAMETERS, best.x)})
    expected = counts.sum() * _bin_probabilities(best.x, edges)
    deviance = 2 * np.sum(xlogy(counts, counts/np.maximum(expected, 1e-300)) - counts + expected)
    ndf = len(counts) - 1 - len(best.x)
    at_boundary = [name for name,x,(lo,hi) in zip(PARAMETERS,best.x,BOUNDS)
                   if min(x-lo, hi-x) < 1e-4 * (hi-lo)]
    # Zero background alone is a legitimate boundary, not an undefined length.
    serious_boundary = set(at_boundary)
    if best.x[3] < 1e-4 * (BOUNDS[3][1]-BOUNDS[3][0]):
        serious_boundary.discard('background_fraction')
    result.update(status='approximate', deviance=float(deviance), ndf=ndf,
                  deviance_per_ndf=float(deviance/ndf), boundary_parameters=at_boundary,
                  model_check='poor_shape_agreement' if deviance/ndf > 2 else 'no_large_deviance',
                  expected_counts=expected.tolist(),
                  z_min_cm=float(best.x[1]-best.x[0]/2), z_max_cm=float(best.x[1]+best.x[0]/2))
    if serious_boundary:
        result['status'] = 'fit_at_boundary'
    rng = np.random.default_rng(seed)
    replicas = []
    for _ in range(bootstrap):
        sample = rng.multinomial(int(counts.sum()), counts/counts.sum())
        fit = _optimize(sample, edges, [best.x])
        if fit is not None:
            replicas.append(fit.x.tolist())
    result['bootstrap_successful'] = len(replicas)
    if len(replicas) >= max(8, int(np.ceil(.8*bootstrap))):
        replicas = np.asarray(replicas)
        result['length_stat_error_cm'] = float(np.std(replicas[:, 0], ddof=1))
        result['parameter_stat_covariance'] = np.cov(replicas, rowvar=False).tolist()
    return result


def observed_xy(xy):
    """Observed illuminated spot, with finite-window overflow and unknown truth."""
    xy = np.asarray(xy, dtype=float)
    if xy.ndim != 2 or xy.shape[1] != 2 or not np.isfinite(xy).all():
        raise ValueError('expected finite Nx2 coordinates')
    counts, xedges, yedges = np.histogram2d(xy[:,0], xy[:,1], bins=100, range=[(-5,5),(-5,5)])
    result = dict(status='empty' if not len(xy) else 'observed_not_unfolded',
                  events=len(xy), outside_xy_window=int(len(xy)-counts.sum()),
                  x_edges_cm=xedges.tolist(), y_edges_cm=yedges.tolist(), counts=counts.astype(int).tolist(),
                  target_diameter_cm=None, target_diameter_status='not_identifiable_without_illuminated_cell_edge',
                  true_beam_covariance_cm2=None, true_beam_status='acceptance_target_and_resolution_not_separated',
                  median_cm=None, sigma68_cm=None, illuminated_diameter95_cm=None)
    if len(xy):
        quantiles = np.quantile(xy, [.16,.5,.84], axis=0)
        median = quantiles[1]
        radii = np.linalg.norm(xy-median, axis=1)
        result.update(median_cm=median.tolist(), sigma68_cm=((quantiles[2]-quantiles[0])/2).tolist(),
                      illuminated_diameter95_cm=float(2*np.quantile(radii,.95)),
                      diameter_definition='twice 95th percentile radius about observed median; not cell diameter')
    return result
