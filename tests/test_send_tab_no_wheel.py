from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent

from app.ui.send_tab import _NoWheelComboBox


def _make_wheel_event() -> QWheelEvent:
    return QWheelEvent(
        QPointF(10, 10), QPointF(10, 10),
        QPoint(0, 0), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )


def test_send_tab_combo_ignores_wheel_scroll(qtbot):
    combo = _NoWheelComboBox()
    qtbot.addWidget(combo)
    combo.addItems(["1", "2", "3"])
    combo.setCurrentIndex(1)

    event = _make_wheel_event()
    combo.wheelEvent(event)

    assert combo.currentIndex() == 1
    assert event.isAccepted() is False
