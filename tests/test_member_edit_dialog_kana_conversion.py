def test_save_converts_fullwidth_kana_to_halfwidth(qtbot, db_session):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    dlg._member_number.setText("A-101")
    dlg._org_name.setText("四日市商会")
    dlg._org_kana.setText("ヨッカイチショウカイ")
    dlg._name.setText("四日市太郎")
    dlg._name_kana.setText("ヨッカイチ　タロウ")
    dlg._save()

    from app.services.member_service import get_members
    saved = next(m for m in get_members(db_session) if m.member_number == "A-101")
    assert saved.organization_kana == "ﾖｯｶｲﾁｼｮｳｶｲ"
    assert saved.name_kana == "ﾖｯｶｲﾁ ﾀﾛｳ"


def test_kana_field_converts_on_editing_finished(qtbot, db_session):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    dlg._org_kana.setText("スズキショウジ")
    dlg._org_kana.editingFinished.emit()
    assert dlg._org_kana.text() == "ｽｽﾞｷｼｮｳｼﾞ"

    dlg._name_kana.setText("タカハシジロウ")
    dlg._name_kana.editingFinished.emit()
    assert dlg._name_kana.text() == "ﾀｶﾊｼｼﾞﾛｳ"


def test_save_keeps_already_halfwidth_kana_unchanged(qtbot, db_session):
    from app.ui.dialogs.member_edit_dialog import MemberEditDialog
    dlg = MemberEditDialog(db_session, staff_name="担当者A")
    qtbot.addWidget(dlg)

    dlg._member_number.setText("A-102")
    dlg._org_name.setText("伊藤建設")
    dlg._org_kana.setText("ｲﾄｳｹﾝｾﾂ")
    dlg._name.setText("伊藤四郎")
    dlg._name_kana.setText("ｲﾄｳ ｼﾛｳ")
    dlg._save()

    from app.services.member_service import get_members
    saved = next(m for m in get_members(db_session) if m.member_number == "A-102")
    assert saved.organization_kana == "ｲﾄｳｹﾝｾﾂ"
    assert saved.name_kana == "ｲﾄｳ ｼﾛｳ"
