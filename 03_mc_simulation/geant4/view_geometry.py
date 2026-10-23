#!/usr/bin/env python3
"""Make an offline interactive view from meshes exported by GEANT4 itself.

Visualization meshes are tessellations, not the solids used for navigation.
Requires plotly; no Docker or network is needed to open the generated HTML.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import plotly.graph_objects as go

GROUPS = {
    "BGO · 480 cristalli": ("#3b82f6", 0.6, True),
    "Bersaglio e finestre": ("#eab308", 0.9, True),
    "Vertice e cilindri": ("#14b8a6", 0.65, True),
    "Camere piane": ("#a855f7", 0.6, True),
    "TOF forward": ("#f97316", 0.55, True),
    "Calorimetro forward": ("#ef4444", 0.5, True),
    "Dischi Catania": ("#ec4899", 0.65, True),
    "Supporti BGO": ("#64748b", 0.2, "legendonly"),
    "Aria e inviluppi": ("#94a3b8", 0.15, "legendonly"),
}


def group(name):
    if name == "BGO":
        return "BGO · 480 cristalli"
    if name in {"CIBM", "ENVM", "ENVI", "FEN1", "FEN2", "FEN3", "REF1", "REF2"}:
        return "Bersaglio e finestre"
    if name.startswith(("DSK", "CTL")):
        return "Dischi Catania"
    if name.startswith(("WAL", "CEL", "CES")) or name == "TROM":
        return "TOF forward"
    if name in {"CASC", "PLOM", "GMMR", "FE1", "FE2", "TROC"}:
        return "Calorimetro forward"
    if name.startswith(("PL", "CAA")) or name in {"CAS1", "CAS2", "TROU"}:
        return "Camere piane"
    if name.startswith("NID"):
        return "Supporti BGO"
    if name == "LAGR" or name.startswith("ARI"):
        return "Aria e inviluppi"
    return "Vertice e cilindri"


def make_view(scene_file: Path, output: Path):
    if output.exists():
        raise FileExistsError(f"Refusing overwrite: {output}")
    scene = json.loads(scene_file.read_text())
    buckets = defaultdict(lambda: {"vertices": [], "triangles": [], "labels": []})
    for mesh in scene:
        bucket = buckets[group(mesh["name"])]
        offset = len(bucket["vertices"])
        bucket["vertices"].extend(mesh["vertices"])
        bucket["triangles"].extend(
            [[offset + i for i in face] for face in mesh["triangles"]]
        )
        bucket["labels"].extend(
            [[mesh["path"], mesh["medium"], mesh["material"]]] * len(mesh["vertices"])
        )
    fig = go.Figure()
    for name, (color, opacity, visible) in GROUPS.items():
        bucket = buckets[name]
        if not bucket["vertices"]:
            continue
        x, y, z = zip(*bucket["vertices"])
        i, j, k = zip(*bucket["triangles"])
        fig.add_trace(
            go.Mesh3d(
                x=x,
                y=y,
                z=z,
                i=i,
                j=j,
                k=k,
                color=color,
                opacity=opacity,
                flatshading=True,
                name=name,
                visible=visible,
                showlegend=True,
                customdata=bucket["labels"],
                hovertemplate="%{customdata[0]}<br>Mezzo %{customdata[1]} · materiale %{customdata[2]}<br>x=%{x:.3f} y=%{y:.3f} z=%{z:.3f} cm<extra></extra>",
            )
        )
    views = {
        "Apparato completo": ([-160, 160], [-160, 160], [-110, 360]),
        "Regione centrale": ([-45, 45], [-45, 45], [-105, 105]),
        "Bersaglio e cilindri": ([-12, 12], [-12, 12], [-30, 35]),
        "Regione forward": ([-160, 160], [-160, 160], [85, 355]),
    }
    buttons = [
        {
            "label": label,
            "method": "relayout",
            "args": [
                {
                    "scene.xaxis.range": ranges[0],
                    "scene.yaxis.range": ranges[1],
                    "scene.zaxis.range": ranges[2],
                    "scene.camera": {"eye": {"x": 1.5, "y": 1.3, "z": 0.8}},
                }
            ],
        }
        for label, ranges in views.items()
    ]
    report_file = scene_file.with_name("comparison.json")
    report = json.loads(report_file.read_text()) if report_file.exists() else {}
    validation = (
        f"{report['queries']:,} punti verificati · tolleranza overlap 1 µm"
        if report.get("status") == "geometry_checks_passed"
        else "conversione diagnostica, validazione aperta"
    )
    fig.update_layout(
        title={
            "text": f"GRAAL · geometria GEANT4<br><sup>GRAAL_26 · cilindri vecchi · D, 6,12 cm · {validation}</sup>",
            "x": 0.03,
        },
        template="plotly_white",
        height=850,
        margin={"l": 0, "r": 0, "t": 105, "b": 35},
        legend={"title": "Clic per mostrare/nascondere", "itemsizing": "constant"},
        scene={
            "aspectmode": "data",
            "xaxis_title": "x [cm]",
            "yaxis_title": "y [cm]",
            "zaxis_title": "z fascio [cm]",
            "camera": {"eye": {"x": 1.5, "y": 1.3, "z": 0.8}},
        },
        updatemenus=[
            {
                "type": "dropdown",
                "buttons": buttons,
                "x": 0.03,
                "y": 1.04,
                "xanchor": "left",
                "yanchor": "top",
            }
        ],
        annotations=[
            {
                "text": "Trascina per ruotare · rotella per zoom · doppio clic nella legenda per isolare un gruppo",
                "xref": "paper",
                "yref": "paper",
                "x": 0,
                "y": -0.025,
                "showarrow": False,
                "xanchor": "left",
            }
        ],
    )
    fig.write_html(
        output,
        include_plotlyjs=True,
        full_html=True,
        config={"displaylogo": False, "responsive": True},
    )
    print(f"{output}: {len(scene)} mesh GEANT4, {len(fig.data)} gruppi, HTML offline")


def make_preview(scene_file: Path, output: Path):
    """Render a static scientific preview from the same native meshes."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    if output.exists():
        raise FileExistsError(output)
    scene = json.loads(scene_file.read_text())
    figure = plt.figure(figsize=(16, 7), facecolor="white")
    for number, central in enumerate((False, True), 1):
        ax = figure.add_subplot(1, 2, number, projection="3d")
        for mesh in scene:
            category = group(mesh["name"])
            if category in {"Aria e inviluppi", "Supporti BGO"}:
                continue
            if central and category in {
                "Camere piane",
                "TOF forward",
                "Calorimetro forward",
            }:
                continue
            vertices = mesh["vertices"]
            faces = [
                [(vertices[i][2], vertices[i][0], vertices[i][1]) for i in face]
                for face in mesh["triangles"]
            ]
            color = GROUPS[category][0]
            alpha = 0.13 if category == "BGO · 480 cristalli" else 0.35
            ax.add_collection3d(
                Poly3DCollection(faces, facecolor=color, alpha=alpha, linewidths=0)
            )
        if central:
            ax.set(xlim=(-105, 50), ylim=(-45, 45), zlim=(-45, 45))
            ax.set_box_aspect((155, 90, 90))
            ax.set_title("Regione centrale · BGO trasparente", pad=18)
        else:
            ax.set(xlim=(-110, 355), ylim=(-160, 160), zlim=(-160, 160))
            ax.set_box_aspect((465, 320, 320))
            ax.set_title("Apparato completo", pad=18)
        ax.set_xlabel("z fascio [cm]")
        ax.set_ylabel("x [cm]")
        ax.set_zlabel("y [cm]")
        ax.view_init(elev=18, azim=-63)
        ax.tick_params(labelsize=8)
    figure.suptitle(
        "GRAAL · geometria GEANT4\nGRAAL_26 · cilindri vecchi · deuterio, 6,12 cm",
        fontsize=17,
        y=0.98,
    )
    handles = [
        Patch(color=color, label=name)
        for name, (color, _, _) in GROUPS.items()
        if name not in {"Aria e inviluppi", "Supporti BGO"}
    ]
    figure.legend(
        handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=9
    )
    figure.subplots_adjust(left=0.01, right=0.98, top=0.82, bottom=0.13, wspace=0.02)
    figure.savefig(output, dpi=160, facecolor="white")
    plt.close(figure)
    print(output)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("scene", type=Path)
    cli.add_argument("output", type=Path)
    cli.add_argument("--preview", type=Path)
    args = cli.parse_args()
    make_view(args.scene, args.output)
    if args.preview:
        make_preview(args.scene, args.preview)
