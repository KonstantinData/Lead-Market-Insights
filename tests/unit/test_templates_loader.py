import templates.loader as loader


def test_render_template(tmp_path, monkeypatch):
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "t.txt").write_text("Run: {{ run_id }}", encoding="utf-8")
    monkeypatch.setattr(loader, "TEMPLATE_ROOT", template_dir)
    result = loader.render_template("t.txt", {"run_id": "run-1"})
    assert result == "Run: run-1"
