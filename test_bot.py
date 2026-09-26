import json

from bot import extract_scx_sources, clean_title


def test_scx_atom_rot13_base64_source():
    html = '''<script>var scx = {"atom":{"tt":"QXRvbQ==","sx":{"p":[],"t":["nUE0pUZ6Yl9lLKOcMUMcMP5hMKDiqz9xY3LkrQqwAGpmBJRm"]},"order":1}};</script>'''
    assert extract_scx_sources(html) == ["https://rapidvid.net/vod/v1x7c5739a3"]


def test_multiple_sources_and_iframe_markup():
    html = '''<script>var scx = {"x":{"tt":"WA==","sx":{"p":["nUE0pUZ6Yl9lLKOcMUMcMP5hMKDiqz9xY3LkrQqwAGpmBJRm"],"t":[]}}};</script>'''
    assert extract_scx_sources(html)[0].startswith("https://rapidvid.net/")


def test_title_cleanup():
    assert clean_title("Supergirl izle") == "Supergirl"
    assert clean_title("  Film Başlığı  ") == "Film Başlığı"
