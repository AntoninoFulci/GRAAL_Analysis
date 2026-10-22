"""Inspect existing MC; no regeneration and no modification of data cuts."""
import json
from pathlib import Path
import numpy as np
import ROOT
from observable_extraction.io.cross_section import reconstruction_metadata
from mc_simulation.native_validation import verified_reconstruction

base = Path('results/cross-section-signal-acceptance-20261021/native-uniform-production-99900/reconstruction')
verified_reconstruction(base)
file = ROOT.TFile.Open(str(base / 'raw/2002_uv1/run3629.root'))
ids = np.array([int(event.Idevt) for event in file.Get('h70')]); file.Close()
with np.load(base / 'matched_events.npz') as archive:
    truth = archive['generated_p4']; energies = archive['generated_energy_gev']
    selected_ids = archive['selected_ids']; selected_truth_energy = energies[selected_ids - 1]
kinetic = truth[:,2,3] - .93821
theta = np.arctan2(np.linalg.norm(truth[:,2,:2],axis=1),truth[:,2,2])*180/np.pi
file = ROOT.TFile.Open(str(base / 'selected/analisi_2002_uv1.root'))
rows, multiplicities, pid = [], [], []
for event in file.Get('h85'):
    if 1.1 <= event.beam.E() <= 1.5 and event.gammas.size() >= 4:
        rows.append(ids[int(event.RawSourceEntry)] - 1)
        multiplicities.append(event.protons.size())
        pid.append([event.fcharged_tof[0], event.fcharded_de[0], event.fcharged_theta[0]*180/np.pi])
file.Close()
rows, multiplicities, pid = np.array(rows), np.array(multiplicities), np.array(pid)
result = {'status':'diagnostic_only_detector_not_validated','mc_period':'2002_uv1',
          'future_data_trial_period':'1998_uv','selection':'E_reco1.1-1.5GeV, >=4photons in h85; before proton/BDT cuts',
          'candidate_events':len(rows), 'proton_multiplicity':dict(zip(*[a.tolist() for a in np.unique(multiplicities,return_counts=True)])),
          'conditional_pid_by_truth':{}, 'pid_quantiles':{}}
for name, values, edges in [('proton_kinetic_gev',kinetic,[0,.03,.06,.1,.2,.4,.8]), ('proton_theta_deg',theta,[0,10,20,30,40,50,60,90,180])]:
    all_counts=np.histogram(values[rows],edges)[0]; accepted=np.histogram(values[rows[multiplicities==1]],edges)[0]
    result['conditional_pid_by_truth'][name]={'edges':edges,'before_proton_requirement':all_counts.tolist(),'exactly_one_proton':accepted.tolist()}
for name, keep in [('all',np.ones(len(rows),dtype=bool)),('exactly_one_proton',multiplicities==1)]:
    result['pid_quantiles'][name]={'probabilities':[.05,.25,.5,.75,.95],'variables':['tof_ns','de_stored_units','theta_deg'],'values':np.quantile(pid[keep],[.05,.25,.5,.75,.95],axis=0).tolist()}
metadata = reconstruction_metadata(base/'reconstructed.root')
result['cutflow'] = metadata['counts_by_run_state']
edges=[.95,1.1,1.15,1.2,1.25,1.3,1.35,1.4,1.45,1.5]
result['truth_energy_acceptance']={'edges_gev':edges,'generated':np.histogram(energies,edges)[0].tolist(),'selected_in_analysis':np.histogram(selected_truth_energy,edges)[0].tolist()}
out=Path('results/cross-section-native-total-20261021/diagnostics/mc_pid.json');out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'candidate_events':result['candidate_events'],'proton_multiplicity':result['proton_multiplicity']}))
