from graal_theory.cli import _REFERENCES


def test_reference_files_are_package_resources():
    for filename in (
        "central_parameters.json", "sources.json", "digitization.json",
        "figure14_eta_p_tree.csv", "figure19_total_1202.csv",
        "nstar1535_final_subtractions.json",
        "nstar1535_vmd_masses.json",
        "eta_pi0_p_full_parameters.json",
        "p73_full_production_curves.csv", "p73_full_production_curves.json",
    ):
        assert _REFERENCES.joinpath(filename).is_file()
