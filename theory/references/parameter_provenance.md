# Equation and parameter provenance

Exact values, units and locators are machine-readable in
[`central_parameters.json`](central_parameters.json); bibliography is in
[`sources.json`](sources.json). Page numbers below refer to printed article
pages (e.g. PRC 73, 045209-10), not PDF page labels.

| JSON key | Central value | Source key and locator | Responsible code |
|---|---:|---|---|
| `proton_mass` | 0.93827208816 GeV | `pdg_2024`, Baryon Summary Tables, proton mass | `EtaPi0PModel.masses`, `s_from_lab_photon_energy`, `predict_energy` |
| `pi0_mass` | 0.1349768 GeV | `pdg_2024`, Meson Summary Tables, π⁰ mass | `EtaPi0PModel.masses`, `tree_amplitude` |
| `eta_mass` | 0.547862 GeV | `pdg_2024`, Meson Summary Tables, η mass | `EtaPi0PModel.masses` |
| `charged_pion_mass` | 0.13957039 GeV | `pdg_2024`, Meson Summary Tables, π± mass | `Delta1700Parameters.from_parameters`, Eq. (37) width integrals |
| `delta_mass` | 1.232 GeV | `pdg_2024`, Baryon Summary Tables, Δ(1232) Breit–Wigner mass midpoint | `tree_amplitude`, `delta1700_width_components` |
| `delta_pole_width` | 0.117 GeV | `pdg_2024`, Baryon Summary Tables, Δ(1232) width midpoint | `p_wave_width`, `delta1700_width_components` |
| `delta1700_mass` | 1.700 GeV | `nacher_2001`, p. 16, Sec. 4 | `breit_wigner`, `delta1700_width_components` |
| `delta1700_nominal_width` | 0.300 GeV | `nacher_2001`, p. 16, PDG-average width | Nπ term in `delta1700_width_components` |
| `rho_mass` | 0.77526 GeV | `pdg_2024`, Meson Summary Tables, ρ(770) | `_n_rho_width` |
| `f_delta_n_pi` | 2.13 | `nacher_2001`, Appendix A1 Eq. (33), A3 | `delta1700_eta_delta_vertex` |
| `g_eta_delta` | 1.7 − 1.4i | `sarkar_2005`, Table 10, S=0 I=3/2, 1827−i108 MeV pole; `doering_2006_prc`, 045209-10 below Eq. (37) | `delta1700_eta_delta_vertex` |
| `g1_prime` | −0.260 mₙ⁻¹ | `nacher_2001`, Appendix A3, photon point | `Delta1700Parameters.from_parameters`, `delta1700_eta_delta_vertex` |
| `g2_prime` | 0.270 mₙ⁻² | `nacher_2001`, Appendix A3, photon point | `Delta1700Parameters.from_parameters`, `delta1700_eta_delta_vertex` |
| `n_pi_branching_fraction` | 0.15 | `pdg_2024`, Baryon Summary Tables, Δ(1700) Nπ range 10–20%, midpoint | `delta1700_width_components` |
| `g_rho` | 2.60 | `nacher_2001`, p. 17, Eqs. (13)/(16), Appendix A3 | `_n_rho_width` |
| `f_rho` | 6.14 | `nacher_2001`, p. 8 after Eq. (17), Appendix A3 | `_rho_width_at_mass`, `_n_rho_width` |
| `f_tilde_delta_pi` | −1.325 | `nacher_2001`, p. 17 after Eq. (31), Appendix A3 | `_delta_pi_width` |
| `g_tilde_delta_pi` | 0.146 | `nacher_2001`, p. 17 after Eq. (31), Appendix A3 | `_delta_pi_width` |

| Formula | Source and location | JSON inputs | Responsible code / convention |
|---|---|---|---|
| Eq. (36), Δ*(1700) propagator | `doering_2006_prc`, 045209-9 | `delta1700_mass`, width inputs | `breit_wigner`, `delta1700_eta_delta_vertex`; denominator √s − M + iΓ/2 |
| Eq. (37), three partial widths | `doering_2006_prc`, 045209-10; `nacher_2001`, Appendix A3 | `delta1700_nominal_width`, `n_pi_branching_fraction`, `g_rho`, `f_rho`, `f_tilde_delta_pi`, `g_tilde_delta_pi`, masses | `delta1700_width_components`, `_n_rho_width`, `_delta_pi_width`, `p_wave_width` |
| Eq. (39), γp → Δ* → ηΔ production | `doering_2006_prc`, 045209-10; `nacher_2001`, Appendix A3; `sarkar_2005`, Table 10 | `g_eta_delta`, `f_delta_n_pi`, `g1_prime`, `g2_prime`, masses | `delta1700_eta_delta_vertex`; coherent magnetic/electric terms, spin transition, no extra e |
| Eq. (43), tree amplitude | `doering_2006_prc`, 045209-11, Fig. 11 | Eq. (39) inputs, `delta_mass`, `delta_pole_width` | `tree_amplitude`; multiply production vertex by Δ(1232) propagator |
| Eq. (44), Δ invariant argument | `doering_2006_prc`, 045209-11 | `pi0_mass`, `proton_mass` | `tree_amplitude`; z′ = √`(p_pi0+p_proton)²` (equivalent to displayed form) |
| Eq. (45), differential cross section | `doering_2006_prc`, 045209-11 | `proton_mass`, all final masses | `predict_energy`; invariant three-body weights, flux `2(s−m_p²)`, baryon factor `4m_p²`, GeV⁻²→μb |
| Eq. (46), η-frame boost | `doering_2006_prc`, 045209-11 | `eta_mass`, `pi0_mass`, `proton_mass` | `sample_three_body` via `boost`; equivalent covariant construction, not literal paper parametrization |

The Figure 14 dotted and Figure 19 full-model reference readings, pixel-axis
calibration and uncertainty are recorded in [`digitization.json`](digitization.json).
They are checks, not fitted parameters.
