from PyQt6.QtWidgets import QFileDialog
from app.ui.dialogs.import_dialog import ImportDialog


def test_on_file_loaded_populates_preview_table_and_headers(qtbot, db_session, monkeypatch):
    """Test that loading a file populates the preview table (rows + headers)."""
    headers = ["会員番号", "事業所名"]
    rows = [["A-001", "○○商事"], ["A-002", "△△産業"], ["A-003", "□□工業"]]

    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    dlg = ImportDialog(db_session)
    qtbot.addWidget(dlg)
    dlg._on_file_loaded("dummy.xlsx", headers, rows)

    # Verify table structure
    assert dlg._preview_table.columnCount() == 2
    assert dlg._preview_table.rowCount() == 3  # 3 rows of data

    # Verify header labels are actually wired via setHorizontalHeaderLabels
    assert dlg._preview_table.horizontalHeaderItem(0).text() == "会員番号"
    assert dlg._preview_table.horizontalHeaderItem(1).text() == "事業所名"

    # Verify table content
    assert dlg._preview_table.item(0, 0).text() == "A-001"
    assert dlg._preview_table.item(0, 1).text() == "○○商事"
    assert dlg._preview_table.item(1, 0).text() == "A-002"
    assert dlg._preview_table.item(1, 1).text() == "△△産業"
    assert dlg._preview_table.item(2, 0).text() == "A-003"
    assert dlg._preview_table.item(2, 1).text() == "□□工業"


def test_preview_table_limits_to_5_rows(qtbot, db_session, monkeypatch):
    """Test that preview table shows only first 5 rows even if file has more."""
    headers = ["ID", "Name"]
    rows = [[str(i), f"Row{i}"] for i in range(1, 11)]  # 10 rows

    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    dlg = ImportDialog(db_session)
    qtbot.addWidget(dlg)
    dlg._on_file_loaded("dummy.xlsx", headers, rows)

    # Should show only 5 rows in preview
    assert dlg._preview_table.rowCount() == 5
    assert dlg._preview_table.item(4, 0).text() == "5"


def test_preview_table_shows_correct_row_count_label(qtbot, db_session, monkeypatch):
    """Test that row count label shows total and preview row count."""
    headers = ["ID", "Name"]
    rows = [[str(i), f"Row{i}"] for i in range(1, 11)]  # 10 rows

    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    dlg = ImportDialog(db_session)
    qtbot.addWidget(dlg)
    dlg._on_file_loaded("dummy.xlsx", headers, rows)

    # Check label text
    assert "全 10 件中 先頭5件を表示" in dlg._row_count_label.text()


def test_import_button_enabled_after_file_load(qtbot, db_session, monkeypatch):
    """Test that import button is enabled after file is loaded."""
    headers = ["会員番号"]
    rows = [["A-001"]]

    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    dlg = ImportDialog(db_session)
    qtbot.addWidget(dlg)

    # Initially disabled
    assert not dlg._btn_import.isEnabled()

    # Enabled after file load
    dlg._on_file_loaded("dummy.xlsx", headers, rows)
    assert dlg._btn_import.isEnabled()


def test_browse_wires_file_dialog_and_load_member_file(qtbot, db_session, monkeypatch):
    """Test that _browse() itself (not just _on_file_loaded) populates the preview."""
    headers = ["会員番号", "事業所名"]
    rows = [["A-001", "○○商事"], ["A-002", "△△産業"]]

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("dummy.xlsx", "")))
    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    dlg = ImportDialog(db_session)
    qtbot.addWidget(dlg)

    dlg._browse()

    assert dlg._file_path.text() == "dummy.xlsx"
    assert dlg._preview_table.columnCount() == 2
    assert dlg._preview_table.rowCount() == 2
    assert dlg._preview_table.horizontalHeaderItem(0).text() == "会員番号"
    assert "全 2 件中 先頭2件を表示" in dlg._row_count_label.text()
    assert dlg._btn_import.isEnabled()


def test_auto_map_matches_email_columns_from_export_headers(qtbot, db_session, monkeypatch):
    """Test that email address/label columns (as produced by export) are auto-mapped."""
    headers = [
        "会員番号", "事業所名", "事業所名フリガナ", "役職名", "氏名", "氏名フリガナ",
        "会議所役職", "委員会",
        "メール1アドレス", "メール1ラベル",
        "メール2アドレス", "メール2ラベル",
        "メール3アドレス", "メール3ラベル",
        "メール4アドレス", "メール4ラベル",
        "メール5アドレス", "メール5ラベル",
    ]
    rows = [["111"] + [""] * (len(headers) - 1)]

    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    dlg = ImportDialog(db_session)
    qtbot.addWidget(dlg)
    dlg._on_file_loaded("dummy.xlsx", headers, rows)

    expected = {
        "email_1_address": "メール1アドレス", "email_1_label": "メール1ラベル",
        "email_2_address": "メール2アドレス", "email_2_label": "メール2ラベル",
        "email_3_address": "メール3アドレス", "email_3_label": "メール3ラベル",
        "email_4_address": "メール4アドレス", "email_4_label": "メール4ラベル",
        "email_5_address": "メール5アドレス", "email_5_label": "メール5ラベル",
    }
    for field_key, header in expected.items():
        combo = dlg._combos[field_key]
        assert combo.currentText() == header, (
            f"{field_key} should auto-map to '{header}' but got "
            f"'{combo.currentText()}'")


def test_browse_returns_early_when_no_file_selected(qtbot, db_session, monkeypatch):
    """Test that cancelling the file dialog leaves the preview untouched."""
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("", "")))

    dlg = ImportDialog(db_session)
    qtbot.addWidget(dlg)

    dlg._browse()

    assert dlg._file_path.text() == ""
    assert not dlg._btn_import.isEnabled()
