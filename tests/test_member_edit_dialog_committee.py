from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from app.services.committee_service import create_committee


def test_committee_combo_populated_and_saved(qtbot, db_session):
    c1 = create_committee(db_session, "総務・運営委員会", 1)
    create_committee(db_session, "地域経済推進委員会", 2)

    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    assert dlg._committee_combo.count() == 3  # （なし）+ 2委員会

    for i in range(dlg._committee_combo.count()):
        if dlg._committee_combo.itemData(i) == c1.id:
            dlg._committee_combo.setCurrentIndex(i)
            break

    dlg._member_number.setText("A-100")
    dlg._org_name.setText("テスト商事")
    dlg._name.setText("山田太郎")
    dlg._save()

    from app.services.member_service import get_members
    saved = next(m for m in get_members(db_session) if m.member_number == "A-100")
    assert saved.committee_id == c1.id


def test_committee_combo_ignores_wheel_scroll(qtbot, db_session):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    before = dlg._committee_combo.currentIndex()
    event = QWheelEvent(
        QPointF(10, 10), QPointF(10, 10),
        QPoint(0, 0), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )
    dlg._committee_combo.wheelEvent(event)
    assert dlg._committee_combo.currentIndex() == before
