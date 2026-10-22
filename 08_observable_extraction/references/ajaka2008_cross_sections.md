# Ajaka 2008 cross-section digitization

Source: J. Ajaka et al., *Phys. Rev. Lett.* **100**, 052003 (2008),
[DOI](https://doi.org/10.1103/PhysRevLett.100.052003).
The preserved, annotated [source PDF](../../docs/papers/Ajaka_2008_EtaPi0_Photoproduction_PRL100_052003.pdf)
has SHA-256 `7fdf85fe56fa8b0e232d070269e3e58d4d7ca542dcd9ac2287291abaa6b4f1cb`.
The extraction and source renderings exclude annotation appearances.

These CSV files are **digitizations of published vector graphics**, not the
original numerical tables. They preserve the plotted normalization without
rescaling. Extra decimal places record the coordinate transformation, not
experimental precision.

## Reproduce

Run with Python, PyMuPDF, NumPy and Matplotlib installed:

```sh
python 08_observable_extraction/references/digitize_ajaka2008.py
```

The default output directory is `results/ajaka-digitization-20261021`.
`--source`, `--reference-dir` and `--output-dir` override paths. The source hash
must match: a different PDF requires a new audit of the drawing indices.
The extraction used PyMuPDF 2.0 and Matplotlib 3.11.2. The script saves calibrated
CSV files, raw coordinate provenance, manifests, PNG/PDF reproductions, original
figure crops, and coordinate-check overlays. Cyan crosses in the latter show
extracted centers over the source figure.

## Figure 2

- `ajaka2008_figure2_digitized.csv`: 12 **filled Ajaka markers**, with nine
  recoverable vertical error bars. `error_ub` is the mean of the lower and upper
  endpoint distances; both distances are also retained. The three lowest-energy
  markers have blank errors and `error_available=False`: no error segments are
  encoded at their positions. A marker-size scale is recorded separately in
  provenance and must not be used as a measured error.
- `ajaka2008_figure2_nakabayashi_digitized.csv`: five **open Nakabayashi markers**
  from Ref. [16], kept separate. Their plotted bar endpoints are retained;
  the two lowest-energy bars reach the lower plotting boundary.
- `ajaka2008_figure2_model_hatching.csv`: 116 published model-band hatch segments,
  saved as individual endpoints, not interpreted as sampled confidence bounds.
- `ajaka2008_figure2_manifest.json`: reference-loader manifest. Published Ajaka
  errors already include the approximately **7% systematic**; do not add it again.

A tiny vertical segment near 0.946 GeV has no central marker in the PDF stream.
It is preserved as unassigned geometry and drawn in the reproduction, but is
not promoted to an experimental point. The paper's mention of 15 acceptance
energy bins does not establish 15 independently recoverable plotted points.
No energy-bin edges have been invented.

## Figure 3

- `ajaka2008_figure3_digitized.csv`: all **300 encoded open-circle markers**, 20
  per panel, covering the five rows and all three mass combinations.
- `ajaka2008_figure3_curves_digitized.csv`: all **60 published curves** (1,167
  polyline vertices): thick chiral-model curves, thin three-body phase space,
  dashed eta-Delta phase space, and dotted pi0-S11 phase space. Curve vertices
  are graphical samples, not independent experimental data.
- `ajaka2008_figure3_manifest.json`: units, nominal energies and limitations.

The y units are **μb/MeV**, while the mass axes use **GeV**. A numerical integral
using GeV therefore requires a factor of 1,000. The paper says each experimental
spectrum's area was normalized to the total cross section at the same energy.
It does not provide a covariance matrix for this normalization.

Page 3 describes five *narrow intervals*. Figure 3 labels only nominal beam
energies **1.1, 1.2, 1.3, 1.4 and 1.5 GeV**; neither their widths nor their edges
are specified. These are not the wide intervals printed under Figure 4.
An analysis overlay must supply and label its own energy-window choice rather
than claim exact matching to unpublished intervals.

No experimental error-bar paths are encoded in Figure 3. All uncertainties
are therefore blank with `error_available=False`, not zero. All encoded
marker centers are preserved, including negative values near the baseline;
`center_inside_frame` distinguishes genuinely out-of-frame centers with a
0.003 PDF-point numerical tolerance. Reproductions clip at the original
panel boundaries. Do not treat near-zero or clipped markers as exact physical
zeros, and do not infer original mass-bin edges merely from marker spacing.

## Coordinate provenance and verification

`ajaka2008_vector_provenance.json` contains PDF coordinates, source drawing
indices, marker centers/radii, error segments, curve vertices and each linear
axis calibration. Coordinates use PDF points with the origin at upper left.
Marker centers come from paired cubic **endpoints**; control-point bounding
boxes would overestimate the circle size. Fig. 2 axes run 0.9–1.5 GeV and
0–5 μb. Fig. 3 mass ranges are 1.0–1.4, 1.4–1.8 and 0.6–1.0 GeV; row maxima
are 0.02, 0.06, 0.06, 0.04 and 0.04 μb/MeV.

The separate digitization resolution is a conservative **0.17 PDF-point
coordinate scale**, rounded above the source's approximately 0.124-point
(Fig. 2) and 0.161-point (Fig. 3) exported grid steps. This is approximately
0.00049 GeV and 0.00616 μb in Fig. 2, and 0.00074 GeV with
0.000065–0.000196 μb/MeV in Fig. 3. It is **not** a Gaussian statistical error
and is not added in quadrature to published errors.

Source SHA, coordinate/curve counts and generated-file hashes are recorded in
`results/ajaka-digitization-20261021/manifest.json`. Reproductions and source
coordinate overlays were visually inspected; both final PDFs were rendered
with Poppler for a separate layout check.
