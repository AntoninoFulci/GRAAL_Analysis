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
BAR_BLUE = "0877C7"
SLIDE_COUNT = 19
CONTENT_FONT_SCALE = 0.86


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

    def rect(self, x: float, y: float, w: float, h: float, color: str):
        sp = e(P, "sp")
        nv = e(P, "nvSpPr")
        nv.append(e(P, "cNvPr", id=self._id, name=f"Fill {self._id}"))
        nv.append(e(P, "cNvSpPr"))
        nv.append(e(P, "nvPr"))
        sp.append(nv)
        pr = e(P, "spPr")
        xf = e(A, "xfrm")
        xf.append(e(A, "off", x=round(x * EMU), y=round(y * EMU)))
        xf.append(e(A, "ext", cx=round(w * EMU), cy=round(h * EMU)))
        pr.append(xf)
        geom = e(A, "prstGeom", prst="rect")
        geom.append(e(A, "avLst"))
        pr.append(geom)
        fill = e(A, "solidFill")
        fill.append(e(A, "srgbClr", val=color))
        pr.append(fill)
        line = e(A, "ln")
        line.append(e(A, "noFill"))
        pr.append(line)
        sp.append(pr)
        self.shapes.append(sp)
        self._id += 1

    def textbox(self, text: str, x: float, y: float, w: float, h: float, *,
                size: float = 20, color: str | None = None, bold: bool = False,
                align: str = "l", italic: bool = False, valign: str = "t"):
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
        body.append(e(A, "bodyPr", wrap="square", lIns="0", rIns="0", tIns="0", bIns="0", anchor=valign))
        body.append(e(A, "lstStyle"))
        for line in text.split("\n"):
            para = e(A, "p")
            para.append(e(A, "pPr", algn=align))
            run = e(A, "r")
            # Keep labels and footnotes legible while reducing oversized content text.
            rendered_size = size * CONTENT_FONT_SCALE if size > 15 else size
            props = e(A, "rPr", lang="it-IT", sz=round(rendered_size * 100), b="1" if bold else "0", i="1" if italic else "0")
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
        s.textbox("Fonte: " + source, .64, 5.08, 8.7, .16, size=8.5, color=MUTED)
    return s


def add_navigation(s: Slide):
    sections = (
        "INTRO", "INTRO", "DATI", "DATI", "FRAMEWORK", "RICOSTRUZIONE",
        "MONTE CARLO", "MONTE CARLO", "BDT", "BDT", "BDT", "CALIBRAZIONE",
        "ASIMMETRIE", "RISULTATI", "RISULTATI", "RISULTATI", "INTERPRETAZIONE",
        "VERIFICHE", "PROSPETTIVE",
    )
    h = .285
    # Header and footer share the same section cue and page counter.
    s.rect(0, 0, 10, h, NAVY)
    s.rect(0, 0, 10 * s.number / SLIDE_COUNT, h, BAR_BLUE)
    s.textbox("GRAAL ANALYSIS", .62, 0, 5.4, h, size=9, color=WHITE,
              bold=True, valign="ctr")
    s.textbox(f"{s.number:02d}/{SLIDE_COUNT:02d}", 8.84, 0, .54, h,
              size=10, color=WHITE, bold=True, align="r", valign="ctr")
    y = 5.34
    s.rect(0, y, 10, h, NAVY)
    s.rect(0, y, 10 * s.number / SLIDE_COUNT, h, BAR_BLUE)
    s.textbox(sections[s.number - 1], .62, y, 5.6, h, size=9, color=WHITE,
              bold=True, valign="ctr")
    s.textbox(f"{s.number:02d}/{SLIDE_COUNT:02d}", 8.84, y, .54, h,
              size=10, color=WHITE, bold=True, align="r", valign="ctr")


slides: list[Slide] = []

s = Slide("GRAAL Analysis", 1, dark=True)
s.textbox("GRAAL Analysis", .67, .67, 8.5, .78, size=50, bold=True)
s.textbox("γp → pηπ⁰", .70, 2.05, 6.15, .92, size=48, color=ICE, bold=True)
s.textbox("Σ", 7.00, 1.35, 2.3, 2.65, size=164, color=BAR_BLUE, bold=True, align="r")
s.textbox("6 ottobre 2026", .72, 4.76, 8.6, .28, size=13, color=ICE)
slides.append(s)

s = standard("La domanda fisica", 2, "wiki/scientific-foundations.md; Ajaka et al. (2008)")
s.textbox("γ p  →  p η π⁰", .74, 1.28, 8.5, .64, size=40, color=BLUE, bold=True)
s.textbox("η → γγ     π⁰ → γγ", .77, 2.02, 7.7, .38, size=24)
s.textbox("Negli eventi cerchiamo quattro fotoni e un protone di rinculo.", .77, 2.66, 8.4, .49, size=20)
s.textbox("Σ in pπ⁰, pη ed ηπ⁰", .77, 3.40, 8.3, .42, size=23, color=BLUE, bold=True)
s.textbox("UV: 1,10–1,50 GeV · VIS: 0,9313–1,10 GeV", .77, 3.93, 8.5, .38, size=19)
s.textbox("Usiamo i risultati di Ajaka et al. (2008) per verificare l'analisi.", .77, 4.48, 8.45, .4, size=17, color=MUTED)
slides.append(s)

s = standard("Dal Fortran ai file ROOT", 3, "wiki/01-pre-analysis.md; 01_pre_analysis/PreAnalysis.C")
s.textbox("01", .72, 1.22, 1.05, .63, size=40, color=BLUE, bold=True)
s.textbox("Eredità Fortran", 1.82, 1.24, 6.9, .35, size=22, bold=True)
s.textbox("Il formato h70 conserva gli array e i metadati originali. Nel passaggio\na C++, l'indice forward passa dalla base 1 alla base 0.", 1.82, 1.65, 7.4, .69, size=17)
s.textbox("02", .72, 2.51, 1.05, .63, size=40, color=BLUE, bold=True)
s.textbox("Pre-analisi C++/ROOT", 1.82, 2.53, 6.9, .35, size=22, bold=True)
s.textbox("PreAnalysis.C applica i criteri PID del singolo run e ricostruisce\nfascio, fotoni, tracce cariche e polarizzazione.", 1.82, 2.93, 7.4, .69, size=17)
s.textbox("03", .72, 3.8, 1.05, .63, size=40, color=BLUE, bold=True)
s.textbox("Output normalizzato", 1.82, 3.82, 6.9, .35, size=22, bold=True)
s.textbox("Otteniamo un file ROOT h80 per periodo. La preselezione produce h85,\nmentre RunNumber e Xstrip conservano il legame con la calibrazione.", 1.82, 4.22, 7.4, .69, size=17)
slides.append(s)

s = standard("Preselezione dei dati", 4, "wiki/02-event-selection.md; wiki/05-reconstruction.md")
s.textbox("h80", .78, 1.20, 2.1, .62, size=44, color=BLUE, bold=True)
s.textbox("h85", 6.9, 1.20, 2.1, .62, size=44, color=BLUE, bold=True, align="r")
s.textbox("Applichiamo un filtro topologico con ROOT RDataFrame", .78, 2.02, 8.4, .4, size=22, bold=True)
s.textbox("gammas.size() > 1  &&  fcharged_theta.size() == 1", .78, 2.55, 8.5, .5, size=21, color=BLUE)
s.textbox("In questa fase bastano almeno due fotoni. I quattro fotoni dello stato finale vengono richiesti più avanti.", .78, 3.33, 8.5, .51, size=19)
s.textbox("Il tree h85 conserva tutti i rami. RunNumber, Polarization e Xstrip\naccompagnano ogni evento nella ricostruzione e nella calibrazione.", .78, 4.02, 8.45, .77, size=17.5, color=MUTED)
slides.append(s)

s = Slide("Un framework di analisi", 5, dark=True, source="wiki/workflow.md")
s.textbox("Un framework di analisi", .65, .4, 8.8, .56, size=32, bold=True)
s.textbox("01  Dai dati grezzi alla preselezione", .75, 1.18, 8.1, .4, size=23)
s.textbox("I file h70, h80 e h85 mantengono i metadati di run e polarizzazione.", 1.34, 1.59, 7.75, .3, size=16, color=ICE)
s.textbox("02  Simulazione e selezione BDT", .75, 2.05, 8.1, .4, size=23)
s.textbox("Simuliamo nove canali e alleniamo modelli distinti per UV e VIS.", 1.34, 2.46, 7.75, .3, size=16, color=ICE)
s.textbox("03  Ricostruzione e flussi", .75, 2.92, 8.1, .4, size=23)
s.textbox("Usiamo lo stesso pairing e calibriamo i flussi POL1, POL2 e BREM.", 1.34, 3.33, 7.75, .3, size=16, color=ICE)
s.textbox("04  Asimmetrie e verifiche", .75, 3.79, 8.1, .4, size=23)
s.textbox("Estraiamo Σ nei tre sottosistemi e confrontiamo i risultati con Ajaka.", 1.34, 4.20, 7.75, .3, size=16, color=ICE)
s.textbox("La stessa catena di analisi potrà essere applicata ad altri canali.", .75, 4.80, 8.5, .28, size=15, color=ICE)
slides.append(s)

s = standard("Ricostruzione pηπ⁰", 6, "wiki/scientific-foundations.md; wiki/05-reconstruction.md")
s.textbox("3 partizioni", .76, 1.22, 4.0, .4, size=24, color=BLUE, bold=True)
s.textbox("Con quattro fotoni possiamo formare tre coppie disgiunte e sei possibili assegnazioni a η e π⁰.", .76, 1.71, 4.05, 1.1, size=18)
s.textbox("χ² minimo", 5.00, 1.22, 4.0, .4, size=24, color=BLUE, bold=True)
s.textbox("Scegliamo l'assegnazione più vicina alle masse nominali e richiediamo χ² < 10.", 5.00, 1.71, 4.02, 1.1, size=18)
s.textbox("Due campioni confrontabili", .76, 3.08, 8.2, .43, size=23, color=BLUE, bold=True)
s.textbox("Nel campione standard usiamo il pairing χ². Nel campione BDT filtriamo prima sullo score, poi applichiamo lo stesso pairing e gli stessi criteri.", .76, 3.60, 8.44, .73, size=19)
s.textbox("Il modello e la ricostruzione usano le stesse ipotesi sulle masse e lo stesso codice di pairing.", .76, 4.53, 8.44, .44, size=17, color=MUTED)
slides.append(s)

s = standard("Simulazione Monte Carlo senza G3", 7, "wiki/03-monte-carlo-simulation.md; 03_mc_simulation/generators/smearing.h")
s.textbox("Generazione", .75, 1.20, 4.0, .37, size=22, color=BLUE, bold=True)
s.textbox("Generiamo eventi non pesati con ROOT TGenPhaseSpace. La soglia deriva dalle masse dei prodotti finali.", .75, 1.62, 8.46, .72, size=18.5)
s.textbox("Finestra energetica", .75, 2.51, 4.1, .37, size=22, color=BLUE, bold=True)
s.textbox("Il campione esteso arriva a 1,75 GeV. Per VIS produciamo un campione dedicato tra la soglia fisica, o 0,9313 GeV se più alta, e 1,10 GeV.", .75, 2.94, 8.45, .75, size=18.5)
s.textbox("Risposta strumentale", .75, 3.84, 4.7, .37, size=22, color=BLUE, bold=True)
s.textbox("Applichiamo lo smearing a fotoni, protone e tagger (FWHM 16 MeV), con un'accettanza semplificata. La simulazione non usa il vecchio G3.", .75, 4.26, 8.46, .72, size=17.5)
slides.append(s)

s = standard("Nove canali simulati", 8, "wiki/physics-channels.md; wiki/03-monte-carlo-simulation.md")
s.textbox("Segnale", .75, 1.16, 2.5, .34, size=20, color=BLUE, bold=True)
s.textbox("ηπ⁰", .75, 1.55, 2.6, .48, size=30, bold=True)
s.textbox("Canali di fondo storici e nuovi", 3.28, 1.16, 5.6, .34, size=20, color=BLUE, bold=True)
s.textbox("π⁰π⁰    3π⁰    4π⁰\nη → 3π⁰    ηπ⁰ con η → 3π⁰\nη2π⁰    ωπ⁰    η′", 3.28, 1.58, 5.8, 1.63, size=20)
s.textbox("VIS: 6/9 canali", .75, 3.36, 8.4, .4, size=23, color=BLUE, bold=True)
s.textbox("ηπ⁰, π⁰π⁰, 3π⁰, 4π⁰, η → 3π⁰, ηπ⁰ con η → 3π⁰.", .75, 3.83, 8.5, .48, size=18)
s.textbox("Le soglie di η2π⁰, ωπ⁰ ed η′ superano 1,10 GeV. Questi canali restano nel catalogo UV, ma non nel campione VIS.", .75, 4.46, 8.5, .50, size=16.5, color=MUTED)
slides.append(s)

s = standard("Come funziona il BDT", 9, "wiki/04-bdt-training.md; artifacts/stage1")
s.textbox("BDT", .75, 1.14, 3.2, .73, size=49, color=BLUE, bold=True)
s.textbox("Alleniamo XGBoost sul MC per distinguere il segnale dai canali di fondo.", .75, 1.99, 4.03, .82, size=19)
s.textbox("Il modello usa 26 variabili, tra cui masse γγ, massa mancante, energia e angoli. Le calcoliamo allo stesso modo anche sui dati.", .75, 2.94, 4.08, 1.13, size=17.5)
s.textbox("Nel training bilanciamo le classi e rimescoliamo l'ordine dei fotoni, così il modello non impara scorciatoie spurie.", .75, 4.12, 4.05, .80, size=16.5, color=MUTED)
s.image("score_uv.png", 4.94, 1.18, 4.30, 3.77)
slides.append(s)

s = standard("Dal MC ai dati", 10, "wiki/04-bdt-training.md; wiki/05-stage1-gate.md")
s.textbox("1", .78, 1.18, .55, .59, size=39, color=BLUE, bold=True)
s.textbox("Spettro misurato e pesi", 1.5, 1.19, 7.4, .4, size=21, bold=True)
s.textbox("Pesiamo il MC con il flusso del tagger, la sezione d'urto e l'accettanza.", 1.5, 1.59, 7.43, .37, size=16.5)
s.textbox("2", .78, 2.14, .55, .59, size=39, color=BLUE, bold=True)
s.textbox("Quattro fotoni osservati", 1.5, 2.15, 7.4, .4, size=21, bold=True)
s.textbox("Applichiamo a segnale e fondi la perdita di fotoni e il loro rimescolamento.", 1.5, 2.55, 7.43, .37, size=16.5)
s.textbox("3", .78, 3.10, .55, .59, size=39, color=BLUE, bold=True)
s.textbox("Due modelli per UV e VIS", 1.5, 3.11, 7.4, .4, size=21, bold=True)
s.textbox("Per ogni regione salviamo insieme il modello, la soglia e la provenienza.", 1.5, 3.51, 7.43, .37, size=16.5)
s.textbox("4", .78, 4.06, .55, .59, size=39, color=BLUE, bold=True)
s.textbox("Selezione dei dati", 1.5, 4.07, 7.4, .4, size=21, bold=True)
s.textbox("Dopo il filtro BDT, ricostruiamo gli eventi con la stessa ipotesi e lo stesso pairing χ².", 1.5, 4.47, 7.43, .37, size=16.5)
slides.append(s)

s = standard("Risultati del BDT", 11, "results/test_data/uv|vis/bdt/artifacts/stage1/stage1_metrics.txt")
s.textbox("UV  AUC 0,9975", .84, 1.13, 4.0, .4, size=22, color=BLUE, bold=True)
s.textbox("VIS  AUC 0,9995", 5.13, 1.13, 4.0, .4, size=22, color=BLUE, bold=True)
s.image("roc_uv.png", .69, 1.57, 4.38, 2.72)
s.image("roc_vis.png", 5.0, 1.57, 4.38, 2.72)
s.textbox("F1 0,9842 · soglia 0,1233", .81, 4.30, 4.12, .32, size=16, color=INK)
s.textbox("F1 0,9956 · soglia 0,0740", 5.10, 4.30, 4.12, .32, size=16, color=INK)
s.textbox("Queste metriche vengono dal MC di prova: l'AUC non indica la purezza del campione reale.", .76, 4.74, 8.5, .25, size=14.5, color=MUTED)
slides.append(s)

s = standard("Calibrazione dei flussi", 12, "wiki/06-calibration.md; config/run_manifest.csv")
s.textbox("Run manifest", .76, 1.16, 3.6, .4, size=23, color=BLUE, bold=True)
s.textbox("Il manifest assegna a ogni run il target, la regione UV o VIS e lo stato di polarizzazione.", .76, 1.59, 8.25, .45, size=18)
s.textbox("h80 + flux ROOT", .76, 2.19, 4.2, .4, size=23, color=BLUE, bold=True)
s.textbox("Calibriamo l'energia delle strip 1–128 con la mediana misurata per run e polarizzazione.", .76, 2.62, 8.25, .48, size=18)
s.textbox("POL1 · POL2 · BREM", .76, 3.25, 6.9, .4, size=23, color=BLUE, bold=True)
s.textbox("Per usare un run servono tutti e tre i flussi. Se ne manca uno, escludiamo il run.", .76, 3.68, 8.25, .45, size=18)
s.textbox("flux_calibrated.root", .76, 4.34, 6.0, .42, size=25, color=BLUE, bold=True)
s.textbox("Il file finale conserva gli assi energetici calibrati e viene scritto in modo atomico.", .76, 4.75, 8.2, .27, size=16, color=MUTED)
slides.append(s)

s = standard("Estrazione dell'asimmetria", 13, "wiki/07-beam-asymmetry-estimators.md")
s.textbox("Σ", .75, 1.12, 1.2, .86, size=60, color=BLUE, bold=True)
s.textbox("Con un fascio polarizzato linearmente, Σ descrive la modulazione azimutale.", 1.9, 1.23, 7.25, .88, size=22)
s.textbox("R(φ) = (yV − yH) / (PH yV + PV yH)", .77, 2.34, 8.5, .52, size=27, color=BLUE, bold=True)
s.textbox("yV = NV / FV       yH = NH / FH", .79, 2.93, 8.3, .4, size=21)
s.textbox("Ricaviamo Σ dalla componente cos(2φ) di R(φ).", .78, 3.59, 8.55, .46, size=20)
s.textbox("Controlliamo il risultato con una likelihood condizionale e usiamo flussi e polarizzazioni specifici di run e strip.", .78, 4.13, 8.55, .46, size=17.5)
s.textbox("L'analisi usa 12 intervalli in φ e 10 in massa per ciascuno dei tre sottosistemi.", .78, 4.68, 8.55, .28, size=15.5, color=MUTED)
slides.append(s)

s = standard("Prime asimmetrie UV", 14, "results/test_data/combined/figure4_experimental.pdf; run locale")
s.textbox("1,30–1,40 GeV · pπ⁰, pη, ηπ⁰", .78, 1.10, 8.45, .38, size=19, color=BLUE, bold=True)
s.image("sigma_uv.png", .54, 1.51, 8.98, 2.74)
s.textbox("Nel sottosistema pη osserviamo valori negativi in diversi intervalli di massa. La figura mostra solo gli errori statistici.", .78, 4.43, 8.45, .53, size=17)
slides.append(s)

s = standard("Confronto con Ajaka", 15, "Ajaka et al. (2008); digitizzazione versionata; run locale")
s.textbox("Tra 1,40 e 1,50 GeV: questa analisi in nero, Ajaka et al. in rosso", .77, 1.09, 8.5, .38, size=18, color=BLUE, bold=True)
s.image("ajaka_uv.png", .54, 1.49, 8.98, 2.75)
s.textbox("L'accordo cambia con la massa e con il sottosistema. Servono ancora controlli sistematici prima di trarre conclusioni quantitative.", .77, 4.42, 8.48, .54, size=16.5)
slides.append(s)

s = standard("VIS vicino alla soglia", 16, "results/test_data/combined/figure4_experimental.pdf; run locale")
s.textbox("Abbiamo esteso la figura combinata alla regione 0,9313–1,10 GeV", .78, 1.08, 8.5, .48, size=20, color=BLUE, bold=True)
s.image("sigma_vis.png", .54, 1.56, 8.98, 2.73)
s.textbox("Nel campione VIS, Σ tende a valori negativi per pη e diventa positiva in alcuni intervalli di ηπ⁰. Il risultato è preliminare.", .78, 4.45, 8.45, .51, size=16.5)
slides.append(s)

s = standard("Perché il VIS è interessante", 17, "wiki/compton-beam-and-polarization.md; ipotesi da verificare")
s.textbox("VIS: polarizzazione alta", .76, 1.17, 4.35, .43, size=23, color=BLUE, bold=True)
s.textbox("Con il laser a 514 nm, la polarizzazione si avvicina al 100% al bordo Compton. Nella regione VIS dipende dall'energia del fotone.", .76, 1.66, 4.17, 1.05, size=17.5)
s.textbox("Ipotesi fisica", .76, 2.99, 4.1, .38, size=22, color=BLUE, bold=True)
s.textbox("Anche vicino alla soglia, le code di risonanze ampie e intense possono interferire tra loro e produrre un'asimmetria che varia con la massa.", .76, 3.41, 4.18, 1.06, size=17.5)
s.textbox("Stiamo verificando questa interpretazione con i modelli teorici.", .76, 4.58, 4.17, .40, size=15.5, color=MUTED)
s.image("polarization.png", 5.0, 1.17, 4.21, 3.80)
slides.append(s)

s = standard("Verifiche ancora aperte", 18, "wiki/known-limitations.md; direttive del progetto")
s.textbox("01", .77, 1.17, .8, .47, size=29, color=BLUE, bold=True)
s.textbox("Codici storici: mergedateu e wnorm", 1.55, 1.19, 7.55, .40, size=19.5, bold=True)
s.textbox("Confronteremo flussi calibrati e Σ per ogni run e intervallo di energia.", 1.55, 1.58, 7.55, .33, size=16)
s.textbox("02", .77, 2.13, .8, .47, size=29, color=BLUE, bold=True)
s.textbox("Asimmetria del fondo", 1.55, 2.15, 7.55, .40, size=19.5, bold=True)
s.textbox("Misureremo la modulazione nelle sideband di massa per controllare il fondo.", 1.55, 2.54, 7.55, .33, size=16)
s.textbox("03", .77, 3.09, .8, .47, size=29, color=BLUE, bold=True)
s.textbox("MC con Σ piatta iniettata", 1.55, 3.11, 7.55, .40, size=19.5, bold=True)
s.textbox("Rieseguiremo l'analisi sul MC per verificare che recuperi l'asimmetria iniettata.", 1.55, 3.50, 7.55, .33, size=16)
s.textbox("04", .77, 4.05, .8, .47, size=29, color=BLUE, bold=True)
s.textbox("Sistematiche", 1.55, 4.07, 7.55, .40, size=19.5, bold=True)
s.textbox("Studieremo l'effetto di flussi, polarizzazione, soglia BDT ed estimatore sul risultato finale.", 1.55, 4.46, 7.55, .42, size=16)
slides.append(s)

s = Slide("Prossimi passi", 19, dark=True)
s.textbox("Prossimi passi", .66, .4, 8.8, .55, size=33, bold=True)
s.textbox("Sezioni d'urto", .75, 1.27, 4.1, .4, size=22, color=ICE, bold=True)
s.textbox("Misureremo sia le sezioni differenziali sia quelle totali.", .75, 1.72, 4.1, .4, size=18)
s.textbox("Primo articolo", 5.03, 1.27, 4.1, .4, size=22, color=ICE, bold=True)
s.textbox("Prepareremo un articolo sul framework e sui risultati originali, valutando una rivista di fisica.", 5.03, 1.72, 4.1, .88, size=18)
s.textbox("Nuovi canali", .75, 2.85, 4.1, .4, size=22, color=ICE, bold=True)
s.textbox("Applicheremo la stessa catena a canali che non erano stati studiati in passato.", .75, 3.30, 4.1, .75, size=18)
s.textbox("Dalitz e teoria", 5.03, 2.85, 4.1, .4, size=22, color=ICE, bold=True)
s.textbox("Studieremo i Dalitz plot e proseguiremo il confronto con i modelli teorici.", 5.03, 3.30, 4.1, .9, size=18)
s.textbox("Completeremo i controlli sulle sideband e sul MC con asimmetria piatta prima della pubblicazione.", .75, 4.66, 8.5, .43, size=16, color=ICE)
slides.append(s)

assert len(slides) == SLIDE_COUNT
for slide in slides:
    add_navigation(slide)


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
