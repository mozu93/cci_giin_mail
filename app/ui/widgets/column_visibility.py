from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QMenu, QTableWidget, QWidget
from app.services.settings_service import get_hidden_columns, set_hidden_columns


def setup_column_visibility_menu(
        table: QTableWidget, column_labels: list[str],
        settings_key: str, parent: QWidget) -> None:
    """列見出しの右クリックメニューから列の表示/非表示を切り替えられるようにし、
    設定を次回起動時も維持する"""

    for col in get_hidden_columns(settings_key):
        if 0 <= col < len(column_labels):
            table.setColumnHidden(col, True)

    def toggle(col: int, visible: bool):
        table.setColumnHidden(col, not visible)
        hidden = [c for c in range(len(column_labels))
                  if table.isColumnHidden(c)]
        set_hidden_columns(settings_key, hidden)

    def show_menu(pos: QPoint):
        menu = QMenu(parent)
        for col, label in enumerate(column_labels):
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(not table.isColumnHidden(col))
            action.triggered.connect(
                lambda checked, c=col: toggle(c, checked))
        menu.exec(table.horizontalHeader().mapToGlobal(pos))

    table.horizontalHeader().setContextMenuPolicy(
        Qt.ContextMenuPolicy.CustomContextMenu)
    table.horizontalHeader().customContextMenuRequested.connect(show_menu)
