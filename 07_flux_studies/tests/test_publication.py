import pytest


def test_input_and_existing_destination_are_protected(tmp_path):
    from flux_studies.reporting import publish_output
    source = tmp_path/'raw.root'; source.write_bytes(b'measured')
    with pytest.raises(ValueError):
        with publish_output(tmp_path, [source]): pass
    link=tmp_path/'link';link.symlink_to(source)
    with pytest.raises((ValueError, FileExistsError)):
        with publish_output(link, [source]): pass
    assert source.read_bytes()==b'measured'


def test_changed_input_cancels_publication(tmp_path):
    from flux_studies.reporting import publish_output
    source=tmp_path/'raw.root';source.write_bytes(b'before')
    output=tmp_path/'out'
    with pytest.raises(ValueError, match='changed'):
        with publish_output(output,[source]) as staged:
            (staged/'audit.json').write_text('{}')
            source.write_bytes(b'after')
    assert not output.exists()
