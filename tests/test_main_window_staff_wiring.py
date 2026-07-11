from PyQt6.QtWidgets import QTabWidget


def test_settings_and_template_tabs_receive_staff_name(qtbot):
    from app.ui.main_window import MainWindow
    window = MainWindow(staff_name="水谷")
    qtbot.addWidget(window)

    tab_widget = window.findChild(QTabWidget)
    template_tab = None
    settings_tab = None
    for i in range(tab_widget.count()):
        if tab_widget.tabText(i) == "テンプレート":
            template_tab = tab_widget.widget(i)
        elif tab_widget.tabText(i) == "設定":
            settings_tab = tab_widget.widget(i)

    assert template_tab is not None and template_tab._staff_name == "水谷"
    assert settings_tab is not None and settings_tab._staff_name == "水谷"
