import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.ui.dialogs.import_dialog import ImportDialog


@pytest.fixture
def app():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def db_session():
    """Create in-memory database session for tests."""
    engine = create_engine("sqlite:///:memory:")
    Session = __import__('sqlalchemy.orm', fromlist=['Session']).sessionmaker(bind=engine)
    return Session()


def test_browse_populates_preview_table(app, db_session, monkeypatch):
    """Test that loading a file populates the preview table with first 5 rows."""
    headers = ["会員番号", "事業所名"]
    rows = [["A-001", "○○商事"], ["A-002", "△△産業"], ["A-003", "□□工業"]]

    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    dlg = ImportDialog(db_session)
    dlg._on_file_loaded("dummy.xlsx", headers, rows)

    # Verify table structure
    assert dlg._preview_table.columnCount() == 2
    assert dlg._preview_table.rowCount() == 3  # 3 rows of data

    # Verify table content
    assert dlg._preview_table.item(0, 0).text() == "A-001"
    assert dlg._preview_table.item(0, 1).text() == "○○商事"
    assert dlg._preview_table.item(1, 0).text() == "A-002"
    assert dlg._preview_table.item(1, 1).text() == "△△産業"
    assert dlg._preview_table.item(2, 0).text() == "A-003"
    assert dlg._preview_table.item(2, 1).text() == "□□工業"


def test_preview_table_limits_to_5_rows(app, db_session, monkeypatch):
    """Test that preview table shows only first 5 rows even if file has more."""
    headers = ["ID", "Name"]
    rows = [[str(i), f"Row{i}"] for i in range(1, 11)]  # 10 rows

    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    dlg = ImportDialog(db_session)
    dlg._on_file_loaded("dummy.xlsx", headers, rows)

    # Should show only 5 rows in preview
    assert dlg._preview_table.rowCount() == 5
    assert dlg._preview_table.item(4, 0).text() == "5"


def test_preview_table_shows_correct_row_count_label(app, db_session, monkeypatch):
    """Test that row count label shows total and preview row count."""
    headers = ["ID", "Name"]
    rows = [[str(i), f"Row{i}"] for i in range(1, 11)]  # 10 rows

    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    dlg = ImportDialog(db_session)
    dlg._on_file_loaded("dummy.xlsx", headers, rows)

    # Check label text
    assert "全 10 件中 先頭5件を表示" in dlg._row_count_label.text()


def test_import_button_enabled_after_file_load(app, db_session, monkeypatch):
    """Test that import button is enabled after file is loaded."""
    headers = ["会員番号"]
    rows = [["A-001"]]

    monkeypatch.setattr(
        "app.ui.dialogs.import_dialog.load_member_file",
        lambda path: (headers, rows))

    dlg = ImportDialog(db_session)

    # Initially disabled
    assert not dlg._btn_import.isEnabled()

    # Enabled after file load
    dlg._on_file_loaded("dummy.xlsx", headers, rows)
    assert dlg._btn_import.isEnabled()
