from types import SimpleNamespace

from app.ui.send_tab import SendTab


class _Label:
    def __init__(self):
        self.text = ""
        self.tooltip = ""

    def setText(self, t):
        self.text = t

    def setToolTip(self, t):
        self.tooltip = t


def _make_stub():
    stub = SimpleNamespace(_common_attachments=[], _common_label=_Label())
    stub._refresh_common_label = lambda: SendTab._refresh_common_label(stub)
    return stub


def test_add_common_attach_paths_appends_across_calls():
    stub = _make_stub()
    SendTab._add_common_attach_paths(stub, [r"C:\a\one.pdf"])
    SendTab._add_common_attach_paths(stub, [r"C:\a\two.pdf"])
    assert stub._common_attachments == [r"C:\a\one.pdf", r"C:\a\two.pdf"]
    assert stub._common_label.text == "2件: one.pdf, two.pdf"
    assert stub._common_label.tooltip == "\n".join(
        [r"C:\a\one.pdf", r"C:\a\two.pdf"])


def test_add_common_attach_paths_skips_duplicates():
    stub = _make_stub()
    SendTab._add_common_attach_paths(stub, [r"C:\a\one.pdf", r"C:\a\one.pdf"])
    SendTab._add_common_attach_paths(stub, [r"C:\a\one.pdf"])
    assert stub._common_attachments == [r"C:\a\one.pdf"]
    assert stub._common_label.text == "1件: one.pdf"


def test_clear_common_attach_resets_label():
    stub = _make_stub()
    SendTab._add_common_attach_paths(stub, [r"C:\a\one.pdf"])
    SendTab._clear_common_attach(stub)
    assert stub._common_attachments == []
    assert stub._common_label.text == "（未選択）"
    assert stub._common_label.tooltip == ""
