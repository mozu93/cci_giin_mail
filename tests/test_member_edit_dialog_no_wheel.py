from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent


def _make_wheel_event() -> QWheelEvent:
    return QWheelEvent(
        QPointF(10, 10), QPointF(10, 10),
        QPoint(0, 0), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )


def test_position_combo_ignores_wheel_scroll(qtbot, db_session):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    before = dlg._position_combo.currentIndex()
    event = _make_wheel_event()
    dlg._position_combo.wheelEvent(event)

    assert dlg._position_combo.currentIndex() == before
    assert event.isAccepted() is False
