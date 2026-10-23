# Figure 4 coherent-amplitude source inventory

Scope: `gamma p -> eta pi0 p` model behind Ajaka et al., *Phys. Rev.
Lett.* **100**, 052003 (2008), Fig. 4. This inventory maps the production
and rescattering contributions described by Döring, Oset, and Strottman,
*Phys. Rev. C* **73**, 045209 (2006). The seven-family coherent implementation
exists as `EtaPi0PFullModel`; its physical convergence and curve-validation
exit gate is **not passed**. Equation and figure numbers below refer to that
PRC paper. The family comparison table retains the historical low-order
Increment A audit; its `W > 1.70 GeV` masks are not current domain limits.
Current direct strong-T support ends at `1.80 GeV`, matching PRC73 source
use, while PRC65 reports qualitative scattering agreement only through about
`1.60 GeV`. **“code complete” is independent of “curve compatible.”**

## Source availability

| Source | Role | Local PDF | SHA-256 / availability |
| --- | --- | --- | --- |
| Döring, Oset, Strottman, *Phys. Rev. C* **73**, 045209 (2006) | Principal `eta pi0 p` amplitudes and Fig. 14 coherent sum | `tmp/pdfs/10.1103@PhysRevC.73.045209.pdf` | `19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb` |
| Döring, Oset, Strottman, *Phys. Lett. B* **639**, 59 (2006) | Complementary `Delta*(1700)` coupling conventions | `tmp/pdfs/10.1016@j.physletb.2006.06.022.pdf` | `c1def91b01ee5750aca4124ae2469178b204d99649075d7d4f4277facab9d430` |
| J. C. Nacher, E. Oset, M. J. Vicente Vacas, L. Roca, *Nucl. Phys. A* **695**, 295 (2001), PRC Ref. [17] | Two-pion resonance couplings, widths, and pion form factor used in Figs. 8–9 | `tmp/pdfs/nucl-th-0012065.pdf` | `0227c86bdf98deb6a7674df6720d5db80a4242fe56cdff431c507729bd7b144e` |
| S. Sarkar, E. Oset, M. J. Vicente Vacas, *Nucl. Phys. A* **750**, 294 (2005), PRC Ref. [21] | Dynamically generated `Delta*(1700)` couplings to `eta Delta` and `K Sigma*` | `tmp/pdfs/nucl-th-0407025.pdf` | `1b67f036787bc1085d1ae0491f64e14b8970ffe4f2377607da51dc5a2fc077af` |
| T. Inoue, E. Oset, M. J. Vicente Vacas, *Phys. Rev. C* **65**, 035204 (2002), PRC Ref. [8] | `N*(1535)` six-channel `T` matrix, loop `G`, subtraction/regularization, full/reduced variants | `tmp/pdfs/PhysRevC.65.035204.pdf` | `e8861394ef3fb86c005694d3cb82d8c2b905e39dbe384903f58392d644cff6ac` |
| M. Döring, E. Oset, M. J. Vicente Vacas, *Phys. Rev. C* **70**, 045203 (2004), PRC Ref. [25] | Later low-energy treatment of the `pi pi N` correction cited after Eq. (6); compare conventions, but do not substitute its constant-vertex approximation for Ref. [8] | `tmp/pdfs/PhysRevC.70.045203.pdf` | `7d07d8510fa19546e9d73824826306babc9cb0b88c06277b5d326303c713854f` |
| M. N. Butler, M. J. Savage, R. P. Springer, *Nucl. Phys. B* **399**, 69 (1993), PRC Ref. [40] | Adopted decuplet effective Lagrangian and state phases in Sec. IV D, Eq. (38) | `tmp/pdfs/9211247v1.pdf` (author preprint `hep-ph/9211247v1`, not journal PDF) | `a1ad108ede40ddfa29bd8147296c2c8fe10f4a167f741b2a5aaea6b2d2ee4e29`; Task 5 checked preprint Eqs. (2.9)–(2.11) |
| E. Oset, A. Ramos, *Nucl. Phys. A* **679**, 616 (2001), PRC Ref. [41] | Comparison SU(3) factors, explicitly up to a different phase | Not supplied | Comparison only; not the adopted convention |

The PRC paper prints the charge-`+1` channel order, leading potential,
Bethe–Salpeter expression, and some corrections in Sec. II, Eqs. (1)–(6).
It explicitly sends the s-wave projection, loop `G`, and the `v11`/`v31`
ingredients back to Ref. [8]. Those ingredients are now available. Its
**reduced** model omits both the vector-meson-exchange correction and the
`pi pi N` channel, not only the latter. Ref. [25] uses a separate low-energy
approximation; the resonance-region prescription must be mapped from [8]
and the charge-`+1` conversion in the principal PRC paper. No curve-matched
substitute is allowed.
The equation-level source audit is in
[`nstar_1535_tmatrix_source_map.md`](nstar_1535_tmatrix_source_map.md);
it lists the remaining numerical/convention choices explicitly.
Sec. IV D adopts the effective Lagrangian and decuplet-state phases of
Ref. [40], stating agreement with Ref. [21]. It compares the resulting
SU(3) factors with Ref. [41] **up to a different phase**; [41] is not the
source of the adopted convention. An author preprint of [40] is supplied;
the comparison paper [41] is not.
Task 5 checked the supplied [40] preprint: `T112=Delta+/sqrt(3)`,
`T113=Sigma*+/sqrt(3)`, `T123=Sigma*0/sqrt(6)`. Eqs. (39)–(42) set the
implemented factors. In particular Eq. (41) is `(2D+F)/(10 f_pi)` and
Eq. (42) contains `4 sqrt(3)/25`; plan transcription alternatives were
not substituted. Only kaon topologies use the intermediate `Sigma*`;
Eq. (39) retains `Delta(1232)`.

## Amplitude families

Each family is independently callable through its listed function and through
`selected_amplitude(sample, polarization, (family_name,))`. These diagnostics
select complete families. The physical `amplitude` always sums all seven
complex spin matrices before squaring; internal gauge partners cannot be
selected separately. Paths in this table are relative to `theory/`.

| Family / source equation | Implementation | Parameter source record | Unit-test evidence | Convergence status | Comparison curve/status and remaining discrepancy |
| --- | --- | --- | --- | --- | --- |
| `chiral_contact`: Fig. 6, Eqs. (16)–(21), Table III | `src/graal_theory/amplitudes/chiral_photoproduction.py:chiral_contact_amplitude` | `eta_pi0_p_full_parameters.json`: `electric_charge`, `b6d`, `b6f`; strong dependency below | `test_chiral_photoproduction.py`: `test_contact_eta_column_isolates_table_iii_and_ordinary_magnetic_limit`, `test_contact_ordinary_term_equals_charge_weighted_wt_coefficient` | No first-loop quadrature; real strong closure is finite inside its domain. Task 7 p4/5 spectra fail the Sobol gate; end-to-end convergence unestablished. | Fig. 12 dotted: 5 masked overlap points, 0 accepted comparisons. Upper-energy external strong invariants can exceed its trusted domain. |
| `external_pi0`: Fig. 7, Eq. (24), coherent Eqs. (8)–(9) | `src/graal_theory/amplitudes/chiral_photoproduction.py:external_pi0_amplitude`; `production_loops.py:eta_photoproduction_amplitude` | `eta_pi0_p_full_parameters.json`: axial, charge and first-loop-cutoff inputs; strong dependency below | `test_chiral_photoproduction.py`: `test_external_complete_eta_pair_propagator_spin_order_and_printed_i`, `test_external_uses_real_coherent_eta_pair`; `test_production_loops.py` | Direct KR+meson-pole pair has checked configured/doubled orders. Task 7 p4/5 spectra fail the Sobol gate; no end-to-end convergence claim. | Fig. 12 dash-dot: 5 masked overlap points. Printed recoil spin order and explicit `i` retained; no accepted source comparison. |
| `internal_pi0`: Fig. 8(c,d), Eq. (25), channels 2/4/5 | `src/graal_theory/amplitudes/chiral_photoproduction.py:internal_pi0_amplitude` | `eta_pi0_p_full_parameters.json`: axial, charge, first-loop and pion-monopole cutoffs; strong dependency below | `test_chiral_photoproduction.py`: independent Eq. (25) channel oracle and closed-channel tests; `test_full_production_convergence.py:test_source_internal_pi0_real_strong_amplitude_at_converged_loop_orders` | Source event 15, `K+Lambda`, `z=1.60842859385` GeV fails strict q/angle16 and 32, passes the isolated 64/128 complex-amplitude check. This single event does not certify the full spectrum. | Fig. 12 solid: 5 masked overlap points. Task 7 failure propagates to the full coherent output; no parameter/tolerance adjustment. |
| `explicit_resonances`: Fig. 9(e,f), Eqs. (26)–(36) | `src/graal_theory/amplitudes/resonance_photoproduction.py:explicit_resonance_amplitude` | `eta_pi0_p_full_parameters.json`: N*(1520) mass/width/couplings and form factor; `central_parameters.json`: Delta*(1700)/Delta inputs; strong dependency below | `test_resonance_photoproduction.py`: printed kernel phase/channel/pole-partner oracle, source partial-width integrals and coherent wrapper tests | Strict threshold+1 MeV full q/angle16 fails Eq. (26), event 0, `pi+n`, `z=1.48664055351` GeV. q/angle32 yields finite p4 output at high runtime; full loop+Sobol convergence not established. | Fig. 13 dotted/solid/dash-dot individual kernels: 15 unresolved points. The indivisible coherent family is not equivalent to any individual stroke; no kernel split was introduced. |
| `eta_delta_rescattering`: Fig. 10, Eq. (39) in Eq. (26) | `src/graal_theory/amplitudes/decuplet_rescattering.py:eta_delta_rescattering_amplitude` | `central_parameters.json`: complex `g_eta_delta`, electromagnetic couplings and Delta parameters; strong dependency below | `test_decuplet_rescattering.py`: `test_eta_family_uses_the_shared_eq39_with_original_tree_and_complex_polarization`, direct loop oracle and default/doubled checks | Independent loop tests pass at their specified events; Task 7 p4/5 spectra fail the Sobol gate. No real-full-spectrum certification. | Fig. 14 dash-dot: 5 masked overlap points. Delta(1232) intermediate propagator retained; no accepted source comparison. |
| `k_sigma_star_rescattering`: Fig. 10, Eqs. (40)–(42) in Eq. (26) | `src/graal_theory/amplitudes/decuplet_rescattering.py:k_sigma_star_rescattering_amplitude` | `eta_pi0_p_full_parameters.json`: complex `g_k_sigma_star`, Sigma* mass/width, axial/charge and empirical `1.15` correction; strong dependency below | `test_decuplet_rescattering.py`: printed K/Sigma* coefficients, `4 sqrt(3)/25` Eq. (42), coherent KR addition and direct-loop oracles | Independent loop checks pass at their specified events; whole-family Task 7 p4/5 spectrum does not establish Sobol convergence. | Fig. 12 Eqs. (40)–(41) and Fig. 13 Eq. (42) separate strokes: 10 unresolved points. Eqs. (40)–(42) remain one coherent family; common Lambda/pi0 running-width and off-real zero-width prescriptions are stated reconstruction conventions. |
| `eq43_tree`: Fig. 11, Eqs. (39), (43)–(44) | `src/graal_theory/amplitudes/delta1700.py:tree_amplitude`; standalone `models/eta_pi0_p.py:EtaPi0PModel` | `central_parameters.json`; [parameter provenance](parameter_provenance.md) | `test_delta1700_amplitude.py`, unchanged `test_eta_pi0_p_model.py`; cold-import complex-amplitude/spectrum preservation and four-energy Sobol tests in `test_full_production_convergence.py` | Eight-bin spectra pass strict p16/17 at threshold+1 MeV, 1.2, 1.4, 1.5 GeV; sampled p10/11, p12/13 and p14/15 fail a populated-bin gate. No production first loop. | Fig. 14 dotted: Task 7's low-resolution 15 overlap points remain masked. Separate legacy tree comparison is not evidence for the full coherent curve. |

Shared strong dependency: `src/graal_theory/amplitudes/nstar1535_reduced.py`,
`nstar1535_pipi_n.py` and `nstar1535_full.py` implement reduced, pion-corrected
intermediate, and reconstructed-full variants. The physical production model
uses `reconstructed_full_tmatrix` with `nstar1535_final_subtractions.json`,
`nstar1535_reduced_parameters.json` mass/decay inputs, and
`nstar1535_vmd_masses.json`. Tests in the corresponding three strong-T files
are invoked unchanged. Current external real-axis `W` is bounded through
`1.80 GeV`; the validated `StrongTGrid` may accelerate the same values.
Above `1.80 GeV` remains **masked unsupported domain**, distinct from
quadrature nonconvergence. The `1.60 < W <= 1.80 GeV` source-used extension
has no assigned quantitative scattering-model uncertainty.

The PRC Fig. 14 **solid** curve is the coherent sum with the full
`N*(1535)` model; the **dashed** curve uses its reduced variant. The
**dotted** curve is the isolated Fig. 11/Eq. (43) tree; the
**dash-dotted** curve is Eq. (39) followed by `eta p` rescattering. The
current `theory/` code has a coherent seven-family implementation, but the
solid line and Ajaka Fig. 4 are not validated. Figure 12 groups chiral
contributions; Figure 13
groups explicit-resonance contributions. Neither group can be added as
incoherent cross sections to obtain the solid curve.

## Increment A exit gate and Increment B handoff

The source-linked callable-family and immutable-parameter API gates are
implemented. The numerical exit gate is **not passed**. The historical
Increment A reason included upper energies beyond its `1.70 GeV` guard;
that domain block is resolved by the source-bounded `1.80 GeV` extension.
Current publication-bin Sobol normalization and runtime gates still fail.
The upper-energy `p_eta` pilot at `p5/p6` changes its denominator by about
`1.72%`, above the fixed `<1%` gate. `p7` also encounters a near-tangent
Eq. (25) event that needs at least `96/72` inner order; complete same-order
`p6/p7` still changes its denominator `1.047245%`, failing `<1%`.
Neither result is an
accepted Ajaka Figure 4 curve.
Figs. 12–14/19 comparisons are recorded without tuning: the Task 7 baseline
has 71 overlap points (0 compatible, 0 discrepant, 30 unresolved, 41 masked).
Its q/angle16, p4/5 results are a diagnostic baseline, not convergence evidence.
The Fig. 14 reduced coherent closure is unavailable and its 5 points stay
unresolved. Individual source kernels remain unresolved where the diagnostic
whole-family API cannot represent them.

The exact API and bounded physical measurements, preservation checks, runtime,
convention limitations, and prerequisites for integrating Ajaka's four-by-three
panels are in [the validation summary](full_production_validation.md).
No parameters were fitted to Ajaka points or digitized theory curves.
