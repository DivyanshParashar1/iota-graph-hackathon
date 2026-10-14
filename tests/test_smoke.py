def test_import():
    import ripple
    from ripple.config import get_settings

    assert ripple.ROOT.exists()
    assert get_settings().ripple_db_mode in ("embedded", "remote")
