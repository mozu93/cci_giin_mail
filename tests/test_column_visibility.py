from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QMenu, QTableWidget, QWidget


def _trigger_context_menu(table, monkeypatch):
    """コンテキストメニューを実際には表示せず、生成されたQMenuを捕捉する"""
    captured = {}

    def fake_exec(self, *args, **kwargs):
        captured["menu"] = self
        return None

    monkeypatch.setattr(QMenu, "exec", fake_exec)
    table.horizontalHeader().customContextMenuRequested.emit(QPoint(0, 0))
    return captured["menu"]


def test_toggling_column_off_hides_it_and_persists(qtbot, monkeypatch):
    saved = {}
    monkeypatch.setattr(
        "app.ui.widgets.column_visibility.get_hidden_columns", lambda key: [])
    monkeypatch.setattr(
        "app.ui.widgets.column_visibility.set_hidden_columns",
        lambda key, hidden: saved.__setitem__(key, hidden))

    from app.ui.widgets.column_visibility import setup_column_visibility_menu
    parent = QWidget()
    qtbot.addWidget(parent)
    table = QTableWidget(0, 3, parent)
    labels = ["A", "B", "C"]
    table.setHorizontalHeaderLabels(labels)
    setup_column_visibility_menu(table, labels, "my_table", parent)

    assert table.horizontalHeader().contextMenuPolicy() == \
        Qt.ContextMenuPolicy.CustomContextMenu
    assert table.isColumnHidden(1) is False

    menu = _trigger_context_menu(table, monkeypatch)
    actions = menu.actions()
    assert [a.text() for a in actions] == labels
    assert all(a.isChecked() for a in actions)

    actions[1].setChecked(False)
    actions[1].triggered.emit(False)

    assert table.isColumnHidden(1) is True
    assert saved["my_table"] == [1]


def test_toggling_column_back_on_shows_it_again(qtbot, monkeypatch):
    saved = {}
    monkeypatch.setattr(
        "app.ui.widgets.column_visibility.get_hidden_columns", lambda key: [])
    monkeypatch.setattr(
        "app.ui.widgets.column_visibility.set_hidden_columns",
        lambda key, hidden: saved.__setitem__(key, hidden))

    from app.ui.widgets.column_visibility import setup_column_visibility_menu
    parent = QWidget()
    qtbot.addWidget(parent)
    table = QTableWidget(0, 3, parent)
    labels = ["A", "B", "C"]
    table.setHorizontalHeaderLabels(labels)
    setup_column_visibility_menu(table, labels, "my_table", parent)

    table.setColumnHidden(1, True)
    menu = _trigger_context_menu(table, monkeypatch)
    actions = menu.actions()
    assert actions[1].isChecked() is False

    actions[1].setChecked(True)
    actions[1].triggered.emit(True)

    assert table.isColumnHidden(1) is False
    assert saved["my_table"] == []


def test_hidden_columns_restored_on_setup(qtbot, monkeypatch):
    monkeypatch.setattr(
        "app.ui.widgets.column_visibility.get_hidden_columns",
        lambda key: [1] if key == "my_table" else [])
    monkeypatch.setattr(
        "app.ui.widgets.column_visibility.set_hidden_columns",
        lambda key, hidden: None)

    from app.ui.widgets.column_visibility import setup_column_visibility_menu
    parent = QWidget()
    qtbot.addWidget(parent)
    table = QTableWidget(0, 3, parent)
    labels = ["A", "B", "C"]
    table.setHorizontalHeaderLabels(labels)
    setup_column_visibility_menu(table, labels, "my_table", parent)

    assert table.isColumnHidden(1) is True
    assert table.isColumnHidden(0) is False
    assert table.isColumnHidden(2) is False
