"""Local target-edge fits with variable interior density and finite-bin likelihood.

Promoted from the independently checked 2000_uv2 pilot. No nominal target length
enters the fit. Smearing is effective, not a detector resolution calibration.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import minimize
from scipy.special import ndtr, xlogy

NODES, WEIGHTS = np.polynomial.legendre.leggauss(12)


def edge_density(z, edge, sigma, slope, direction):
    """Gaussian convolution of exp(slope*u) H(u), u pointing into cell.

    Valid as a local approximation, not a full-cell acceptance model.
    """
    t = direction*(z-edge)
    return np.exp(slope*t+.5*(slope*sigma)**2)*ndtr(t/sigma+slope*sigma)


def probabilities(parameters, edges, direction):
    edge, sigma, slope, background = parameters
    widths = np.diff(edges)
    points = (edges[:-1]+edges[1:])[:, None]/2 + widths[:, None]*NODES/2
    integrated = (edge_density(points, edge, sigma, slope, direction)@WEIGHTS)*widths/2
    signal = integrated/integrated.sum()
    return (1-background)*signal+background*widths/widths.sum()


def locate_edges(counts, edges):
    """Outer 15%-height crossings seed fit windows, never fix fitted edges."""
    centers = (edges[:-1]+edges[1:])/2
    smooth = gaussian_filter1d(np.asarray(counts, float)/np.diff(edges), 1.)
    background = np.median(smooth[np.abs(centers)>10])
    signal = np.maximum(smooth-background, 0)
    peak = np.argmax(signal)
    if signal[peak] <= 0:
        raise ValueError('no edge signal')
    # Contiguous central signal component prevents an isolated far-out bin seeding a window.
    threshold = .15*signal[peak]
    lo = peak
    hi = peak
    while lo>0 and signal[lo-1]>threshold:
        lo-=1
    while hi<len(signal)-1 and signal[hi+1]>threshold:
        hi+=1
    if hi-lo<10:
        raise ValueError('signal too narrow to locate two independent edges')
    return [float(centers[lo]), float(centers[hi])]


def fit_edge(counts, edges, seed, direction, halfwidth=1.6, initial=None):
    centers = (edges[:-1]+edges[1:])/2
    indices = np.flatnonzero(np.abs(centers-seed)<=halfwidth)
    bins = edges[indices[0]:indices[-1]+2]
    observed = np.asarray(counts, float)[indices]
    base = dict(status='insufficient_statistics', edge_cm=None, sigma_cm=None,
                slope_per_cm=None, background_fraction=None, window_cm=[float(bins[0]),float(bins[-1])],
                seed_cm=float(seed), direction=direction, halfwidth_cm=halfwidth, events=float(observed.sum()),
                indices=indices.tolist(), expected_counts=None)
    if observed.sum()<200 or np.count_nonzero(observed)<8:
        return base
    bounds = [(seed-.7*halfwidth,seed+.7*halfwidth),(.03,1.2),(-1.5,1.5),(0.,.5)]
    weights = observed/observed.sum()
    def objective(p):
        q = probabilities(p,bins,direction)
        return -float(weights@np.log(np.maximum(q,1e-300)))
    starts = [initial] if initial is not None else [[seed,sigma,slope,.03] for sigma,slope in ((.12,.2),(.3,.6),(.7,0.))]
    fits = [minimize(objective,start,method='L-BFGS-B',bounds=bounds,
                     options=dict(ftol=1e-12,gtol=1e-7,maxiter=500))
            for start in starts]
    fits = [f for f in fits if f.success and np.isfinite(f.fun)]
    if not fits:
        return {**base,'status':'fit_failed'}
    best = min(fits,key=lambda f:f.fun)
    edge,sigma,slope,bg = map(float,best.x)
    expected = observed.sum()*probabilities(best.x,bins,direction)
    deviance = float(2*np.sum(xlogy(observed,observed/np.maximum(expected,1e-300))-observed+expected))
    boundary = [i for i,(v,(low,high)) in enumerate(zip(best.x,bounds))
                if min(v-low,high-v)<1e-4*(high-low) and not(i==3 and v<1e-4)]
    return {**base,'status':'at_boundary' if boundary else 'ok','edge_cm':edge,'sigma_cm':sigma,
            'slope_per_cm':slope,'background_fraction':bg,'expected_counts':expected.tolist(),
            'deviance':deviance,'ndf':len(observed)-1-4,'deviance_per_ndf':deviance/(len(observed)-1-4),
            'parameters':best.x.tolist(),'bounds':bounds,'boundary_parameters':boundary}


def fit_pair(counts,edges,seeds,halfwidth):
    left,right = [fit_edge(counts,edges,seed,direction,halfwidth)
                  for seed,direction in zip(seeds,(1,-1))]
    ok = left['status']=='ok' and right['status']=='ok'
    return dict(status='ok' if ok else 'invalid_edge_fit',left=left,right=right,
                length_cm=right['edge_cm']-left['edge_cm'] if ok else None,
                center_cm=(right['edge_cm']+left['edge_cm'])/2 if ok else None)



def fit_edges(z, *, halfwidth=1.6, seeds=None, bootstrap=0, seed=73):
    """Find each run's own edges and fit disjoint local neighborhoods.

    Bootstrap conditions on the selected vertices and baseline seed/windows.
    None outside local windows means unmodelled density, never zero density.
    """
    z=np.asarray(z,dtype=float)
    if z.ndim!=1 or not np.isfinite(z).all():
        raise ValueError('expected finite 1D z coordinates')
    if not np.isfinite(halfwidth) or halfwidth<=0 or bootstrap<0:
        raise ValueError('invalid fit window or bootstrap count')
    edges=np.linspace(-15.,15.,301)
    counts=np.histogram(z,edges)[0]
    result=dict(status='insufficient_statistics',model='local_exponential_step_convolved_gaussian_plus_flat_background',
                model_scope='local_edges',length_cm=None,center_cm=None,z_min_cm=None,z_max_cm=None,
                length_stat_error_cm=None,resolution_status='effective_fit_width_not_detector_calibration',
                statistical_method='multinomial_event_bootstrap_conditional_on_selection_and_local_windows',
                bootstrap_requested=bootstrap,bootstrap_successful=0,seed=int(seed),
                input_events=len(z),fit_events=int(counts.sum()),outside_fit_window=int(len(z)-counts.sum()),
                edges_cm=edges.tolist(),counts=counts.tolist(),expected_counts=None,
                model_check='unavailable',halfwidth_requested_cm=halfwidth)
    if counts.sum()<400:
        return result
    try:
        seeds=locate_edges(counts,edges) if seeds is None else list(map(float,seeds))
    except ValueError as exc:
        return {**result,'status':'edge_detection_failed','note':str(exc)}
    if len(seeds)!=2 or not np.isfinite(seeds).all() or seeds[1]-seeds[0]<1.:
        return {**result,'status':'edge_detection_failed','note':'invalid or unresolved seed separation'}
    # Short cells must not place both opposing transitions in either local fit.
    width=min(halfwidth,.4*(seeds[1]-seeds[0]))
    centers=(edges[:-1]+edges[1:])/2
    if any(np.count_nonzero(np.abs(centers-s)<=width)<8 for s in seeds):
        return {**result,'status':'edge_detection_failed','note':'fit window outside histogram'}
    pair=fit_pair(counts,edges,seeds,width)
    result.update(edge_seeds_cm=seeds,halfwidth_effective_cm=width,local_edges={s:pair[s] for s in ('left','right')})
    if pair['status']!='ok':
        states={pair[s]['status'] for s in ('left','right')}
        status=('insufficient_statistics' if 'insufficient_statistics' in states else
                'fit_at_boundary' if 'at_boundary' in states else 'fit_failed')
        return {**result,'status':status}
    if pair['length_cm']<=0:
        return {**result,'status':'fit_failed','note':'crossed edges'}
    model=[None]*len(counts)
    for side in ('left','right'):
        for i,value in zip(pair[side]['indices'],pair[side]['expected_counts']):
            model[i]=value
    deviance=sum(pair[s]['deviance'] for s in ('left','right'))
    ndf=sum(pair[s]['ndf'] for s in ('left','right'))
    result.update(status='approximate',length_cm=pair['length_cm'],center_cm=pair['center_cm'],
                  z_min_cm=pair['left']['edge_cm'],z_max_cm=pair['right']['edge_cm'],
                  expected_counts=model,deviance=deviance,ndf=ndf,deviance_per_ndf=deviance/ndf,
                  model_check='poor_shape_agreement' if any(pair[s]['deviance_per_ndf']>2 for s in ('left','right')) else 'no_large_deviance')
    rng=np.random.default_rng(seed)
    replicas=[]
    for _ in range(bootstrap):
        sample=rng.multinomial(int(counts.sum()),counts/counts.sum())
        fits=[fit_edge(sample,edges,s,d,width,initial=pair[name]['parameters'])
              for s,d,name in zip(seeds,(1,-1),('left','right'))]
        if all(f['status']=='ok' for f in fits):
            replicas.append([f['edge_cm'] for f in fits])
    result['bootstrap_successful']=len(replicas)
    if len(replicas)>=max(8,int(np.ceil(.8*bootstrap))):
        replicas=np.array(replicas)
        result['length_stat_error_cm']=float(np.std(replicas[:,1]-replicas[:,0],ddof=1))
        result['edge_stat_covariance_cm2']=np.cov(replicas,rowvar=False).tolist()
    return result
