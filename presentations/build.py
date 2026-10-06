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
SLIDE_COUNT = 18
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

    def rect(self, x: float, y: float, w: float, h: float, color: str,
             *, rounded: bool = False):
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
        geom = e(A, "prstGeom", prst="roundRect" if rounded else "rect")
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

    def image(self, name: str, x: float, y: float, w: float, h: float, *,
              crop: tuple[float, float, float, float] | None = None):
        path = HERE / "assets" / name
        with Image.open(path) as im:
            iw, ih = im.size
        if crop is None:
            ratio = min(w / iw, h / ih)
            dw, dh = iw * ratio, ih * ratio
            x += (w - dw) / 2
            y += (h - dh) / 2
        else:
            if any(value < 0 or value >= 1 for value in crop) or crop[0] + crop[2] >= 1 or crop[1] + crop[3] >= 1:
                raise ValueError(f"Invalid crop for {name}: {crop}")
            dw, dh = w, h
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
        if crop is not None:
            bf.append(e(A, "srcRect", l=round(crop[0] * 100000),
                        t=round(crop[1] * 100000), r=round(crop[2] * 100000),
                        b=round(crop[3] * 100000)))
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
        "INTRO", "INTRO", "FRAMEWORK", "DATI", "RICOSTRUZIONE",
        "MONTE CARLO", "MONTE CARLO", "BDT", "BDT", "BDT", "CALIBRAZIONE",
        "ASIMMETRIE", "RISULTATI", "RISULTATI", "RISULTATI", "INTERPRETAZIONE",
        "VERIFICHE", "PROSPETTIVE",
    )
    h = .285
    # The page counter belongs only in the footer.
    s.rect(0, 0, 10, h, NAVY)
    s.rect(0, 0, 10 * s.number / SLIDE_COUNT, h, BAR_BLUE)
    s.textbox("GRAAL ANALYSIS", .62, 0, 5.4, h, size=9, color=WHITE,
              bold=True, valign="ctr")
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

s = standard("GRAAL e obiettivo del lavoro", 2,
             "D. Rebreyend (MENU04); V. Nedorezov (2015); Ajaka et al., PRL 100 (2008)")
s.textbox("GRAAL all'ESRF", .72, 1.14, 4.2, .38, size=21, color=BLUE, bold=True)
s.textbox("A Grenoble, la retrodiffusione Compton del laser sugli elettroni dell'anello produce fotoni polarizzati. LAGRANγE registra i prodotti della reazione su un ampio angolo.",
          .72, 1.55, 4.13, 1.06, size=17)
s.textbox("Il nostro lavoro", .72, 2.78, 4.2, .38, size=21, color=BLUE, bold=True)
s.textbox("Abbiamo costruito un framework che porta i dati GRAAL dalla preselezione all'estrazione dell'asimmetria Σ.",
          .72, 3.18, 4.13, .68, size=17)
s.textbox("Lo testiamo su γp → pηπ⁰, confrontando i risultati con Ajaka et al. (2008).",
          .72, 3.94, 4.13, .60, size=17)
s.image("graal_detector_source.jpg", 5.14, 1.21, 4.08, 2.91,
        crop=(.05, .18, .34, .24))
s.textbox("LAGRANγE: fascio (1), bersaglio (2), BGO (3), parete (8)", 5.15, 4.16, 4.05, .24,
          size=11, color=MUTED)
s.textbox("Aggiungiamo una selezione BDT addestrata sul nuovo MC e calibriamo i flussi per run. Estendiamo inoltre l'analisi ai dati VIS vicini alla soglia.",
          .72, 4.61, 8.54, .43, size=16)
slides.append(s)

s = standard("Il flusso completo dell'analisi", 3, "wiki/workflow.md; wiki/data-and-artifacts.md")

def flow_box(slide: Slide, label: str, x: float, y: float, w: float,
             *, color: str = ICE, size: float = 15):
    slide.rect(x, y, w, .63, color, rounded=True)
    slide.textbox(label, x + .08, y + .04, w - .16, .55, size=size,
                  color=NAVY, bold=True, align="ctr", valign="ctr")

def flow_arrow(slide: Slide, x: float, y: float):
    slide.textbox("→", x, y, .30, .63, size=23, color=BLUE,
                  bold=True, align="ctr", valign="ctr")

s.textbox("DATI", .67, 1.32, .76, .30, size=12, color=BLUE, bold=True)
for label, x, w in (("ROOT h70\ngrezzi", 1.45, 1.32),
                    ("Pre-analisi\nh80", 3.01, 1.38),
                    ("Selezione\nh85", 4.64, 1.35),
                    ("Ricostruzione\npηπ⁰", 6.24, 1.43),
                    ("Σ e figure", 7.94, 1.37)):
    flow_box(s, label, x, 1.13, w,
             size=13 if label.startswith("Ricostruzione") else 15)
for x in (2.76, 4.39, 5.99, 7.67):
    flow_arrow(s, x, 1.13)
s.textbox("Il percorso principale trasforma i dati del rivelatore in eventi ricostruiti e osservabili.",
          1.46, 1.83, 7.83, .31, size=14.5, color=MUTED)

s.textbox("MC / BDT", .67, 2.56, .76, .34, size=12, color=BLUE, bold=True)
for label, x, w in (("9 canali MC\ne spettro h85", 1.45, 1.73),
                    ("26 variabili\nper evento", 3.54, 1.70),
                    ("Training\nUV e VIS", 5.60, 1.70),
                    ("Gate BDT\nsui dati", 7.66, 1.65)):
    flow_box(s, label, x, 2.36, w, color="EAF4FB", size=14.5)
for x in (3.19, 5.25, 7.31):
    flow_arrow(s, x, 2.36)
s.textbox("Il classificatore apprende dal MC e dallo spettro misurato; il gate precede la ricostruzione.",
          1.46, 3.06, 7.83, .31, size=14.5, color=MUTED)

s.textbox("FLUSSI", .67, 3.79, .76, .34, size=12, color=BLUE, bold=True)
for label, x, w in (("h80, manifest\ne flussi esterni", 1.45, 2.08),
                    ("Energia per strip\ne polarizzazione", 3.94, 2.20),
                    ("Flussi calibrati\nPOL1 / POL2 / BREM", 6.56, 2.75)):
    flow_box(s, label, x, 3.59, w, color="EEF6FC", size=14.5)
for x in (3.56, 6.18):
    flow_arrow(s, x, 3.59)
s.textbox("Gli estimatori di Σ combinano eventi ricostruiti, esposizione calibrata e polarizzazione per run.",
          .73, 4.51, 8.63, .42, size=15.5, color=INK)
slides.append(s)

s = standard("Dai dati Fortran alla preselezione", 4,
             "codice semplificato da PreAnalysis.C e select_events.py; attribuzione: progetto")
s.textbox("Le routine Fortran hanno prodotto i dati storici. Antonio Riggio li ha convertiti in ROOT h70 e ha preparato i tagli PID; il codice della repo parte dai file h70 già convertiti.",
          .72, 1.08, 8.58, .62, size=16.5)
s.textbox("Con C++/ROOT produciamo h80; Python/PyROOT filtra gli eventi in h85. La ricostruzione e gli osservabili usano entrambi gli ambienti.",
          .72, 1.77, 8.58, .50, size=16, color=BLUE, bold=True)

s.rect(.73, 2.47, 3.69, .88, NAVY, rounded=True)
s.textbox('auto* cut = RequireCut("Proton","Cnt",Idrun);\ncut->IsInside(Eclusc_track[i],\n              Dedx_track[i]);',
          .91, 2.57, 3.34, .63, size=12.8, color=WHITE, valign="ctr")
s.textbox("→", 4.51, 2.59, .45, .64, size=28, color=BLUE, bold=True, align="ctr", valign="ctr")
s.rect(5.04, 2.47, 4.24, .88, ICE, rounded=True)
s.textbox("I poligoni PID del run classificano le tracce centrali. PreAnalysis.C scrive h80 con particelle e metadati.",
          5.20, 2.55, 3.94, .70, size=15, color=INK, valign="ctr")

s.rect(.73, 3.56, 3.69, 1.04, NAVY, rounded=True)
s.textbox('selected = frame.Filter(\n  "gammas.size() > 1 &&"\n  " fcharged_theta.size() == 1")\nselected.Snapshot("h85", ...)',
          .91, 3.62, 3.34, .94, size=12.3, color=WHITE, valign="ctr")
s.textbox("→", 4.51, 3.76, .45, .64, size=28, color=BLUE, bold=True, align="ctr", valign="ctr")
s.rect(5.04, 3.56, 4.24, 1.04, ICE, rounded=True)
s.textbox("La preselezione richiede almeno 2 fotoni e una traccia carica in avanti. h85 conserva tutti i rami; i 4 fotoni si richiedono più avanti.",
          5.20, 3.65, 3.94, .85, size=14.5, color=INK, valign="ctr")
s.textbox("RunNumber, Polarization e Xstrip restano disponibili per ricostruzione e calibrazione.",
          .75, 4.72, 8.55, .28, size=14, color=MUTED)
slides.append(s)

s = standard("Ricostruzione dei candidati pηπ⁰", 5,
             "05_reconstruction/runtime/reco_core.py; core/event_logic.py; 00_common/physics/pairing.py")
s.textbox("Dagli eventi h85 ricostruiamo η → γγ e π⁰ → γγ. I percorsi standard e BDT usano lo stesso algoritmo: nel secondo, il classificatore seleziona gli eventi prima del pairing.",
          .74, 1.04, 8.56, .58, size=16)

s.rect(.73, 1.77, 4.00, .77, NAVY, rounded=True)
s.textbox("if chain.gammas.size() < 4: continue\nif chain.protons.size() != 1: continue",
          .91, 1.91, 3.65, .53, size=12.7, color=WHITE, valign="ctr")
s.textbox("→", 4.80, 1.84, .37, .62, size=27, color=BLUE, bold=True, align="ctr", valign="ctr")
s.rect(5.22, 1.77, 4.04, .77, ICE, rounded=True)
s.textbox("Servono almeno quattro fotoni e un solo protone. Usiamo i primi quattro fotoni e conserviamo la molteplicità originale.",
          5.38, 1.84, 3.72, .61, size=14.4, color=INK, valign="ctr")

s.rect(.73, 2.69, 4.00, 1.00, NAVY, rounded=True)
s.textbox("pairing, chi2_value = pairing_fn(\n    event.photons, channel.hypothesis)\nif chi2_value >= config.chi2_cut:\n    return RejectionReason.CHI_SQUARE",
          .91, 2.79, 3.65, .80, size=12.4, color=WHITE, valign="ctr")
s.textbox("→", 4.80, 2.87, .37, .62, size=27, color=BLUE, bold=True, align="ctr", valign="ctr")
s.rect(5.22, 2.69, 4.04, 1.00, ICE, rounded=True)
s.textbox("Tre partizioni dei fotoni, con due assegnazioni ciascuna, danno sei ipotesi ηπ⁰. Scegliamo quella più vicina alle masse nominali: χ² < 10.",
          5.38, 2.77, 3.72, .84, size=14.2, color=INK, valign="ctr")

s.rect(.73, 3.84, 4.00, .91, NAVY, rounded=True)
s.textbox("heavy = photons[0] + photons[1]\nlight = photons[2] + photons[3]",
          .91, 3.99, 3.65, .60, size=12.7, color=WHITE, valign="ctr")
s.textbox("→", 4.80, 3.97, .37, .62, size=27, color=BLUE, bold=True, align="ctr", valign="ctr")
s.rect(5.22, 3.84, 4.04, .91, ICE, rounded=True)
s.textbox("Sommiamo i quadrivettori per ottenere η e π⁰. Scartiamo energie incompatibili con il fascio; salviamo masse, χ² e dati del run.",
          5.38, 3.92, 3.72, .75, size=14.2, color=INK, valign="ctr")
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
for number, slide in enumerate(slides, 1):
    slide.number = number
    add_navigation(slide)


def renumber_manual_navigation(xml: bytes, number: int) -> bytes:
    """Keep PowerPoint edits while updating its footer and progress bars."""
    root = etree.fromstring(xml)
    for shape in root.xpath("//p:sp", namespaces=N):
        xfrm = shape.find("p:spPr/a:xfrm", namespaces=N)
        if xfrm is None:
            continue
        off = xfrm.find("a:off", namespaces=N)
        ext = xfrm.find("a:ext", namespaces=N)
        if off is None or ext is None:
            continue
        if (int(off.get("x")) == 0
                and int(off.get("y")) in {0, round(5.34 * EMU)}
                and 0 < int(ext.get("cx")) < 10 * EMU):
            ext.set("cx", str(round(10 * number / SLIDE_COUNT * EMU)))
    for label in root.xpath("//a:t", namespaces=N):
        if label.text and label.text in {"02/19", "04/19", "07/19"}:
            label.text = f"{number:02d}/{SLIDE_COUNT:02d}"
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


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
            manual_slide = {2: "slide2_manual.xml", 4: "slide4_manual.xml",
                            6: "slide7_manual.xml"}.get(s.number)
            if manual_slide:
                # Preserve edits made in PowerPoint; navigation follows the
                # new order without replacing the user's text or formatting.
                xml = renumber_manual_navigation(
                    (HERE / "assets" / manual_slide).read_bytes(), s.number
                )
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
        if "jpg" not in extensions:
            types.append(e(CT, "Default", Extension="jpg", ContentType="image/jpeg"))
        members["[Content_Types].xml"] = etree.tostring(types, xml_declaration=True, encoding="UTF-8")
        with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as out:
            for name, data in members.items():
                out.writestr(name, data)
    print(OUT)


if __name__ == "__main__":
    build()
