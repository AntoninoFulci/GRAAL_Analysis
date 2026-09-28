from __future__ import annotations

from io import StringIO


def _scripted_input(*answers):
    iterator = iter(answers)
    return lambda _prompt="": next(iterator)


def test_main_menu_shows_descriptions_and_exits():
    from graal_pipeline.cli import run_wizard

    output = StringIO()

    assert run_wizard(input_fn=_scripted_input("7"), output=output) == 0
    text = output.getvalue()
    assert "GRAAL Pipeline" in text
    assert "Continua ultima esecuzione" in text
    assert "Riparte dal primo checkpoint incompleto" in text
    assert "Estrai osservabile" in text
    assert "Calcola quantità fisiche" in text


def test_observable_hierarchy_shows_final_states_and_disabled_cross_section():
    from graal_pipeline.cli import run_wizard

    output = StringIO()
    run_wizard(
        input_fn=_scripted_input("4", "1", "1", "?", "6", "7"),
        output=output,
    )

    text = output.getvalue()
    assert "Stato finale" in text
    assert "eta pi0" in text
    assert "Asimmetria del fascio" in text
    assert "Estrae Sigma da campioni polarizzati" in text
    assert "Sezione d'urto [non disponibile]" in text
    assert "Estrazione finale" in text
    assert "Prima passata non corretta" in text
    assert "Configurazione avanzata" in text


def test_policy_prompt_handles_old_stale_and_untracked():
    from graal_pipeline.model import ArtifactState
    from graal_pipeline.cli import ask_state_policy

    output = StringIO()
    assert ask_state_policy(
        ArtifactState.OLD, input_fn=_scripted_input("2"), output=output
    ) == "reuse"
    assert ask_state_policy(
        ArtifactState.STALE, input_fn=_scripted_input("1"), output=output
    ) == "rebuild"
    assert ask_state_policy(
        ArtifactState.UNTRACKED, input_fn=_scripted_input("1"), output=output
    ) == "adopt"
    assert "validare e adottare" in output.getvalue().casefold()


def test_confirmation_requires_explicit_yes():
    from graal_pipeline.cli import confirm_plan

    output = StringIO()
    assert confirm_plan(input_fn=_scripted_input("no"), output=output) is False
    assert confirm_plan(input_fn=_scripted_input("sì"), output=output) is True
