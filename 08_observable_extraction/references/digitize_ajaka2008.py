#!/usr/bin/env python3
"""Recover Ajaka Figs 2/3 vector geometry, calibrate axes, reproduce published plots.

Requires pymupdf, numpy, matplotlib. This is a source-specific, auditable extraction,
not original tabulated experimental data. Run from any directory; see --help.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
import pymupdf

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/papers/Ajaka_2008_EtaPi0_Photoproduction_PRL100_052003.pdf"
SOURCE_SHA256 = "7fdf85fe56fa8b0e232d070269e3e58d4d7ca542dcd9ac2287291abaa6b4f1cb"
DOI = "https://doi.org/10.1103/PhysRevLett.100.052003"
PAIRS = ["p_pi0", "p_eta", "eta_pi0"]
LABELS = [r"$M(p\pi^0)$ (GeV)", r"$M(p\eta)$ (GeV)", r"$M(\eta\pi^0)$ (GeV)"]
CURVES = ["chiral_model", "three_body_phase_space", "eta_delta_phase_space", "pi0_s11_phase_space"]
CURVE_LABELS = ["Chiral model [11,12]", "Three-body phase space", r"$\eta\Delta$ phase space", r"$\pi^0 S_{11}$ phase space"]
STYLES = ["-", "-", "--", ":"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, default=lambda x: list(x)) + "\n")


def csv_write(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def circles(drawing):
    """Two closed cubic half-circles; their ENDPOINTS give the exact center.

    Drawing rect includes Bezier control points and is NOT the circle's bbox.
    """
    items = drawing["items"]
    out = []
    i = 0
    while i < len(items):
        item = items[i]
        if item[0] != "c":
            i += 1
            continue
        other = items[i + 1]
        assert other[0] == "c" and np.allclose(item[4], other[1], atol=.003)
        assert np.allclose(item[1], other[4], atol=.003)
        center = (np.array(item[1]) + np.array(item[4])) / 2
        out.append((i, center, abs(item[1].x - item[4].x) / 2))
        i += 2
    return out


def lines(drawing):
    return [np.array([it[1], it[2]]) for it in drawing["items"] if it[0] == "l"]


def calibration(rect, xlo, xhi, yhi):
    x0, y0, x1, y1 = map(float, rect)
    return dict(pdf_rect_pt=[x0, y0, x1, y1], x_range_gev=[xlo, xhi],
                y_range=[0, yhi], x_gev_per_pt=(xhi-xlo)/(x1-x0),
                y_units_per_pt=yhi/(y1-y0))


def transform(xy, cal):
    xy = np.asarray(xy)
    x0, _, _, y1 = cal["pdf_rect_pt"]
    return np.stack((cal["x_range_gev"][0] + (xy[..., 0]-x0)*cal["x_gev_per_pt"],
                     (y1-xy[..., 1])*cal["y_units_per_pt"]), axis=-1)


def extract_fig2(drawings):
    cal = calibration(drawings[0]["rect"], .9, 1.5, 5.)
    points, provenance, nakabayashi = [], [], []
    for idx in range(4, 25):
        d = drawings[idx]
        if d["type"] != "f":
            continue
        markers = circles(d)
        assert len(markers) == 1
        _, center, radius = markers[0]
        energy, sigma = transform(center, cal)
        error_paths = lines(drawings[idx-1]) if drawings[idx-1]["type"] == "s" else []
        # Only associate vertical lines at this marker's x (first marker has an
        # unrelated isolated fragment immediately before it in PDF draw order).
        error_paths = [x for x in error_paths if np.max(abs(x[:, 0]-center[0])) < .005]
        ys = np.concatenate(error_paths)[:, 1] if error_paths else None
        upper = (center[1]-min(ys))*cal["y_units_per_pt"] if ys is not None else None
        lower = (max(ys)-center[1])*cal["y_units_per_pt"] if ys is not None else None
        points.append(dict(energy_gev=float(energy), sigma_ub=float(sigma),
                           error_ub=(lower+upper)/2 if ys is not None else "",
                           error_available=bool(error_paths), error_low_ub=lower if ys is not None else "",
                           error_high_ub=upper if ys is not None else ""))
        provenance.append(dict(point_index=len(points)-1, drawing_index=idx, seqno=d["seqno"],
                               marker_center_pdf_pt=center.tolist(), marker_radius_pdf_pt=radius,
                               marker_bezier_items=d["items"], error_segments_pdf_pt=error_paths,
                               errorbar_average_note="Mean half-span; tiny asymmetry from exported plot quantization",
                               unresolved_error_graphical_upper_scale_ub=radius*cal["y_units_per_pt"] if not error_paths else None))
    assert len(points) == 12 and sum(p["error_available"] for p in points) == 9
    hollow = drawings[25]
    for item_index, center, radius in circles(hollow):
        error_paths = [np.array(it[1:]) for it in hollow["items"][item_index+2:item_index+4]]
        y = np.concatenate(error_paths)[:, 1]
        energy, sigma = transform(center, cal)
        nakabayashi.append(dict(energy_gev=float(energy), sigma_ub=float(sigma),
                               error_ub=(max(y)-min(y))/2*cal["y_units_per_pt"],
                               error_low_ub=(max(y)-center[1])*cal["y_units_per_pt"],
                               error_high_ub=(center[1]-min(y))*cal["y_units_per_pt"]))
    band = [transform(seg, cal) for seg in lines(drawings[26])]
    band_rows = [dict(segment=i, energy_start_gev=s[0, 0], sigma_start_ub=s[0, 1],
                      energy_end_gev=s[1, 0], sigma_end_ub=s[1, 1]) for i, s in enumerate(band)]
    fragment = [transform(seg, cal) for seg in lines(drawings[3])]
    return points, nakabayashi, band_rows, dict(calibration=cal, points=provenance,
          nakabayashi_raw_drawing=hollow, model_hatch_raw_drawing=drawings[26],
          unassigned_near_threshold_fragment=drawings[3],
          unassigned_fragment_note="No central marker is encoded at this x; excluded from numerical data."), band, fragment


def extract_fig3(drawings):
    points, curve_rows, panels = [], [], []
    for row in range(5):
        for col in range(3):
            # Each row is a 19-path group. First-column axes occupy two paths.
            base = row*19 + (0 if col == 0 else 7 if col == 1 else 13)
            curve_start = base + (2 if col == 0 else 1)
            marker_index = curve_start + 4
            frame = next(it[1] for it in drawings[base]["items"] if it[0] == "re")
            cal = calibration(frame, [1., 1.4, .6][col], [1.4, 1.8, 1.][col], [.02, .06, .06, .04, .04][row])
            panel = f"{'abcde'[row]}_{PAIRS[col]}"
            markers = circles(drawings[marker_index])
            assert len(markers) == 20 and len(drawings[marker_index]["items"]) == 40
            panel_meta = dict(panel=panel, row="abcde"[row], pair=PAIRS[col], energy_gev=round(1.1+.1*row, 1),
                              calibration=cal, frame_drawing_index=base, marker_drawing_index=marker_index,
                              markers=[], curves=[])
            for k, (item_index, center, radius) in enumerate(markers):
                mass, value = transform(center, cal)
                within_frame = bool(frame.x0-.003 <= center[0] <= frame.x1+.003 and
                                frame.y0-.003 <= center[1] <= frame.y1+.003)
                points.append(dict(panel=panel, row="abcde"[row], pair=PAIRS[col],
                                   energy_gev=panel_meta["energy_gev"], point_index=k, mass_gev=float(mass),
                                   dsigma_ub_per_mev=float(value), error_ub_per_mev="", error_available=False,
                                   center_inside_frame=within_frame))
                panel_meta["markers"].append(dict(point_index=k, item_index=item_index,
                     center_pdf_pt=center.tolist(), radius_pdf_pt=radius, center_inside_frame=within_frame))
            for curve_i, kind in enumerate(CURVES):
                idx = curve_start+curve_i
                d = drawings[idx]
                assert d["type"] == "s" and all(it[0] == "l" for it in d["items"])
                assert (d["width"] > 1) == (curve_i == 0)
                assert (d["dashes"] != "[] 0") == (curve_i >= 2)
                segments = lines(d)
                # Save all vertices in original path order, including outside-frame
                # vertices; plotting clips to the same frame as the source.
                vertices = np.vstack((segments[0][0], [s[1] for s in segments]))
                assert all(np.allclose(a[1], b[0], atol=.004) for a, b in zip(segments, segments[1:]))
                values = transform(vertices, cal)
                for n, (mass, val) in enumerate(values):
                    curve_rows.append(dict(panel=panel, row="abcde"[row], pair=PAIRS[col],
                         energy_gev=panel_meta["energy_gev"], curve=kind, vertex_index=n,
                         mass_gev=float(mass), dsigma_ub_per_mev=float(val)))
                panel_meta["curves"].append(dict(curve=kind, drawing_index=idx, seqno=d["seqno"],
                                               width_pdf_pt=d["width"], dashes=d["dashes"], vertices_pdf_pt=vertices))
            panels.append(panel_meta)
    assert len(points) == 300 and len(panels) == 15
    return points, curve_rows, panels


def plots(fig2, nak, band, fragment, fig3, curves, out):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": True,
                         "axes.spines.right": True, "pdf.fonttype": 42})
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.add_collection(LineCollection(band, colors=".55", linewidths=.45, label="Published model uncertainty band"))
    ax.add_collection(LineCollection(fragment, colors="black", linewidths=1.2))
    for i, p in enumerate(fig2):
        err = [[p["error_low_ub"]], [p["error_high_ub"]]] if p["error_available"] else None
        ax.errorbar(p["energy_gev"], p["sigma_ub"], yerr=err, fmt="o", color="black", markersize=5,
                    label="Ajaka et al. (filled points)" if i == 0 else None)
    ax.errorbar([p["energy_gev"] for p in nak], [p["sigma_ub"] for p in nak],
                yerr=np.array([[p["error_low_ub"] for p in nak], [p["error_high_ub"] for p in nak]]),
                fmt="o", markerfacecolor="white", color=".35", markersize=6, label="Nakabayashi et al. [16]")
    ax.set(xlim=(.9,1.5), ylim=(0,5), xlabel=r"$E_\gamma$ (GeV)", ylabel=r"Total cross section ($\mu$b)",
           title="Ajaka et al. (2008), Fig. 2: vector digitization")
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    fig.text(.5,.015,"Three low-energy error bars unresolved in source; not assigned zero uncertainty.",ha="center",fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1))
    for ext in ("png","pdf"):
        fig.savefig(out/f"ajaka2008_figure2_reproduced.{ext}",dpi=220)
    plt.close(fig)
    fig, axes = plt.subplots(5,3,figsize=(10,12),sharex="col",gridspec_kw={"hspace":0,"wspace":0})
    for row in range(5):
        for col in range(3):
            ax=axes[row,col]; panel=f"{'abcde'[row]}_{PAIRS[col]}"
            for i, kind in enumerate(CURVES):
                vals=[p for p in curves if p["panel"]==panel and p["curve"]==kind]
                ax.plot([p["mass_gev"] for p in vals],[p["dsigma_ub_per_mev"] for p in vals],
                        STYLES[i],color=".1" if i==0 else ".45",lw=1.7 if i==0 else .8,label=CURVE_LABELS[i])
            pts=[p for p in fig3 if p["panel"]==panel]
            ax.plot([p["mass_gev"] for p in pts],[p["dsigma_ub_per_mev"] for p in pts],
                    "o",mfc="none",mec="black",ms=3.5,mew=.65,label="Published experimental markers")
            ax.set(xlim=([1.,1.4,.6][col],[1.4,1.8,1.][col]),ylim=(0,[.02,.06,.06,.04,.04][row]))
            ax.set_yticks([0,[.01,.03,.03,.02,.02][row]])
            if col: ax.tick_params(labelleft=False)
            ax.tick_params(direction="in",top=False,right=False)
            ax.text(.95,.90,f"({'abcde'[row]})  {1.1+.1*row:.1f} GeV",ha="right",va="top",transform=ax.transAxes,fontsize=9)
            if row==4:ax.set_xlabel(LABELS[col])
    axes[4,0].set_xticks([1.,1.1,1.2,1.3]);axes[4,1].set_xticks([1.5,1.6,1.7]);axes[4,2].set_xticks([.7,.8,.9])
    fig.supylabel(r"$d\sigma/dM$ ($\mu$b/MeV)",x=.02)
    fig.suptitle("Ajaka et al. (2008), Fig. 3: all 15 panels",y=.985)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc="lower center",bbox_to_anchor=(.5,.013),ncol=2,fontsize=9,frameon=False)
    fig.text(.5,.006,"Nominal beam energies only; energy-window edges and experimental errors are not published.",ha="center",fontsize=8)
    fig.subplots_adjust(left=.10,right=.98,bottom=.12,top=.95)
    for ext in ("png","pdf"):
        fig.savefig(out/f"ajaka2008_figure3_reproduced.{ext}",dpi=220)
    plt.close(fig)


def render_source_and_check(doc, prov2, panels, out):
    for page_index, crop, figure in [(2,(306,43,562,244),2),(3,(143,49,470,368),3)]:
        pix=doc[page_index].get_pixmap(matrix=pymupdf.Matrix(4,4),clip=pymupdf.Rect(crop),annots=False)
        pix.save(out/f"ajaka2008_figure{figure}_source.png")
    # Source-image overlays verify mapping independently of the reproduction axes.
    for page_index,crop,figure,centers in [
        (2,(340,70,557,215),2,[p["marker_center_pdf_pt"] for p in prov2["points"]]),
        (3,(188,50,468,315),3,[m["center_pdf_pt"] for p in panels for m in p["markers"]])]:
        pix=doc[page_index].get_pixmap(matrix=pymupdf.Matrix(4,4),clip=pymupdf.Rect(crop),annots=False)
        rgb=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n)
        fig,ax=plt.subplots(figsize=(10,10 if figure==3 else 6))
        # Pixmap rounds the crop bounds to integer device coordinates.
        ax.imshow(rgb,extent=[pix.x/4,(pix.x+pix.width)/4,(pix.y+pix.height)/4,pix.y/4])
        c=np.array(centers);ax.scatter(c[:,0],c[:,1],s=9,marker="+",color="#00bfff",linewidths=.7)
        ax.set_xlim(crop[0],crop[2]);ax.set_ylim(crop[3],crop[1]);ax.axis("off")
        fig.tight_layout(pad=0);fig.savefig(out/f"ajaka2008_figure{figure}_coordinate_check.png",dpi=200);plt.close(fig)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source",type=Path,default=SOURCE)
    ap.add_argument("--reference-dir",type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument("--output-dir",type=Path,default=ROOT/"results/ajaka-digitization-20261021")
    args=ap.parse_args();ref=args.reference_dir;out=args.output_dir
    ref.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    if sha(args.source)!=SOURCE_SHA256:
        raise ValueError("Source hash changed; re-audit drawing indices and calibration before extraction")
    doc=pymupdf.open(args.source)
    d2,d3=doc[2].get_drawings(),doc[3].get_drawings()
    f2,nak,band_rows,prov2,band,fragment=extract_fig2(d2)
    f3,curves,panels=extract_fig3(d3)
    csv_write(ref/"ajaka2008_figure2_digitized.csv",f2)
    csv_write(ref/"ajaka2008_figure2_nakabayashi_digitized.csv",nak)
    csv_write(ref/"ajaka2008_figure2_model_hatching.csv",band_rows)
    csv_write(ref/"ajaka2008_figure3_digitized.csv",f3)
    csv_write(ref/"ajaka2008_figure3_curves_digitized.csv",curves)
    dump(ref/"ajaka2008_vector_provenance.json",dict(source_sha256=SOURCE_SHA256,
         coordinate_system="PDF points, origin upper left, x right, y down",figure2=prov2,figure3=panels,
         drawing_index_convention="0-based PyMuPDF get_drawings() in pinned source, excluding annotation appearance",
         extraction_resolution_pdf_pt=.17,
         resolution_note="Conservative one exported-plot grid step (~0.124 pt Fig2, ~0.161 pt Fig3), rounded up; not measurement uncertainty.",
         figure3_marker_note="All 20 encoded symbols retained per panel, including negative/baseline centers clipped by source frame; no physical zero or uncertainty substituted."))
    common=dict(schema_version=1,source=DOI,source_pdf=str(args.source.relative_to(ROOT)) if args.source.is_relative_to(ROOT) else str(args.source),
                source_sha256=SOURCE_SHA256,label="Ajaka et al. (2008), vector digitization",
                extraction="Published PDF vector marker centers/line endpoints; linear calibration to labeled axes; not original numerical data.",
                provenance="ajaka2008_vector_provenance.json",energy_units="GeV")
    dump(ref/"ajaka2008_figure2_manifest.json",dict(common,figure=2,observable="total",units="ub",
         errors="published_total_including_systematics",energy_bins="centers_only",data="ajaka2008_figure2_digitized.csv",
         digitization_uncertainty_ub=.17*prov2["calibration"]["y_units_per_pt"],
         digitization_uncertainty_energy_gev=.17*prov2["calibration"]["x_gev_per_pt"],
         missing_error_policy="Blank error_ub and error_available=False for three hidden/unencoded errorbars; never zero.",
         systematic_note="Published Fig2 errors already include approximately 7% systematic; do not add again.",
         error_symmetrization="error_ub is mean of low/high endpoint distances; asymmetric distances retained in CSV.",
         recovered_points=12,recovered_errorbars=9,excluded_geometry="One unassigned near-threshold line fragment; retained in provenance and reproduction."))
    dump(ref/"ajaka2008_figure3_manifest.json",dict(common,figure=3,observable="invariant_mass",units="ub/MeV",mass_units="GeV",
         errors="not_published",energy_bins="nominal_centers_only",energy_centers_gev=[1.1,1.2,1.3,1.4,1.5],
         energy_window_edges_gev=None,data="ajaka2008_figure3_digitized.csv",curves="ajaka2008_figure3_curves_digitized.csv",
         pairs=PAIRS,panels=15,points=300,curves_count=60,
         digitization_uncertainty_mass_gev=.00074,
         digitization_uncertainty_ub_per_mev_by_energy={str(p["energy_gev"]):.17*p["calibration"]["y_units_per_pt"] for p in panels},
         energy_window_note="Page3 says five narrow intervals; Fig3 labels nominal energies only, and gives no widths/edges. Fig4 wide intervals must not be reused.",
         normalization_note="Published experimental spectrum areas normalized to total experimental cross section at same nominal energy; curves retain published normalization.",
         errors_note="No errorbar path is encoded in any Fig3 data-marker drawing. Blank errors mean unavailable, not zero.",
         clipped_markers_note="All 300 encoded symbols retained; center_inside_frame=False flags centers outside frame (0.003 pt numeric tolerance). Preserve negative values; plotting clips to original frame."))
    plots(f2,nak,band,fragment,f3,curves,out)
    render_source_and_check(doc,prov2,panels,out)
    files=list(ref.glob("ajaka2008_figure[23]*"))+[ref/"ajaka2008_vector_provenance.json",Path(__file__)]+list(out.glob("*.png"))+list(out.glob("*.pdf"))
    dump(out/"manifest.json",dict(source_sha256=SOURCE_SHA256,source=str(args.source),
         pymupdf_version=pymupdf.__version__,matplotlib_version=matplotlib.__version__,
         generated_files={str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):sha(p) for p in sorted(files)},
         verification=dict(fig2_filled_markers=12,fig2_recovered_errorbars=9,fig2_hollow_markers=5,
                           fig3_panels=15,fig3_markers=300,fig3_curves=60,
                           fig3_centers_outside_frame=sum(not p["center_inside_frame"] for p in f3))))
    print(json.dumps({"figure2_points":len(f2),"figure2_errors":sum(p["error_available"] for p in f2),
                      "figure3_panels":len(panels),"figure3_points":len(f3),"curve_vertices":len(curves),"output":str(out)}))

if __name__=="__main__":
    main()
