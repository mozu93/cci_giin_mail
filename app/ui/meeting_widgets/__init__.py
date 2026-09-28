from PyQt6.QtWidgets import QLabel
from app.ui.theme import style


def count_label(text: str, color: str, bold: bool = False) -> QLabel:
    """color は app.ui.theme の配色名（例: "success"）"""
    lbl = QLabel(text)
    weight = "bold" if bold else "normal"
    style(lbl, f"font-size: 15px; font-weight: {weight}; color: ${{{color}}}; padding: 4px 14px;")
    return lbl
