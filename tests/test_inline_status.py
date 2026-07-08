from PyQt6.QtWidgets import QLabel


def test_show_inline_message_sets_text_and_clears_after_timeout(qtbot):
    from app.ui.widgets.inline_status import show_inline_message
    label = QLabel()
    qtbot.addWidget(label)

    show_inline_message(label, "保存しました", ms=100)
    assert label.text() == "保存しました"

    qtbot.waitUntil(lambda: label.text() == "", timeout=1000)
