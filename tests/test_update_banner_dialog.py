import pytest
from PyQt6.QtWidgets import QMessageBox

from app.ui import update_banner as ub


@pytest.fixture
def banner(qtbot, monkeypatch):
    monkeypatch.setattr(ub.UpdateBanner, "check_now", lambda self, manual=False: None)
    b = ub.UpdateBanner()
    qtbot.addWidget(b)
    return b


def _answer(monkeypatch, button):
    calls = []

    def fake_question(*args, **kwargs):
        calls.append(args)
        return button

    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
    return calls


def test_dialog_shown_when_update_found(banner, monkeypatch):
    calls = _answer(monkeypatch, QMessageBox.StandardButton.No)
    banner._on_update_found("v9.9.9", "https://github.com/x", "0" * 64)
    assert len(calls) == 1
    assert banner.isHidden() is False or banner._lbl.text().find("v9.9.9") >= 0


def test_dialog_not_repeated_for_same_tag_on_auto_check(banner, monkeypatch):
    calls = _answer(monkeypatch, QMessageBox.StandardButton.No)
    banner._on_update_found("v9.9.9", "https://github.com/x", "0" * 64)
    banner._on_update_found("v9.9.9", "https://github.com/x", "0" * 64)
    assert len(calls) == 1


def test_dialog_shown_again_on_manual_check(banner, monkeypatch):
    calls = _answer(monkeypatch, QMessageBox.StandardButton.No)
    banner._on_update_found("v9.9.9", "https://github.com/x", "0" * 64)
    banner._manual_check = True
    banner._on_update_found("v9.9.9", "https://github.com/x", "0" * 64)
    assert len(calls) == 2


def test_yes_starts_download(banner, monkeypatch):
    _answer(monkeypatch, QMessageBox.StandardButton.Yes)
    started = []
    monkeypatch.setattr(banner, "_start_download", lambda: started.append(True))
    banner._on_update_found("v9.9.9", "https://github.com/x", "0" * 64)
    assert started == [True]
    assert banner._install_after_download is True
