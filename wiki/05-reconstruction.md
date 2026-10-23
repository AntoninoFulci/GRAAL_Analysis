# Stage 05: pairing and missing mass

[Reconstruction core](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/05_reconstruction/core) owns candidate and selection logic; [runtime](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/05_reconstruction/runtime) owns ROOT I/O and BDT adaptation. The standard and BDT paths use the same meson-pairing and missing-mass selection. The BDT gate is the intentional difference.

For four photons there are three disjoint pair partitions and two η/π⁰ assignments. Minimize the sum of the two squared mass pulls. Current defaults retain relative mass resolution 0.08, χ² < 10, the meson-energy guard and recoil missing-mass window ±0.06 GeV around the proton mass. Reconstruction uses the first four photons when adapting a broader input; the current stage 02 contract selects exactly four.

Supported entry points are `reconstruct_eta_pi0_chi2.py`, `reconstruct_eta_pi0_bdt.py`, `reconstruct_eta_pi0_bdt_sideband.py`, `prepare_signal_mc_selected.py`, and `reconstruct_2pi0.py` under [05_reconstruction](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/05_reconstruction). Use each script's `--help` for its declared inputs and outputs.

Products carry raw four-vectors, inclusive run/state cutflow, and reconstruction provenance `schema=2`, `selection_algorithm="pairing_missing_mass"`. Stage 08 exposes samples `raw` and `raw_bdt`. Historical reconstructed files with incompatible selection provenance are rejected by certified consumers even if they contain raw branches. Preserve those historical files; produce a new campaign from inputs when a compatible comparison is needed.
