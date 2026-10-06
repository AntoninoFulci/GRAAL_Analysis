"""Build the GRAAL overview deck from project-approved slide text and assets.

Requires pandoc, lxml, and Pillow. All image assets are committed alongside the
deck so the presentation can be rebuilt without ignored analysis outputs.
"""

from __future__ import annotations

import subprocess
import tempfile
import zipfile
from pathlib import Path

from lxml import etree
from PIL import Image


HERE = Path(__file__).resolve().parent
OUT = HERE / "graal_analysis_framework_asimmetrie.pptx"
EMU = 914400
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
N = {"p": P, "a": A, "r": R}
NAVY = "071E42"
BLUE = "0B5FA5"
ICE = "DDEFFA"
WHITE = "FFFFFF"
INK = "112642"
MUTED = "52657B"


def e(ns: str, tag: str, **attrs):
    return etree.Element(f"{{{ns}}}{tag}", **{k: str(v) for k, v in attrs.items()})


class Slide:
    def __init__(self, title: str, number: int, *, dark: bool = False, source: str = ""):
        self.number = number
        self.dark = dark
        self.title = title
        self.source = source
        self.shapes = []
        self.pictures = []
        self._id = 2

    def textbox(self, text: str, x: float, y: float, w: float, h: float, *,
                size: float = 20, color: str | None = None, bold: bool = False,
                align: str = "l", italic: bool = False):
        if color is None:
            color = WHITE if self.dark else INK
        sp = e(P, "sp")
        nv = e(P, "nvSpPr")
        nv.append(e(P, "cNvPr", id=self._id, name=f"Text {self._id}"))
        nv.append(e(P, "cNvSpPr", txBox="1"))
        nv.append(e(P, "nvPr"))
        sp.append(nv)
        sppr = e(P, "spPr")
        xfrm = e(A, "xfrm")
        xfrm.append(e(A, "off", x=round(x * EMU), y=round(y * EMU)))
        xfrm.append(e(A, "ext", cx=round(w * EMU), cy=round(h * EMU)))
        sppr.append(xfrm)
        sppr.append(e(A, "noFill"))
        ln = e(A, "ln")
        ln.append(e(A, "noFill"))
        sppr.append(ln)
        sp.append(sppr)
        body = e(P, "txBody")
        body.append(e(A, "bodyPr", wrap="square", lIns="0", rIns="0", tIns="0", bIns="0", anchor="t"))
        body.append(e(A, "lstStyle"))
        for line in text.split("\n"):
            para = e(A, "p")
            para.append(e(A, "pPr", algn=align))
            run = e(A, "r")
            props = e(A, "rPr", lang="it-IT", sz=round(size * 100), b="1" if bold else "0", i="1" if italic else "0")
            fill = e(A, "solidFill")
            fill.append(e(A, "srgbClr", val=color))
            props.append(fill)
            props.append(e(A, "latin", typeface="Aptos"))
            run.append(props)
            value = e(A, "t")
            value.text = line
            run.append(value)
            para.append(run)
            body.append(para)
        sp.append(body)
        self.shapes.append(sp)
        self._id += 1

    def image(self, name: str, x: float, y: float, w: float, h: float):
        path = HERE / "assets" / name
        with Image.open(path) as im:
            iw, ih = im.size
        ratio = min(w / iw, h / ih)
        dw, dh = iw * ratio, ih * ratio
        x += (w - dw) / 2
        y += (h - dh) / 2
        pic = e(P, "pic")
        nv = e(P, "nvPicPr")
        nv.append(e(P, "cNvPr", id=self._id, name=name, descr=name))
        cp = e(P, "cNvPicPr")
        cp.append(e(A, "picLocks", noChangeAspect="1", noGrp="1"))
        nv.append(cp)
        nv.append(e(P, "nvPr"))
        pic.append(nv)
        bf = e(P, "blipFill")
        bf.append(e(A, "blip", **{f"{{{R}}}embed": f"rId{len(self.pictures)+2}"}))
        stretch = e(A, "stretch")
        stretch.append(e(A, "fillRect"))
        bf.append(stretch)
        pic.append(bf)
        pr = e(P, "spPr")
        xf = e(A, "xfrm")
        xf.append(e(A, "off", x=round(x * EMU), y=round(y * EMU)))
        xf.append(e(A, "ext", cx=round(dw * EMU), cy=round(dh * EMU)))
        pr.append(xf)
        geom = e(A, "prstGeom", prst="rect")
        geom.append(e(A, "avLst"))
        pr.append(geom)
        pic.append(pr)
        self.shapes.append(pic)
        self.pictures.append(path)
        self._id += 1

    def render(self):
        slide = etree.Element(f"{{{P}}}sld", nsmap={"p": P, "a": A, "r": R})
        csld = e(P, "cSld")
        bg = e(P, "bg")
        bgpr = e(P, "bgPr")
        sf = e(A, "solidFill")
        sf.append(e(A, "srgbClr", val=NAVY if self.dark else WHITE))
        bgpr.append(sf)
        bgpr.append(e(A, "effectLst"))
        bg.append(bgpr)
        csld.append(bg)
        tree = e(P, "spTree")
        ng = e(P, "nvGrpSpPr")
        ng.append(e(P, "cNvPr", id="1", name=""))
        ng.append(e(P, "cNvGrpSpPr"))
        ng.append(e(P, "nvPr"))
        tree.append(ng)
        gp = e(P, "grpSpPr")
        xf = e(A, "xfrm")
        for tag, attrs in (("off", {"x": 0, "y": 0}), ("ext", {"cx": 0, "cy": 0}),
                           ("chOff", {"x": 0, "y": 0}), ("chExt", {"cx": 0, "cy": 0})):
            xf.append(e(A, tag, **attrs))
        gp.append(xf)
        tree.append(gp)
        for shape in self.shapes:
            tree.append(shape)
        csld.append(tree)
        slide.append(csld)
        override = e(P, "clrMapOvr")
        override.append(e(A, "masterClrMapping"))
        slide.append(override)
        rels = etree.Element(f"{{{REL}}}Relationships", nsmap={None: REL})
        rels.append(e(REL, "Relationship", Id="rId1", Type=R + "/slideLayout", Target="../slideLayouts/slideLayout2.xml"))
        for i, path in enumerate(self.pictures, 2):
            rels.append(e(REL, "Relationship", Id=f"rId{i}", Type=R + "/image", Target=f"../media/graal_slide{self.number}_{path.name}"))
        return etree.tostring(slide, xml_declaration=True, encoding="UTF-8"), etree.tostring(rels, xml_declaration=True, encoding="UTF-8")


def standard(title: str, n: int, source: str = "") -> Slide:
    s = Slide(title, n, source=source)
    s.textbox(title, .62, .38, 8.8, .52, size=32, color=NAVY, bold=True)
    if source:
        s.textbox("Fonte: " + source, .64, 5.29, 8.45, .18, size=8.5, color=MUTED)
    s.textbox(f"{n:02d}", 9.12, 5.27, .32, .2, size=9, color=MUTED, align="r")
    return s


slides: list[Slide] = []

s = Slide("GRAAL Analysis", 1, dark=True)
s.textbox("GRAAL Analysis", .67, .72, 8.5, .65, size=42, bold=True)
s.textbox("Framework per γp → pηπ⁰", .67, 1.58, 8.6, .5, size=28, color=ICE)
s.textbox("Dalla preselezione dei dati alle asimmetrie del fascio", .67, 2.23, 8.4, .7, size=20)
s.textbox("Campagna locale UV/VIS · 6 ottobre 2026", .67, 4.67, 8.6, .3, size=13, color=ICE)
slides.append(s)

s = standard("La domanda fisica", 2, "wiki/scientific-foundations.md; Ajaka et al. (2008)")
s.textbox("γ p  →  p η π⁰", .74, 1.28, 8.5, .64, size=40, color=BLUE, bold=True)
s.textbox("η → γγ     π⁰ → γγ", .77, 2.02, 7.7, .38, size=24)
s.textbox("Misura: asimmetria del fascio Σ nelle tre masse invarianti\npπ⁰, pη ed ηπ⁰.", .77, 2.8, 8.3, 1.0, size=21)
s.textbox("Benchmark sperimentale: punti pubblicati da Ajaka et al. (2008).", .77, 4.25, 8.35, .44, size=18, color=MUTED)
slides.append(s)

s = standard("Dal Fortran ai file ROOT", 3, "wiki/01-pre-analysis.md; 01_pre_analysis/PreAnalysis.C")
s.textbox("01", .72, 1.3, 1.05, .63, size=42, color=BLUE, bold=True)
s.textbox("Eredità Fortran", 1.82, 1.36, 6.9, .35, size=22, bold=True)
s.textbox("Tree grezzo h70 e convenzioni storiche, incluso indice Fortran da 1.", 1.82, 1.78, 7.4, .53, size=18)
s.textbox("02", .72, 2.65, 1.05, .63, size=42, color=BLUE, bold=True)
s.textbox("Pre-analisi C++/ROOT", 1.82, 2.7, 6.9, .35, size=22, bold=True)
s.textbox("PreAnalysis.C costruisce beam, candidati particella e metadati per run.", 1.82, 3.12, 7.4, .53, size=18)
s.textbox("03", .72, 4.0, 1.05, .63, size=42, color=BLUE, bold=True)
s.textbox("Output normalizzato", 1.82, 4.05, 6.9, .35, size=22, bold=True)
s.textbox("Un file ROOT h80 per periodo, pronto per preselezione e calibrazione.", 1.82, 4.47, 7.4, .53, size=18)
slides.append(s)

s = standard("Preselezione dei dati", 4, "wiki/02-event-selection.md; wiki/05-reconstruction.md")
s.textbox("h80", .78, 1.34, 2.1, .62, size=44, color=BLUE, bold=True)
s.textbox("h85", 6.9, 1.34, 2.1, .62, size=44, color=BLUE, bold=True, align="r")
s.textbox("Filtro topologico", .78, 2.27, 8.4, .4, size=22, bold=True)
s.textbox("Più di un fotone centrale e un solo track carico in avanti.", .78, 2.75, 8.3, .6, size=20)
s.textbox("Run, polarizzazione e strip del tagger restano nei dati selezionati.\nIpotesi pηπ⁰, accoppiamento dei fotoni e fit arrivano dopo.", .78, 3.75, 8.4, 1.0, size=18, color=MUTED)
slides.append(s)

s = Slide("Un framework di analisi", 5, dark=True, source="wiki/workflow.md")
s.textbox("Un framework di analisi", .65, .4, 8.8, .56, size=32, bold=True)
s.textbox("01  Dati ROOT e preselezione", .75, 1.30, 8.1, .43, size=24)
s.textbox("02  MC e BDT", .75, 2.08, 8.1, .43, size=24)
s.textbox("03  Ricostruzione e calibrazione", .75, 2.86, 8.1, .43, size=24)
s.textbox("04  Estrazione di Σ e controlli", .75, 3.64, 8.1, .43, size=24)
s.textbox("Contratti di file e ipotesi condivise rendono il flusso riutilizzabile.", .75, 4.62, 8.5, .4, size=17, color=ICE)
s.textbox("05", 9.08, 5.27, .3, .2, size=9, color=ICE, align="r")
slides.append(s)

s = standard("Ricostruzione pηπ⁰", 6, "wiki/scientific-foundations.md; wiki/05-reconstruction.md")
s.textbox("Percorso standard", .76, 1.3, 3.85, .36, size=22, color=BLUE, bold=True)
s.textbox("Accoppiamento dei 4 fotoni con χ² sulle masse η e π⁰.", .76, 1.75, 3.95, 1.05, size=19)
s.textbox("Percorso con BDT", 5.0, 1.3, 4.15, .36, size=22, color=BLUE, bold=True)
s.textbox("Filtro di fondo a monte; stessa ricostruzione dopo il gate.", 5.0, 1.75, 4.15, 1.05, size=19)
s.textbox("6C", .76, 3.28, 1.8, .7, size=46, color=BLUE, bold=True)
s.textbox("Fit cinematico vincolato come controllo della qualità del candidato.", 2.45, 3.39, 6.68, .8, size=20)
s.textbox("Differenza tra campioni: solo filtro BDT, non logica di pairing o fit.", .76, 4.56, 8.4, .36, size=17, color=MUTED)
slides.append(s)

s = standard("Nuovo MC senza vecchio G3", 7, "wiki/03-monte-carlo-simulation.md; 03_mc_simulation/generators/smearing.h")
s.textbox("ROOT TGenPhaseSpace", .75, 1.33, 8.6, .47, size=27, color=BLUE, bold=True)
s.textbox("Generazione non pesata dalla soglia fisica; beam fino a 1,75 GeV nel set esteso.", .75, 1.9, 8.45, .88, size=19)
s.textbox("Smearing parametrico", .75, 3.1, 8.4, .4, size=23, color=BLUE, bold=True)
s.textbox("Energia e direzione di fotoni e protoni; tagger con FWHM 16 MeV.", .75, 3.58, 8.45, .7, size=19)
s.textbox("MC autonomo dal vecchio Geant3; accettanza semplificata, non simulazione completa del rivelatore.", .75, 4.55, 8.5, .5, size=16, color=MUTED)
slides.append(s)

s = standard("Nove canali simulati", 8, "wiki/physics-channels.md; wiki/03-monte-carlo-simulation.md")
s.textbox("Segnale", .75, 1.24, 2.5, .34, size=20, color=BLUE, bold=True)
s.textbox("ηπ⁰", .75, 1.69, 2.6, .48, size=30, bold=True)
s.textbox("Fondi storici e nuovi", 3.48, 1.24, 5.1, .34, size=20, color=BLUE, bold=True)
s.textbox("π⁰π⁰     3π⁰     4π⁰\nη → 3π⁰     ηπ⁰ con η → 3π⁰\nη2π⁰     ωπ⁰     η′", 3.48, 1.7, 5.5, 1.75, size=20)
s.textbox("VIS: sei canali con soglia ≤ 1,10 GeV.", .75, 3.85, 8.4, .4, size=22, color=BLUE, bold=True)
s.textbox("η2π⁰, ωπ⁰ ed η′ restano fuori dall'intervallo VIS per soglia fisica.", .75, 4.38, 8.6, .56, size=17, color=MUTED)
slides.append(s)

s = standard("BDT: idea e ingressi", 9, "wiki/04-bdt-training.md; artifacts/stage1")
s.textbox("BDT", .75, 1.18, 3.2, .73, size=50, color=BLUE, bold=True)
s.textbox("Classificatore XGBoost: distingue segnale MC e fondi prima del χ².", .75, 2.02, 4.0, 1.03, size=19)
s.textbox("26 feature: masse γγ, quantità mancanti, energia, angoli e protone.", .75, 3.15, 4.0, 1.12, size=18)
s.image("score_uv.png", 4.95, 1.28, 4.25, 3.5)
slides.append(s)

s = standard("Dal MC ai dati", 10, "wiki/04-bdt-training.md; wiki/05-stage1-gate.md")
s.textbox("1", .78, 1.28, .55, .59, size=42, color=BLUE, bold=True)
s.textbox("Spettro reale del beam e pesi dei canali", 1.5, 1.34, 7.4, .5, size=21)
s.textbox("2", .78, 2.32, .55, .59, size=42, color=BLUE, bold=True)
s.textbox("Accettanza, perdita di fotoni e 4 γ osservati", 1.5, 2.38, 7.4, .5, size=21)
s.textbox("3", .78, 3.36, .55, .59, size=42, color=BLUE, bold=True)
s.textbox("Training UV e VIS separati; soglia validata", 1.5, 3.42, 7.4, .5, size=21)
s.textbox("4", .78, 4.4, .55, .59, size=42, color=BLUE, bold=True)
s.textbox("Gate applicato ai dati, poi pairing e fit condivisi", 1.5, 4.46, 7.4, .5, size=21)
slides.append(s)

s = standard("Prestazioni BDT", 11, "results/test_data/uv|vis/bdt/artifacts/stage1/stage1_metrics.txt")
s.textbox("UV  AUC 0,9975", .84, 1.22, 4.0, .4, size=22, color=BLUE, bold=True)
s.textbox("VIS  AUC 0,9995", 5.13, 1.22, 4.0, .4, size=22, color=BLUE, bold=True)
s.image("roc_uv.png", .69, 1.75, 4.38, 2.72)
s.image("roc_vis.png", 5.0, 1.75, 4.38, 2.72)
s.textbox("Validazione su MC nella campagna locale; AUC non equivale a purezza misurata sui dati.", .76, 4.63, 8.5, .47, size=15.5, color=MUTED)
slides.append(s)

s = standard("Calibrazione dei flussi", 12, "wiki/06-calibration.md; config/run_manifest.csv")
s.textbox("Run manifest", .76, 1.33, 2.8, .4, size=23, color=BLUE, bold=True)
s.textbox("Classifica run, target, UV/VIS e stato di polarizzazione.", .76, 1.83, 8.25, .57, size=19)
s.textbox("h80 + flux ROOT", .76, 2.67, 3.65, .4, size=23, color=BLUE, bold=True)
s.textbox("Associa strip ed energia; calibra POL1, POL2 e BREM per run.", .76, 3.17, 8.25, .57, size=19)
s.textbox("flux_calibrated.root", .76, 4.02, 5.8, .42, size=25, color=BLUE, bold=True)
s.textbox("Esporre solo run completi: POL1, POL2 e BREM presenti.", .76, 4.53, 8.25, .45, size=18)
slides.append(s)

s = standard("Estrazione dell'asimmetria", 13, "wiki/07-beam-asymmetry-estimators.md")
s.textbox("Σ", .75, 1.20, 1.2, .86, size=60, color=BLUE, bold=True)
s.textbox("Modulazione azimutale con fascio polarizzato linearmente", 1.9, 1.31, 7.25, .88, size=22)
s.textbox("R(φ) = (yV − yH) / (PH yV + PV yH)", .77, 2.75, 8.5, .52, size=27, color=BLUE, bold=True)
s.textbox("yV = NV / FV       yH = NH / FH", .79, 3.36, 8.3, .4, size=21)
s.textbox("Fit: R(φ) = Σ cos(2φ)     ·     likelihood condizionale come cross-check", .78, 4.26, 8.55, .59, size=18)
slides.append(s)

s = standard("Prime asimmetrie UV", 14, "results/test_data/combined/figure4_experimental.pdf; run locale")
s.textbox("1,30–1,40 GeV · tre sottosistemi", .78, 1.13, 8.45, .38, size=19, color=BLUE, bold=True)
s.image("sigma_uv.png", .58, 1.63, 8.9, 2.48)
s.textbox("Struttura in pη; risultati locali da sottoporre ai controlli sistematici.", .78, 4.38, 8.45, .55, size=18)
slides.append(s)

s = standard("Confronto con Ajaka", 15, "Ajaka et al. (2008); digitizzazione versionata; run locale")
s.textbox("1,40–1,50 GeV · nero: questa analisi · rosso: Ajaka et al.", .77, 1.12, 8.5, .38, size=18, color=BLUE, bold=True)
s.image("ajaka_uv.png", .58, 1.58, 8.9, 2.48)
s.textbox("Confronto punto per punto: compatibilità e scarti dipendono dal sottosistema e dalla massa.", .77, 4.35, 8.48, .64, size=17)
slides.append(s)

s = standard("VIS vicino alla soglia", 16, "results/test_data/combined/figure4_experimental.pdf; run locale")
s.textbox("0,9313–1,10 GeV: prima riga aggiunta alla figura combinata", .78, 1.1, 8.5, .48, size=20, color=BLUE, bold=True)
s.image("sigma_vis.png", .57, 1.66, 8.9, 2.47)
s.textbox("Le asimmetrie estratte non sono uniformemente nulle: pη e ηπ⁰ mostrano modulazione.", .78, 4.38, 8.45, .57, size=18)
slides.append(s)

s = standard("Una finestra fisica nuova", 17, "wiki/compton-beam-and-polarization.md; ipotesi da verificare")
s.textbox("VIS: polarizzazione alta", .76, 1.26, 4.35, .43, size=23, color=BLUE, bold=True)
s.textbox("Vicino al bordo Compton arriva quasi al 100%; nell'intero intervallo 0,93–1,10 GeV varia con Eγ.", .76, 1.79, 4.17, 1.07, size=17.5)
s.textbox("Ipotesi fisica", .76, 3.26, 4.1, .38, size=22, color=BLUE, bold=True)
s.textbox("Anche vicino alla soglia, code di risonanze larghe e intense possono interferire e produrre Σ non piatta.", .76, 3.74, 4.18, 1.15, size=17.5)
s.image("polarization.png", 5.0, 1.27, 4.21, 3.59)
slides.append(s)

s = standard("Verifiche ancora aperte", 18, "wiki/known-limitations.md; direttive del progetto")
s.textbox("01", .77, 1.25, .8, .47, size=31, color=BLUE, bold=True)
s.textbox("Confrontare flussi e Σ con mergedateu e wnorm.", 1.55, 1.30, 7.55, .53, size=20)
s.textbox("02", .77, 2.18, .8, .47, size=31, color=BLUE, bold=True)
s.textbox("Misurare asimmetria del fondo nelle sideband.", 1.55, 2.23, 7.55, .53, size=20)
s.textbox("03", .77, 3.11, .8, .47, size=31, color=BLUE, bold=True)
s.textbox("Iniettare Σ piatta nel MC e rieseguire tutta la catena.", 1.55, 3.16, 7.55, .53, size=20)
s.textbox("04", .77, 4.04, .8, .47, size=31, color=BLUE, bold=True)
s.textbox("Quantificare sistematiche prima di un risultato finale.", 1.55, 4.09, 7.55, .53, size=20)
slides.append(s)

s = Slide("Prossimi passi", 19, dark=True)
s.textbox("Prossimi passi", .66, .4, 8.8, .55, size=33, bold=True)
s.textbox("Sezioni d'urto", .75, 1.27, 4.1, .4, size=22, color=ICE, bold=True)
s.textbox("Differenziali e totali", .75, 1.72, 4.1, .4, size=18)
s.textbox("Primo paper", 5.03, 1.27, 4.1, .4, size=22, color=ICE, bold=True)
s.textbox("Framework e risultati originali; sede di fisica da valutare.", 5.03, 1.72, 4.1, .88, size=18)
s.textbox("Nuovi canali", .75, 2.85, 4.1, .4, size=22, color=ICE, bold=True)
s.textbox("Riutilizzare il framework oltre pηπ⁰.", .75, 3.30, 4.1, .75, size=18)
s.textbox("Dalitz e teoria", 5.03, 2.85, 4.1, .4, size=22, color=ICE, bold=True)
s.textbox("Dalitz plot non studiati prima; modelli teorici in corso.", 5.03, 3.30, 4.1, .9, size=18)
s.textbox("Controlli delle sideband e del MC piatto prima della pubblicazione.", .75, 4.66, 8.5, .43, size=16, color=ICE)
s.textbox("19", 9.08, 5.27, .3, .2, size=9, color=ICE, align="r")
slides.append(s)

assert len(slides) == 19


def build():
    with tempfile.TemporaryDirectory() as td:
        temp = Path(td)
        md = temp / "stub.md"
        md.write_text("\n\n".join(f"# {s.title}\n" for s in slides), encoding="utf-8")
        base = temp / "base.pptx"
        subprocess.run(["pandoc", str(md), "-t", "pptx", "--slide-level=1", "-o", str(base)], check=True)
        with zipfile.ZipFile(base) as inp:
            members = {name: inp.read(name) for name in inp.namelist()}
        # Pandoc's default reference includes an orphan second theme.
        members.pop("ppt/theme/theme2.xml", None)
        for s in slides:
            xml, rels = s.render()
            members[f"ppt/slides/slide{s.number}.xml"] = xml
            members[f"ppt/slides/_rels/slide{s.number}.xml.rels"] = rels
            for path in s.pictures:
                members[f"ppt/media/graal_slide{s.number}_{path.name}"] = path.read_bytes()
        types = etree.fromstring(members["[Content_Types].xml"])
        for node in list(types):
            if node.get("PartName") == "/ppt/theme/theme2.xml":
                types.remove(node)
        extensions = {node.get("Extension") for node in types.findall(f"{{{CT}}}Default")}
        if "png" not in extensions:
            types.append(e(CT, "Default", Extension="png", ContentType="image/png"))
        members["[Content_Types].xml"] = etree.tostring(types, xml_declaration=True, encoding="UTF-8")
        with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as out:
            for name, data in members.items():
                out.writestr(name, data)
    print(OUT)


if __name__ == "__main__":
    build()
