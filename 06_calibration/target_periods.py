"""Equal-run period summaries; preserve mixtures and flag incompatible cells."""
from collections import defaultdict
import re

import numpy as np


LENGTH_SPAN_LIMIT_CM = .5  # descriptive compatibility guard, not a calibrated test


def exclusion_reason(row):
    """A local-edge estimate needs at least one successful check of each kind."""
    fit=row['length_fit']
    if row.get('reconstruction_status','completed')!='completed':
        return row['reconstruction_status']
    if fit['status']!='approximate':
        return fit['status']
    if fit.get('model_scope')=='local_edges':
        dca_checked=any(v.get('status')=='approximate'
                        for v in row.get('dca_variations_cm',{}).values())
        baseline_width=fit.get('halfwidth_effective_cm')
        window_checked=any(
            v.get('status')=='approximate' and baseline_width is not None
            and v.get('halfwidth_effective_cm') is not None
            and not np.isclose(v['halfwidth_effective_cm'],baseline_width,rtol=0,atol=1e-9)
            for v in row.get('window_variations_cm',{}).values())
        if not dca_checked or not window_checked:
            return 'edge_robustness_unavailable'
    if not np.asarray(row['observed_xy']['counts']).sum():
        return 'empty_xy_profile'
    return None


def _profile_summary(probability, xedges, yedges):
    if not probability.sum():
        return dict(spot_mean_cm=None, spot_rms_cm=None, spot_sigma68_cm=None,
                    spot_covariance_cm2=None, illuminated_diameter95_cm=None)
    centers = [(edges[:-1]+edges[1:])/2 for edges in (xedges,yedges)]
    marginals = [probability.sum(axis=1), probability.sum(axis=0)]
    means = [float(p@x) for p,x in zip(marginals,centers)]
    variances = [float(p@((x-mean)**2+np.diff(edges)**2/12))
                 for p,x,mean,edges in zip(marginals,centers,means,(xedges,yedges))]
    cross = float(np.sum(probability*(centers[0]-means[0])[:,None]*(centers[1]-means[1])[None,:]))
    widths = []
    for p,edges in zip(marginals,(xedges,yedges)):
        q = np.interp([.16,.84],np.r_[0,np.cumsum(p)],edges)
        widths.append(float((q[1]-q[0])/2))
    radii = np.hypot((centers[0]-means[0])[:,None],(centers[1]-means[1])[None,:]).ravel()
    order = np.argsort(radii)
    r95 = float(np.interp(.95,np.cumsum(probability.ravel()[order]),radii[order]))
    return dict(spot_mean_cm=means,spot_rms_cm=np.sqrt(variances).tolist(),spot_sigma68_cm=widths,
                spot_covariance_cm2=[[variances[0],cross],[cross,variances[1]]],
                illuminated_diameter95_cm=2*r95)


def aggregate_periods(runs, catalog_runs):
    """Average normalized per-run profiles, never raw-count-weighted widths.

    All valid fits are retained in descriptive averages, including a flagged
    poor shape agreement. A spread >0.5 cm or mixed material/beam labels blocks
    the single-geometry proposal. Coverage refers to the supplied catalog.
    """
    groups=defaultdict(list)
    for run,row in runs.items():
        period=row.get('catalog',{}).get('source_period')
        if not period or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',period):
            raise ValueError(f'run {run}: missing or invalid source period')
        groups[period].append(row)
    result={}
    for period,rows in sorted(groups.items()):
        rows=sorted(rows,key=lambda r:r['run'])
        reference=rows[0]
        xedges=np.asarray(reference['observed_xy']['x_edges_cm'],dtype=float)
        yedges=np.asarray(reference['observed_xy']['y_edges_cm'],dtype=float)
        zedges=np.asarray(reference['length_fit']['edges_cm'],dtype=float)
        for row in rows:
            for current,expected in ((row['observed_xy']['x_edges_cm'],xedges),
                                      (row['observed_xy']['y_edges_cm'],yedges),
                                      (row['length_fit']['edges_cm'],zedges)):
                if not np.array_equal(current,expected):
                    raise ValueError(f'{period}: incompatible histogram bins')
        included=[];excluded={}
        for row in rows:
            reason=exclusion_reason(row)
            if reason:
                excluded[str(row['run'])]=reason
            else:
                included.append(row)
        n=len(included)
        xy=np.zeros((len(xedges)-1,len(yedges)-1))
        z=np.zeros(len(zedges)-1);model=z.copy(); model_coverage=np.zeros(len(z),dtype=int)
        scopes={r['length_fit'].get('model_scope','full_profile') for r in rows}
        if len(scopes)!=1:
            raise ValueError(f'{period}: cannot mix local-edge and global length models')
        model_scope=scopes.pop()
        for row in included:
            h=np.asarray(row['observed_xy']['counts'],dtype=float)
            xy+=h/h.sum()/n
            h=np.asarray(row['length_fit']['counts'],dtype=float)
            z+=h/h.sum()/n
            expected=np.asarray(row['length_fit']['expected_counts'],dtype=float)
            if model_scope=='local_edges':
                valid=np.isfinite(expected)
                model[valid]+=expected[valid]/h.sum()/n
                model_coverage[valid]+=1
            else:
                model+=expected/expected.sum()/n
        # Show local predictions only where every included run has a model.
        # Unmodelled cell interior is absent, never a fabricated flat plateau.
        model_values=([float(v) if n and c==n else None for v,c in zip(model,model_coverage)]
                      if model_scope=='local_edges' else model.tolist())
        lengths=np.asarray([r['length_fit']['length_cm'] for r in included])
        centers=np.asarray([r['length_fit']['center_cm'] for r in included])
        errors=[r['length_fit']['length_stat_error_cm'] for r in included]
        target_labels=sorted({r['catalog']['target'] for r in rows})
        beam_labels=sorted({r['catalog']['beam_type'] for r in rows})
        span=float(np.ptp(lengths)) if n else None
        geometry_status=('no_valid_runs' if not n else
                         'mixed_target_labels' if len(target_labels)!=1 or target_labels[0]=='UNKNOWN' else
                         'mixed_beam_labels' if len(beam_labels)!=1 or beam_labels[0]=='UNKNOWN' else
                         'heterogeneous_lengths' if span>LENGTH_SPAN_LIMIT_CM else
                         'single_run' if n==1 else 'compatible_lengths')
        processed=[r['run'] for r in rows]
        expected=set(catalog_runs[period])
        if not set(processed)<=expected:
            raise ValueError(f'{period}: processed runs absent from catalog')
        mean_length=float(lengths.mean()) if n else None
        mean_center=float(centers.mean()) if n else None
        result[period]=dict(
            period=period,weighting='equal_weight_per_valid_run',processed_runs=processed,
            included_runs=[r['run'] for r in included],excluded_runs=sorted(map(int,excluded)),
            exclusion_reasons=excluded,catalog_runs=sorted(expected),missing_runs=sorted(expected-set(processed)),
            coverage_status='complete' if expected==set(processed) else 'partial',
            n_runs=n,n_processed_runs=len(rows),n_catalog_runs=len(expected),
            selected_events=sum(r['selected_events'] for r in included),
            target_labels=target_labels,beam_labels=beam_labels,
            geometry_status=geometry_status,geometry_candidate_available=geometry_status in ('compatible_lengths','single_run'),
            length_span_limit_cm=LENGTH_SPAN_LIMIT_CM,length_span_cm=span,
            length_cm=mean_length,center_z_cm=mean_center,
            length_run_std_cm=float(lengths.std(ddof=1)) if n>1 else None,
            length_stat_error_cm=float(np.linalg.norm(errors)/n) if n and all(e is not None for e in errors) else None,
            z_min_cm=mean_center-mean_length/2 if n else None,z_max_cm=mean_center+mean_length/2 if n else None,
            target_diameter_cm=None,historical_reference_diameter_cm=5.,
            poor_shape_runs=[r['run'] for r in included if r['length_fit']['model_check']=='poor_shape_agreement'],
            x_edges_cm=xedges.tolist(),y_edges_cm=yedges.tolist(),xy_probability=xy.tolist(),
            model_scope=model_scope,z_model_coverage_runs=model_coverage.tolist(),
            z_edges_cm=zedges.tolist(),z_probability=z.tolist(),z_model_probability=model_values,
            **_profile_summary(xy,xedges,yedges))
    return result
