from PyQt6.QtCore import Qt


def test_preentry_table_has_column_visibility_menu(qtbot):
    from app.ui.meeting_widgets.preentry_widget import PreentryWidget
    w = PreentryWidget()
    qtbot.addWidget(w)
    assert w._pre_table.horizontalHeader().contextMenuPolicy() == \
        Qt.ContextMenuPolicy.CustomContextMenu


def test_reception_table_has_column_visibility_menu(qtbot):
    from app.ui.meeting_widgets.reception_widget import ReceptionWidget
    w = ReceptionWidget(staff_name="担当者A")
    qtbot.addWidget(w)
    assert w._rec_table.horizontalHeader().contextMenuPolicy() == \
        Qt.ContextMenuPolicy.CustomContextMenu


def test_log_table_has_column_visibility_menu(qtbot):
    from app.ui.meeting_widgets.log_widget import LogWidget
    w = LogWidget()
    qtbot.addWidget(w)
    assert w._log_table.horizontalHeader().contextMenuPolicy() == \
        Qt.ContextMenuPolicy.CustomContextMenu
