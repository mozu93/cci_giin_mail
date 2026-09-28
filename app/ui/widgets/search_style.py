from PyQt6.QtWidgets import QLineEdit
from app.ui.theme import style

_STYLE = (
    "QLineEdit {"
    " border: 1px solid ${border_strong}; border-radius: 4px;"
    " padding: 4px 8px; background: ${base}; }"
    "QLineEdit:focus { border: 2px solid ${focus}; }"
)


def style_search_input(line_edit: QLineEdit, max_width: int = 280) -> None:
    """検索欄を目立たせつつ、ウィンドウ幅に応じて際限なく伸びないようにする"""
    style(line_edit, _STYLE)
    line_edit.setMaximumWidth(max_width)
