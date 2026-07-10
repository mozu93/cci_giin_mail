from PyQt6.QtWidgets import QLineEdit

_STYLE = (
    "QLineEdit {"
    " border: 1px solid #94A3B8; border-radius: 4px;"
    " padding: 4px 8px; background: white; }"
    "QLineEdit:focus { border: 2px solid #1E40AF; }"
)


def style_search_input(line_edit: QLineEdit, max_width: int = 280) -> None:
    """検索欄を目立たせつつ、ウィンドウ幅に応じて際限なく伸びないようにする"""
    line_edit.setStyleSheet(_STYLE)
    line_edit.setMaximumWidth(max_width)
