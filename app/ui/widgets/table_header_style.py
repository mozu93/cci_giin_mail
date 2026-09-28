from PyQt6.QtWidgets import QTableWidget
from app.ui.theme import style

_STYLE = (
    "QHeaderView::section {"
    " background-color: ${header}; color: ${header_text};"
    " padding: 4px; font-weight: bold; border: 1px solid ${header_border}; }"
)


def style_table_header(table: QTableWidget) -> None:
    style(table.horizontalHeader(), _STYLE)
