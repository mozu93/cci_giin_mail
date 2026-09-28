from PyQt6.QtWidgets import QApplication, QLabel

from app.ui import theme


def test_light_and_dark_define_same_color_names():
    assert set(theme._LIGHT) == set(theme._DARK)


def test_global_style_uses_only_defined_color_names(monkeypatch):
    for dark in (False, True):
        monkeypatch.setattr(theme, "is_dark", lambda d=dark: d)
        rendered = theme.render(theme._GLOBAL_STYLE)
        assert "${" not in rendered


def test_style_switches_colors_when_windows_mode_changes(qtbot, monkeypatch):
    label = QLabel()
    qtbot.addWidget(label)

    monkeypatch.setattr(theme, "is_dark", lambda: False)
    theme.style(label, "color: ${danger};")
    assert label.styleSheet() == f"color: {theme._LIGHT['danger']};"

    app = QApplication.instance()
    original_palette = app.palette()
    original_style_sheet = app.styleSheet()
    monkeypatch.setattr(theme, "is_dark", lambda: True)
    try:
        theme._on_color_scheme_changed(None)
        assert label.styleSheet() == f"color: {theme._DARK['danger']};"
        assert app.palette().base().color().name().upper() == theme._DARK["base"]
    finally:
        app.setPalette(original_palette)
        app.setStyleSheet(original_style_sheet)
