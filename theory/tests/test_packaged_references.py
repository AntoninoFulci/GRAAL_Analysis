from graal_theory.cli import _REFERENCES


def test_reference_files_are_package_resources():
    for filename in (
        "central_parameters.json", "sources.json", "digitization.json",
        "figure14_eta_p_tree.csv", "figure19_total_1202.csv",
    ):
        assert _REFERENCES.joinpath(filename).is_file()
