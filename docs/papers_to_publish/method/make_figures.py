#!/usr/bin/env python3
"""Render the methods-paper figures from immutable stored products; no extraction rerun.

Run from any directory. Scratch configuration stays in results_test. Physics panels
are restricted to Ajaka Figure 4, 1.20--1.30 GeV, and matching published mass bins.
"""
from pathlib import Path
import os

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCRATCH = ROOT / 'results_test/method-paper-preservation-20261111'
for name in ('tmp', 'mpl', 'cache'):
    (SCRATCH / name).mkdir(parents=True, exist_ok=True)
os.environ['MPLCONFIGDIR'] = str(SCRATCH / 'mpl')
os.environ['TMPDIR'] = str(SCRATCH / 'tmp')
os.environ['XDG_CACHE_HOME'] = str(SCRATCH / 'cache')
import csv
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import uproot

OUT = HERE / 'figures'
OUT.mkdir(exist_ok=True)
CAMPAIGN = ROOT / 'results/trima_uv_vis_ajaka_phi0_gaussian_20261103'
HIST = CAMPAIGN / 'root/uv/reconstruction/istogrammi.root'
ASYM = CAMPAIGN / 'root/uv/beam_asymmetry/beam_asymmetry.root'
AJAKA = ROOT / '08_observable_extraction/references/ajaka2008_figure4_digitized.csv'
COLORS = ['#315b80', '#c3642a', '#28333d']
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.labelsize': 10, 'legend.fontsize': 8,
                     'pdf.fonttype': 42, 'savefig.bbox': 'tight'})
manifest = {'scope': 'Methods working draft; not final physics inference',
            'physics_domain_gev': [1.2, 1.3],
            'quality_domain_gev': [0.93, 1.5],
            'inputs': {}, 'figures': {}, 'checks': []}
for path in (HIST, ASYM, AJAKA):
    manifest['inputs'][str(path.relative_to(ROOT))] = {
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'bytes': path.stat().st_size}

def save(fig, name, details):
    fig.savefig(OUT / (name + '.pdf'), metadata={'Creator': 'GRAAL methods make_figures.py'})
    plt.close(fig)
    manifest['figures'][name] = details

def box(ax, x, y, width, height, title, body, color=COLORS[0]):
    ax.add_patch(FancyBboxPatch((x, y), width, height,
        boxstyle='round,pad=0.008,rounding_size=0.018',
        fc=color+'12', ec=color, lw=1.1))
    ax.text(x+width/2, y+height*.73, title, ha='center', va='center',
            fontsize=9.5, weight='bold', color=color)
    ax.text(x+width/2, y+height*.32, body, ha='center', va='center', fontsize=8)

def arrow(ax, start, end, color=COLORS[0], style='-'):
    ax.annotate('', xy=end, xytext=start,
                arrowprops={'arrowstyle': '-|>', 'color': color, 'lw': 1.2, 'linestyle': style})

fig, ax = plt.subplots(figsize=(7.2, 2.8))
ax.set(xlim=(0, 1), ylim=(0, 1)); ax.axis('off')
for x,t,b in [(0.01,'Preserve','HBOOK + Fortran\ncalibrations + conditions'),
              (.355,'Translate','ROOT + C++ / Python\nexplicit data contracts'),
              (.70,'Reanalyse','common reconstruction\nconventional + BDT')]:
    box(ax,x,.54,.29,.37,t,b)
arrow(ax,(.306,.725),(.345,.725));arrow(ax,(.652,.725),(.69,.725))
box(ax,.17,.04,.66,.27,'Validate and retain provenance',
    'identities + event counts + numerical checks\nbenchmark in the published domain',COLORS[1])
for x in [.155,.50,.845]:
    arrow(ax,(x,.53),(x if x==.50 else (.24 if x<.5 else .76),.32),COLORS[1])
save(fig,'preservation_chain',{'type':'conceptual schematic',
     'meaning':'Preservation strategy; arrows do not certify completed validation.'})

fig, ax = plt.subplots(figsize=(7.2, 3.0))
ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
for x,t,b in [(0.01,'Legacy evidence','GEANT3 geometry\nFortran response + PREAN'),
              (.355,'Modern execution','Geant4 + C++ response\nPython orchestration'),
              (.70,'Common boundary','detector records\nreconstruction + selection')]:
    box(ax,x,.56,.29,.38,t,b)
arrow(ax,(.306,.75),(.345,.75));arrow(ax,(.652,.75),(.69,.75))
box(ax,.01,.06,.46,.29,'Numerical validation','geometry / identities / routine parity',COLORS[0])
box(ax,.53,.06,.46,.29,'Physical validation — open','response / efficiencies / observable closure',COLORS[1])
arrow(ax,(.34,.55),(.24,.37));arrow(ax,(.67,.55),(.76,.37),COLORS[1], '--')
save(fig,'simulation_migration',{'type':'conceptual schematic',
     'meaning':'Numerical equivalence and physical calibration are separate validation levels.'})

h = uproot.open(HIST)
quality = json.loads(h['quality_metadata'].member('fTitle'))
source = json.loads(h['dalitz_metadata'].member('fTitle'))
manifest['quality_source_events'] = {s:{k:v[k] for k in
    ('entries','input','observed_energy_range_gev')}
    for s,v in source['samples'].items()}
manifest['eta_diagnostic_fits'] = {s:v['eta_mass_fit'] for s,v in quality['samples'].items()}

def histplot(ax, name, xlabel, xlim=None):
    counts = {}
    for sample, color, label in zip(('chi2','bdt'), COLORS, ('Conventional','BDT')):
        obj = h[name+'_'+sample]
        values, edges = obj.to_numpy()
        total = obj.values(flow=True).sum()
        assert total > 0 and np.all(values >= 0)
        ax.stairs(values/total, edges, label=label, color=color, lw=1.4)
        counts[sample] = {'total_including_flow': float(total),
                         'outside_visible_axis': float(total-values.sum())}
    ax.set_xlabel(xlabel); ax.set_ylabel('Fraction per bin')
    if xlim: ax.set_xlim(xlim)
    ax.grid(axis='y', alpha=.15)
    return counts

fig, axes = plt.subplots(1,2,figsize=(7.2,2.45),layout='constrained')
counts={}
for ax,n,label,ran in zip(axes,('massa_eta','massa_pi0'),
    (r'$m(\gamma\gamma)_\eta$ [GeV]',r'$m(\gamma\gamma)_{\pi^0}$ [GeV]'),
    ((.35,.75),(.06,.23))):
    counts[n]=histplot(ax,n,label,ran)
axes[0].legend(frameon=False)
save(fig,'mass_quality',{'type':'stored histograms','normalization':'total entries including flow',
    'domain':'UV integrated 0.93--1.50 GeV; no differential physics observable',
    'counts':counts,'warning':'Selected shapes, not detector resolution; no new fit performed.'})

fig, axes = plt.subplots(1,3,figsize=(7.2,2.4),layout='constrained')
counts={}
for ax,n,label in zip(axes,('missing_mass','coplanarity','theta_missing_proton'),
    (r'$M_{\rm miss}(\eta\pi^0)$ [GeV]',r'$\Delta\phi_p$ [deg]',r'$\theta_{\rm miss}-\theta_p$ [deg]')):
    counts[n]=histplot(ax,n,label)
axes[0].set_xlim(.87,1.01);axes[0].legend(frameon=False)
save(fig,'kinematic_quality',{'type':'stored histograms','counts':counts,
    'domain':'UV integrated 0.93--1.50 GeV; already selected',
    'warning':'Missing-mass window already applied; angular flow bins remain in normalization.'})

f = uproot.open(ASYM)
a = f['sigma_points'].arrays(library='np')
assert 'final_inference=suspended' in f['provenance'].member('fTitle')
assert 'sample 1 raw_bdt' in f['id_mapping'].member('fTitle')
assert 'estimator 0 likelihood' in f['id_mapping'].member('fTitle')
refs=list(csv.DictReader(AJAKA.open()))
pairs=('p_pi0','p_eta','eta_pi0')
labels=(r'$p\pi^0$',r'$p\eta$',r'$\eta\pi^0$')
matched={}
for pid,pair in enumerate(pairs):
    ref=[r for r in refs if r['pair']==pair and int(r['energy_bin'])==1]
    ix=np.flatnonzero((a['sample_id']==1)&(a['estimator_id']==0)&
                     (a['pair_id']==pid)&(a['energy_bin']==2))
    matched[pair]=[]
    for r in ref:
        near=ix[np.abs(a['mass_center_gev'][ix]-float(r['mass_gev']))<.006]
        assert len(near)==1, (pair,r)
        i=int(near[0])
        assert np.isclose(a['energy_low_gev'][i],1.2) and np.isclose(a['energy_high_gev'][i],1.3)
        assert a['fit_converged'][i] and not a['used_fallback'][i]
        matched[pair].append((i,r))

fig,axes=plt.subplots(1,3,figsize=(7.2,2.7),layout='constrained')
benchmark=[]
for ax,pair,label in zip(axes,pairs,labels):
    matches=matched[pair]; ix=np.array([i for i,r in matches])
    ax.errorbar(a['mass_center_gev'][ix],a['sigma'][ix],
        yerr=[a['stat_low'][ix],a['stat_high'][ix]],fmt='o',ms=3.5,
        capsize=2,color=COLORS[1],label='Modern chain (provisional)')
    for j,(i,r) in enumerate(matches):
        err=np.array([float(r['stat_low']),float(r['stat_high'])])
        ax.errorbar(float(r['mass_gev']),float(r['sigma']),
            yerr=err[:,None] if np.all(np.isfinite(err)) else None,
            fmt='s',mfc='white',ms=4,capsize=2,color=COLORS[0],
            label='Ajaka et al. (digitised)' if j==0 else None)
        benchmark.append({'pair':pair,'mass_bin':int(a['mass_bin'][i]),
            'mass_gev':float(a['mass_center_gev'][i]), 'sigma':float(a['sigma'][i]),
            'stat_low':float(a['stat_low'][i]),'stat_high':float(a['stat_high'][i]),
            'reference':r})
    ax.axhline(0,color='.6',lw=.7);ax.set_ylim(-.85,.30)
    ax.set_xlabel('$m('+label[1:-1]+')$ [GeV]'); ax.set_title(label)
    ax.grid(axis='y',alpha=.15)
axes[0].set_ylabel(r'$\Sigma$');axes[0].legend(frameon=False,fontsize=6.5,loc='lower left')
fig.suptitle(r'$1.20 < E_\gamma < 1.30$ GeV · conditional statistical intervals only',fontsize=10)
save(fig,'ajaka_benchmark',{'type':'published-domain diagnostic comparison','points':benchmark,
    'sample':'raw_bdt','estimator':'conditional likelihood; no finite-bin scaling',
    'warning':'final_inference=suspended; no full systematics or covariance with historical sample'})

# One fixed central reference point per projection, chosen by position, not fit quality.
fig,axes=plt.subplots(1,3,figsize=(7.2,2.7),layout='constrained')
fit_info=[]
for ax,pid,pair,label in zip(axes,range(3),pairs,labels):
    i,r=matched[pair][1]
    massbin=int(a['mass_bin'][i]);path=f'ratio_objects/{pair}/e2/m{massbin}'
    graph=f[path+'/ratio'];fit=f[path+'/fit']
    assert fit.member('fTitle')=='[0]*cos(2*x)+[1]+[2]*sin(2*x)'
    pars=np.array(fit.member('fFormula').member('fClingParameters'))
    x,y,err=[np.asarray(graph.member(k)) for k in ('fX','fY','fEY')]
    ri=np.flatnonzero((a['sample_id']==1)&(a['estimator_id']==1)&
        (a['pair_id']==pid)&(a['energy_bin']==2)&(a['mass_bin']==massbin))
    assert len(ri)==1
    ri=int(ri[0]);divisor=float(a['phi_bin_divisor'][ri])
    assert np.isclose(pars[0],a['sigma'][ri]*divisor)
    fit_y=pars[0]*np.cos(2*x)+pars[1]+pars[2]*np.sin(2*x)
    chi2=float(np.sum(((y-fit_y)/err)**2))
    assert np.isclose(chi2,a['fit_chi2'][ri],rtol=1e-6)
    ax.errorbar(np.degrees(x),y,yerr=err,fmt='o',ms=3,color=COLORS[0],capsize=2)
    xx=np.linspace(0,2*np.pi,400)
    ax.plot(np.degrees(xx),pars[0]*np.cos(2*xx)+pars[1]+pars[2]*np.sin(2*xx),color=COLORS[1],lw=1.4)
    ax.axhline(0,color='.65',lw=.6);ax.set_xlim(-10,360);ax.set_xticks([0,90,180,270,360])
    ax.set_ylim(-.85,.85);ax.set_xlabel(r'$\phi$ [deg]')
    ax.set_title(label+f"\n{a['mass_low_gev'][i]:.2f}–{a['mass_high_gev'][i]:.2f} GeV",fontsize=9)
    ax.text(.04,.05,rf'$\chi^2/\mathrm{{ndf}}={chi2:.1f}/{a["fit_ndf"][ri]}$',
            transform=ax.transAxes,fontsize=8)
    fit_info.append({'root_directory':path,'mass_reference':r,'parameters':pars.tolist(),
        'chi2_recomputed':chi2,'ndf':int(a['fit_ndf'][ri]),'divisor':divisor})
axes[0].set_ylabel(r'$R(\phi)$')
fig.suptitle(r'$1.20 < E_\gamma < 1.30$ GeV · stored polarisation-normalised fits',fontsize=10)
save(fig,'azimuthal_fits',{'type':'stored ratio graphs and fitted curves','fits':fit_info,
    'warning':'R is polarisation-normalised, not raw P_gamma Sigma; plotted amplitude is uncorrected for phi-bin averaging.'})
manifest['checks']=['Ajaka mass matching within 6 MeV; modern 40 MeV bins retained',
    'All displayed physics points within 1.20--1.30 GeV and published mass positions',
    'Stored fit amplitude equals ratio Sigma times phi-bin divisor',
    'Chi-square recomputed from stored graph equals recorded value',
    'No raw data, historical results or scientific configuration modified']
manifest['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
print('Generated',len(manifest['figures']),'figures; all provenance and domain checks passed.')
