# Modernising the GRAAL simulation and analysis chain: GEANT3-to-Geant4 migration and multivariate event selection

**Working draft v0.1 — 10 November 2026. Not for submission.**

Authors and affiliations: **[TO COMPLETE]**.

This draft describes the documented implementation and a proposed validation programme. Quantitative evidence is dated explicitly. Items marked **[TO COMPLETE]** require evidence or author decisions before submission. Citation keys refer to `references.bib`; internal evidence is mapped in `note_lavoro.md`.

## Abstract — provisional

Reanalysing archived photoproduction data requires a detector simulation and event selection whose assumptions can be traced to the original experiment. We describe the modernisation of the GRAAL simulation and analysis chain, using the reaction $\gamma p\rightarrow\eta\pi^0p\rightarrow4\gamma p$ as a reference channel. The approach combines migration of a preserved GEANT3 detector description to Geant4, recovery of selected detector-response and reconstruction algorithms, and a common analysis interface for conventional and boosted decision tree selections. Generated-event identity and weights are retained across transport and selection, including events without reconstructed candidates. A staged validation programme separates geometry conversion, numerical agreement with recovered routines, detector-response measurements and closure of extracted observables. The current implementation has reached a small reaction pilot with complete generated-event accounting but no selected final candidates; physical efficiencies and multivariate performance on Geant4-derived candidates remain unvalidated. This draft defines the measurements required to establish the method's accuracy and benefit before its use in a physics analysis.

**Keywords:** photoproduction; detector simulation; Geant4; legacy software; event reconstruction; boosted decision trees.

## 1. Introduction

The scientific value of an archived experimental sample depends on the ability to reconstruct how detector signals became selected events and measured observables. A modern analysis must recover this chain while retaining the acquisition conditions, selection conventions and provenance needed to interpret the original data. Replacing an obsolete software environment is therefore only one part of the task: the detector response and the effect of event selection must also be established.

The reaction $\gamma p\rightarrow\eta\pi^0p$, with both mesons decaying into two photons, provides a concrete test case. Its four-photon final state requires meson assignment, rejection of competing channels and identification of a recoil proton. Previous GRAAL measurements include cross sections and beam asymmetries [@Ajaka2008]. The present methods study is intended to provide a reusable basis for a subsequent physics analysis of this channel and, after channel-specific validation, other reactions.

The work has two connected components. First, the preserved GEANT3 detector description and selected legacy response algorithms are migrated into a Geant4-based simulation chain [@GEANTManual; @Agostinelli2003]. Second, conventional reconstruction and multivariate selection are connected to the same measured-event representation. This separation makes it possible to investigate detector modelling and classifier selection without silently changing the underlying reconstruction criteria.

**[TO COMPLETE: establish the contribution relative to published detector migrations and multivariate photoproduction analyses. No priority claim or quantitative performance improvement is established by this draft.]**

## 2. Experimental inputs and common event definition

The reference channel contains four detected photons and an identified proton. The current common selection requires exactly four central photon candidates, exactly one identified proton and no identified pion candidate. It additionally requires one forward charged track for a proton polar angle below $25^\circ$, and none for larger angles. The absence of an identified pion is not equivalent to the absence of all additional charged particles.

Particle identification (PID) uses the established period-dependent cuts. These cuts remain fixed when comparing reconstruction paths or diagnosing the simulated response. The ultraviolet (UV) and visible (VIS) laser profiles are treated as explicit analysis domains; extending the energy range or changing a proton topology requires corresponding validation of the simulation and classifier.

The analysis uses ROOT for event storage and data processing [@Brun1997]. Event provenance connects the input sample, acquisition period, configuration and selected output. Raw inputs and historical scientific products are retained without retroactive changes to their metadata or observable conventions.

**[TO COMPLETE: add the authoritative apparatus reference, detector coverage and resolutions, acquisition periods, data-quality criteria, and the exact data and simulation samples used for the publication. Sample sizes must come from a frozen publication campaign.]**

## 3. Migration from GEANT3 to Geant4

### 3.1. Geometry and material interpretation

The conversion starts from a preserved GEANT3 geometry snapshot. The current model uses the GRAAL_26 detector description. Conversion produces a Geometry Description Markup Language (GDML) representation for Geant4 while retaining detector identities needed to associate sensitive volumes with response channels.

Geometric translation and transport-material interpretation are treated separately. Some historical material records use effective elemental parameters or nested mixtures that require an explicit interpretation in the modern transport engine. The source description remains unchanged, while the runtime material definitions record the composition and density actually used. Agreement of volume identities and placements does not establish agreement of interaction probabilities or material budgets.

The current detector baseline combines the `GRAAL_26` geometry with the recovered `NEW_PLAN` forward-chamber and `OLD_CYL` central-chamber paths. This configuration is not asserted to reproduce every historical acquisition period. In particular, the documented `NEW_PLAN`/`OLD_PLAN` difference must remain visible in comparisons involving older detector conditions.

### 3.2. Target and interaction conditions

Period-dependent configurations specify the target material, active length and longitudinal position. The interaction-vertex model uses fitted longitudinal target boundaries and an observed transverse interaction map. The latter is a reconstructed distribution affected by acceptance and resolution, rather than an unfolded incident-photon beam profile. The current model samples the longitudinal coordinate uniformly between the fitted ends, independently of the transverse position.

Hydrogen and deuterium configurations require different generator assumptions. The present exclusive replay describes a free proton and is restricted to compatible hydrogen periods. A deuterium geometry alone does not supply a nuclear event generator. Passive material, alignment and the response dependence on acquisition period remain subjects of physical validation.

### 3.3. Generation, transport and event accounting

The generator supplies unsmeared final-state four-vectors to transport. Detector smearing used by the existing fast simulation is excluded from this input to avoid applying detector response twice. The supported export and replay path checks the source identity, kinematics and beam range, and binds the transported events to their original generator entries.

The current diagnostic transport uses the `FTFP_BERT_HP_EMZ` configuration. This is a declared starting point, not a demonstrated optimum for GRAAL, and does not generate the polarized exclusive reaction. Physics-model and production-cut variations must be assessed independently of detector thresholds.

Sensitive-volume steps, channel identities and event records are stored in ROOT. Event accounting retains generated events with no hits, unavailable reconstruction inputs or failed selections. Generation weights are kept distinct from flux, branching fractions and cross-section normalizations. This distinction is necessary before constructing a physical efficiency denominator.

### 3.4. Digitisation and reconstruction

Recovered response and reconstruction routines are ported and checked at their individual boundaries. The implemented paths include responses for the bismuth germanate (BGO) calorimeter and barrel, chamber tracking, central and forward associations, a tagger response and an interface to the common preanalysis and event selection. Numerical comparisons against recovered original routines test specific calculations and input domains.

Numerical agreement with a legacy routine does not establish a calibrated detector response. The historical Monte Carlo path contains idealisations that differ from the calibration applied to data. Similarly, the explicit modern initialisation of clustering parameters is not evidence that a historical executable used the same runtime values. Source-domain failures remain marked as unavailable rather than being converted into measured detector inefficiencies.

**[TO COMPLETE: provide a compact legacy-to-modern component table, geometry/material comparisons, the precise configuration of each validated sample, and detector-response comparisons against independent data.]**

## 4. Common reconstruction and multivariate selection

### 4.1. Photon pairing and recoil missing mass

Four photons admit three disjoint pair partitions and two assignments of each partition to $\eta$ and $\pi^0$. The reconstruction selects the assignment that minimises the sum of squared mass pulls,

$$
\chi^2_{\mathrm{pair}}=
\left(\frac{m_{\gamma\gamma}^{(\eta)}-m_\eta}{\sigma_\eta}\right)^2+
\left(\frac{m_{\gamma\gamma}^{(\pi^0)}-m_{\pi^0}}{\sigma_{\pi^0}}\right)^2.
$$

This statistic ranks assignments; it is not a global constrained kinematic fit. The documented defaults use relative mass resolutions of 0.08, require $\chi^2_{\mathrm{pair}}<10$, apply a meson-energy guard and select a recoil missing mass within $0.06\ \mathrm{GeV}$ of the proton mass. The recoil quantity is formed from the beam and target minus the reconstructed meson four-vectors.

Both the conventional and classifier-selected paths apply the same pairing and missing-mass requirements. The classifier gate is the intended difference between them. This provides a controlled comparison of the extra selection, subject to common input and exposure definitions.

### 4.2. Boosted decision tree selection

The boosted decision tree (BDT) uses an ordered set of 26 features shared between training and inference. These include two-photon masses, pairing information, missing quantities, photon energy and angular summaries, and proton kinematics. The feature missing mass formed from beam plus target minus the measured proton is distinct from the meson-based recoil missing mass used in reconstruction.

The model bundle records its feature order, beam coverage, operating threshold and provenance. The existing training samples use simplified detector smearing and photon loss; they have not been replaced by a physically validated Geant4-derived production sample. The migration must therefore be evaluated before attributing any classifier improvement to the new simulation.

Training, threshold selection and final testing must be separated. Repeated versions of the same generated event must remain grouped across these partitions. Validation-selected performance is not an independent final test. Background composition, domain differences and the central-proton topology require dedicated checks.

**[TO COMPLETE: add the exact feature definitions, classifier implementation and reference, frozen training configuration, sample partitions, weights, threshold-selection criterion and independent performance results. Do not copy an operating threshold from a diagnostic pilot into the publication by default.]**

## 5. Validation strategy

Validation is organised around four distinct questions:

1. Does the conversion preserve the declared geometry, channel identities and input/output accounting?
2. Do recovered numerical routines agree within their specified domains, and are unsupported cases explicit?
3. Does the simulated response reproduce independent detector measurements, including central energy-loss versus calorimeter-energy and forward energy-loss versus time-of-flight distributions?
4. Does the complete selection recover injected observables with acceptable bias and interval coverage, and improve the measurement relative to the conventional path?

The final question requires more than a cleaner invariant-mass peak or a classifier score distribution. Comparisons should report signal efficiency, residual background, kinematic dependence and the uncertainty of the extracted observable. A change in selected yield alone cannot establish improvement. Detector-response tuning samples and final controls must have a documented history of use; a run already used to determine target conditions is not independent of the entire simulation model.

For an observable-level check, the beam-asymmetry extraction compares flux-normalised yields for vertical and horizontal polarization. With $y_V=N_V/F_V$ and $y_H=N_H/F_H$, the implemented ratio is

$$
R=\frac{y_V-y_H}{P_Hy_V+P_Vy_H},
$$

where $P_V$ and $P_H$ are the polarization magnitudes. The angular phase and sign follow the established experimental convention. The ratio estimator applies the approved finite-azimuth-bin divisor once to the fitted asymmetry and its errors: 0.9003, 0.9549 and 0.9745 for 8, 12 and 16 uniform bins, respectively. The event-level conditional-likelihood estimator receives no such rescaling. The physical applicability of the bin correction requires checking the within-bin acceptance assumptions.

Injected-asymmetry studies must span the relevant kinematics, background mixtures and polarization/exposure conditions. Correlations between selections and projections of the same events must be retained. These checks test the method; the final measured asymmetry distributions and their physics interpretation are reserved for the subsequent analysis paper.

**[TO COMPLETE: define and execute the frozen validation campaign, report uncertainty and coverage, and document the final sample used only for evaluation. Polarization closure is not supplied by the present unpolarized reaction pilot.]**

## 6. Current technical evidence

The fixed reaction pilot documented on 10 November 2026 contains 128 generated $\gamma p\rightarrow\eta\pi^0p\rightarrow4\gamma p$ events with incident energy uniformly distributed over 1.10–1.50 GeV. It uses the `1998_uv` hydrogen conditions, generator seed 20261110 and transport seed 20261111. All events were transported without aborts, and the event ledger retained unit generation weights with $\sum w=\sum w^2=128$.

| Boundary | Recorded population | Interpretation |
| --- | ---: | --- |
| Generated and transported | 128 / 128 | Complete transport accounting for this pilot |
| Measured-event interface (`h70`) | 32 | Events entering the common preanalysis |
| Inclusive preanalysis (`h80`) | 32 | Events available to the common topology selection |
| Topology-selected sample (`h85`) | 0 | No final candidate in this diagnostic sample |
| Conventional and BDT reconstruction | 0 / 0 | Valid empty outputs; no BDT event scored |

The four-photon events have no intersection with the events containing an identified proton. Charged candidates in the four-photon events lie outside the unchanged proton-identification cuts. This observation motivates response and source-domain investigations; it does not identify a physical cause or justify changing those cuts. The empty selection is not a measurement of zero detector efficiency.

This pilot demonstrates a connected technical path and explicit accounting. It does not establish physical acceptance, a nonempty reconstructed signal sample, or BDT performance on transported events. A publication result section must replace or supplement these development diagnostics with the validation measurements specified above.

## 7. Discussion and extension to other channels

The common event representation allows detector response, conventional reconstruction and classifier selection to be investigated through explicit interfaces. Keeping original sources and input identities also makes changes in material interpretation and acquisition conditions reviewable. These properties support reproducible comparisons, but are not substitutes for physical validation.

Extension to another channel requires its own production model, final-state reconstruction, competing-channel treatment, acceptance study and observable closure. The reusable method can be cited by subsequent analyses, while their channel-dependent assumptions and uncertainties remain part of those papers.

## 8. Conclusions — provisional

The current work establishes a migration and analysis structure linking a preserved detector description, Geant4 transport, selected recovered response algorithms and common event selection. Its central scientific objective is a quantitatively validated comparison between conventional and multivariate analysis under a controlled detector model. The available reaction pilot establishes technical connectivity but does not yet establish that objective. Claims of improved precision, validated efficiencies or a complete GEANT3-to-Geant4 replacement await independent detector and observable-level tests.

## Data and software availability — to complete

**[TO COMPLETE: publication release identifier, archived code and configuration references, redistributable validation samples, figure source data and access conditions for experimental data. No public data release or permission is implied by this draft.]**

## Acknowledgements — to complete

**[TO COMPLETE: authorship, collaboration review, institutional support and funding.]**

## References

Bibliographic records are maintained in [references.bib](references.bib). Literature review, exact GEANT manual edition, apparatus and classifier references, and full-text checks remain open; see [working notes](note_lavoro.md).
