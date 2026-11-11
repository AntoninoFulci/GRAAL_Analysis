"""Self-contained NumPy plot archive and run/period rendering.

Members are plain .npy arrays inside a zip, readable with np.load(...,
allow_pickle=False). Write one run at a time to bound archive-building memory.
"""
import json
from pathlib import Path

import numpy as np

from graal_common.io.filesystem import atomic_output_directory


def write_array(archive, key, value):
    with archive.open(key+'.npy','w',force_zip64=True) as stream:
        np.save(stream,np.asarray(value),allow_pickle=False)


def write_run(archive, run, xyz, data, mask, record):
    prefix=f'run_{run}_'
    write_array(archive,prefix+'xyz_cm',xyz)
    for name in ('dca_cm','source_file','source_entry'):
        write_array(archive,prefix+name,data[name][mask])
    fit,spot=record['length_fit'],record['observed_xy']
    for key,value in {
        'z_edges_cm':fit['edges_cm'],'z_counts':fit['counts'],
        'z_expected_counts':fit['expected_counts'] if fit['expected_counts'] is not None else [],
        'x_edges_cm':spot['x_edges_cm'],'y_edges_cm':spot['y_edges_cm'],
        'xy_counts':spot['counts'],
    }.items():
        write_array(archive,prefix+key,np.asarray(value,dtype=float))


def metadata_without_arrays(report):
    # Keep provenance and every scalar diagnostic; numerical plot data live in NPZ.
    result={k:v for k,v in report.items() if k not in ('runs','periods')}
    result['runs']={}
    for run,row in report['runs'].items():
        result['runs'][run]={**row,
            'length_fit':{k:v for k,v in row['length_fit'].items() if k not in ('edges_cm','counts','expected_counts')},
            'observed_xy':{k:v for k,v in row['observed_xy'].items() if k not in ('x_edges_cm','y_edges_cm','counts')}}
    arrays={'x_edges_cm','y_edges_cm','xy_probability','z_edges_cm','z_probability','z_model_probability'}
    result['periods']={name:{k:v for k,v in row.items() if k not in arrays}
                       for name,row in report['periods'].items()}
    return result


def finish_archive(archive, report):
    for period,row in report['periods'].items():
        prefix=f'period_{period}_'
        for name in ('xy_probability','z_probability','z_model_probability','z_edges_cm'):
            write_array(archive,prefix+name,np.asarray(row[name],dtype=float))
        for axis in 'xy':
            write_array(archive,prefix+axis+'_edges_mm',10*np.asarray(row[axis+'_edges_cm']))
    metadata=metadata_without_arrays(report)
    write_array(archive,'metadata_json',json.dumps(metadata,allow_nan=False))
    return metadata


def _draw(output, *, title, xyz, zedges, zvalues, zmodel, length, edges,
          xedges, yedges, xyvalues, center, widths, normalized=False, length_std=None, local_edges=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    fig=plt.figure(figsize=(16,5),layout='constrained')
    fig.get_layout_engine().set(rect=(0,.06,1,.94))
    fig.suptitle(title,fontsize=13)
    ax=fig.add_subplot(1,3,1,projection='3d')
    inside=np.all(np.abs(xyz)<=np.array([3,3,8]),axis=1)
    points=xyz[inside]
    if len(points)>15000:
        points=points[np.random.default_rng(73).choice(len(points),15000,replace=False)]
    ax.scatter(*points.T,s=2,alpha=.2,color='#166b89')
    ax.set(xlim=(-3,3),ylim=(-3,3),zlim=(-8,8),xlabel='x [cm]',ylabel='y [cm]',zlabel='z [cm]',
           title=f'Vertici: campione visualizzato {len(points):,}\n{int((~inside).sum()):,} fuori vista nel campione')
    ax.set_box_aspect((6,6,16));ax.view_init(elev=18,azim=-55)
    ax=fig.add_subplot(1,3,2)
    ax.stairs(zvalues,zedges,label='Media profili run' if normalized else 'Dati',color='#166b89')
    if zmodel is not None and len(zmodel):
        if local_edges:
            ax.plot((np.asarray(zedges[:-1])+zedges[1:])/2,zmodel,drawstyle='steps-mid',
                    label='Media fit locali dei bordi' if normalized else 'Fit locali dei bordi',color='#dc6b26')
        else:
            ax.stairs(zmodel,zedges,label='Media modelli run' if normalized else 'Modello cella + fondo',color='#dc6b26')
    if length is not None:
        label=f"L {'media' if normalized else 'stimata'} ≈ {length:.3f} cm"
        if length_std is not None:
            label+=f'\nDispersione fra run: {length_std:.3f} cm'
        ax.set_title(label)
        for edge in edges:
            ax.axvline(edge,linestyle='--',color='.4')
    else:
        ax.set_title('Lunghezza non disponibile')
    ax.set(xlim=(-8,8),xlabel='z [cm]',ylabel='Densità media [1/cm]' if normalized else 'Eventi / bin')
    ax.legend(fontsize=8)
    ax=fig.add_subplot(1,3,3)
    h=np.asarray(xyvalues)
    if h.any():
        positive=h[h>0]
        mesh=ax.pcolormesh(xedges,yedges,np.ma.masked_equal(h.T,0),
                           norm=LogNorm(vmin=positive.min(),vmax=max(positive.min()*2,positive.max())),cmap='viridis')
        fig.colorbar(mesh,ax=ax,label='Probabilità media / bin' if normalized else 'Eventi / bin')
    ax.set(xlim=(-3,3),ylim=(-3,3),xlabel='x [cm]',ylabel='y [cm]',
           title='Spot XY medio — uguale peso ai run' if normalized else 'Spot XY osservato entro bordi z')
    ax.set_aspect('equal')
    if center is not None:
        ax.text(.02,.02,f'Centro: ({center[0]:.3f}, {center[1]:.3f}) cm\n'
                f'Larghezze 68%: ({widths[0]:.3f}, {widths[1]:.3f}) cm',transform=ax.transAxes,
                fontsize=9,bbox={'facecolor':'white','alpha':.85,'edgecolor':'none'})
    fig.savefig(output,dpi=160)
    plt.close(fig)


def period_sample(archive, runs):
    """Same achievable quota per run; never let statistics change run weights."""
    if not runs:
        return np.empty((0,3))
    quota=min(15000//len(runs), *(len(archive[f'run_{run}_xyz_cm']) for run in runs))
    samples=[]
    for run in runs:
        points=archive[f'run_{run}_xyz_cm']
        rng=np.random.default_rng(73+run)
        samples.append(points[rng.choice(len(points),quota,replace=False)])
    return np.concatenate(samples)


def render_periods(archive_path, report, output):
    with np.load(archive_path,allow_pickle=False) as archive:
        for period,row in report['periods'].items():
            # Equal-size samples per included run; all original points remain archived.
            xyz=period_sample(archive,row['included_runs'])
            bins=np.asarray(row['z_edges_cm'])
            _draw(Path(output)/f'period_{period}_target_spot.png',
                  title=f"Periodo {period} | DCA ≤4 mm | {row['n_runs']} run inclusi / {row['n_catalog_runs']} catalogati | "
                        f"copertura {row['coverage_status']} | {row['geometry_status']}",
                  xyz=xyz,zedges=bins,zvalues=np.asarray(row['z_probability'])/np.diff(bins),
                  zmodel=np.asarray(row['z_model_probability'],dtype=float)/np.diff(bins),length=row['length_cm'],
                  edges=[row['z_min_cm'],row['z_max_cm']],length_std=row['length_run_std_cm'],
                  xedges=row['x_edges_cm'],yedges=row['y_edges_cm'],xyvalues=row['xy_probability'],
                  center=row['spot_mean_cm'],widths=row['spot_sigma68_cm'],normalized=True,
                  local_edges=row.get('model_scope')=='local_edges')


def render_archived_run(archive_path, run, output):
    run=int(run)
    filename=f'run_{run}_target_spot.png'
    with np.load(archive_path,allow_pickle=False) as archive:
        metadata=json.loads(archive['metadata_json'].item())
        if metadata.get('schema')!=2 or str(run) not in metadata['runs']:
            raise ValueError('unsupported archive or missing run')
        row=metadata['runs'][str(run)];fit=row['length_fit'];spot=row['observed_xy']
        prefix=f'run_{run}_'
        with atomic_output_directory(Path(output),overwrite=False) as out:
            _draw(out/filename,title=f'Run {run} | DCA ≤4 mm | {row["selected_events"]:,} eventi | da archivio NPZ',
                  xyz=archive[prefix+'xyz_cm'],zedges=archive[prefix+'z_edges_cm'],
                  zvalues=archive[prefix+'z_counts'],zmodel=archive[prefix+'z_expected_counts'],
                  length=fit['length_cm'],edges=[fit.get('z_min_cm'),fit.get('z_max_cm')],
                  xedges=archive[prefix+'x_edges_cm'],yedges=archive[prefix+'y_edges_cm'],
                  xyvalues=archive[prefix+'xy_counts'],center=spot['median_cm'],widths=spot['sigma68_cm'],
                  local_edges=fit.get('model_scope')=='local_edges')
    return Path(output)/filename
