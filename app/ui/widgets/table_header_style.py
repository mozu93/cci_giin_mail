from PyQt6.QtWidgets import QTableWidget

_STYLE = (
    "QHeaderView::section {"
    " background-color: #1E293B; color: white;"
    " padding: 4px; font-weight: bold; border: 1px solid #334155; }"
)


def style_table_header(table: QTableWidget) -> None:
    table.horizontalHeader().setStyleSheet(_STYLE)
