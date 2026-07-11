from PyQt6.QtWidgets import QGroupBox


class _FakeSession:
    def close(self):
        pass


def _patch_common(monkeypatch):
    monkeypatch.setattr("app.ui.send_tab.get_session", lambda: _FakeSession())
    monkeypatch.setattr("app.ui.send_tab.get_positions", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_committees", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_members", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_templates", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_signatures", lambda s: [])
    monkeypatch.setattr("app.ui.send_tab.get_default_signature", lambda s: None)


def test_step_titles_without_dev_flag(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    assert not hasattr(tab, "_merge_status")
    titles = [grp.title() for grp in tab.findChildren(QGroupBox)]
    assert "Step 1：宛先条件" in titles
    assert "Step 2：テンプレート・署名選択" in titles
    assert "Step 3：添付ファイル（任意）" in titles
    assert "Step 4：最終確認・送信" in titles
    assert not any("差し込みデータ" in t for t in titles)


def test_step_titles_with_dev_flag(qtbot, monkeypatch):
    monkeypatch.setenv("CCI_MAIL_DEV_TOOLS", "1")
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)

    assert hasattr(tab, "_merge_status")
    titles = [grp.title() for grp in tab.findChildren(QGroupBox)]
    assert "Step 3：差し込みデータ（任意）" in titles
    assert "Step 4：添付ファイル（任意）" in titles
    assert "Step 5：最終確認・送信" in titles


def test_clear_all_does_not_crash_without_merge_section(qtbot, monkeypatch):
    monkeypatch.delenv("CCI_MAIL_DEV_TOOLS", raising=False)
    _patch_common(monkeypatch)
    from app.ui.send_tab import SendTab
    tab = SendTab(staff_name="担当者A")
    qtbot.addWidget(tab)
    tab._clear_all()  # 例外が発生しないこと
