import pytest
from PyQt6.QtWidgets import QTabWidget
from app.ui.main_window import MainWindow


@pytest.fixture
def main_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    return window


def test_main_window_creates(main_window):
    """メインウィンドウが正常に生成される"""
    assert main_window is not None


def test_main_window_title(main_window):
    """ウィンドウタイトルが正しい"""
    assert main_window.windowTitle() == "商工会議所メール配信システム"


def test_main_window_has_six_tabs(main_window):
    """タブが6つ存在する"""
    tab_widget = main_window.centralWidget()
    assert isinstance(tab_widget, QTabWidget)
    assert tab_widget.count() == 6


def test_main_window_tab_names(main_window):
    """各タブのラベルが正しい"""
    tab_widget = main_window.centralWidget()
    tab_labels = [tab_widget.tabText(i) for i in range(tab_widget.count())]
    assert "名簿管理" in tab_labels
    assert "会議管理" in tab_labels
    assert "メール送信" in tab_labels
    assert "テンプレート" in tab_labels
    assert "設定" in tab_labels
    assert "送信履歴" in tab_labels
