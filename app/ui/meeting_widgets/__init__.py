from PyQt6.QtWidgets import QLabel


def count_label(text: str, color: str, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(
        f"font-size: 15px; font-weight: {weight}; color: {color}; padding: 4px 14px;")
    return lbl
