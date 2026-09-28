"""画面の配色（ライト／ダーク）を Windows の設定に合わせて切り替える。

色は画面ごとに直接書かず、ここの名前（例: "danger"）で参照する。
style() で設定したスタイルシートは、起動中に Windows 側の設定が
切り替わったときにも自動で塗り直される。
"""
from string import Template

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPalette, QPen
from PyQt6.QtWidgets import QApplication, QProxyStyle, QStyle, QWidget

_LIGHT = {
    # 基本
    "window": "#F5F7FA",
    "base": "#FFFFFF",
    "alt_base": "#F8FAFC",
    "text": "#1E293B",
    "text_muted": "#64748B",
    "text_faint": "#94A3B8",
    "border": "#CBD5E1",
    "border_strong": "#94A3B8",
    "selection": "#BFDBFE",
    "selection_text": "#0F172A",
    # タブ・スクロールバーなど Qt が描く部品の地色
    "chrome": "#F0F4F8",
    # ボタン
    "button": "#F0F4F8",
    "button_hover": "#DBEAFE",
    "button_hover_border": "#3B82F6",
    "button_hover_text": "#1D4ED8",
    "button_pressed": "#BFDBFE",
    "button_pressed_border": "#2563EB",
    "button_disabled": "#F1F5F9",
    "button_disabled_border": "#CBD5E1",
    "button_disabled_text": "#94A3B8",
    "focus": "#3B82F6",
    "indicator_border": "#64748B",
    # 意味のある文字色
    "accent": "#1E40AF",
    "accent_border": "#BFDBFE",
    "danger": "#DC2626",
    "success": "#16A34A",
    "warning": "#CA8A04",
    "info": "#2563EB",
    "purple": "#7C3AED",
    "orange": "#F97316",
    # 塗りつぶしボタン（白文字）
    "primary_fill": "#1E40AF",
    "danger_fill": "#DC2626",
    "info_fill": "#2563EB",
    "info_fill_hover": "#1D4ED8",
    "success_fill": "#16A34A",
    "success_fill_hover": "#15803D",
    "on_fill": "#FFFFFF",
    # 表の見出し
    "header": "#1E293B",
    "header_text": "#FFFFFF",
    "header_border": "#334155",
    # 行・欄の背景（淡い色）
    "tint_green": "#DCFCE7",
    "tint_blue": "#DBEAFE",
    "tint_yellow": "#FEF9C3",
    "tint_red": "#FEE2E2",
    "tint_amber": "#FEF3C7",
    "table_selection": "#C8E9FA",
    "table_selection_text": "#000000",
    # 注意表示（テストモード・更新のお知らせ）
    "notice": "#FEF3C7",
    "notice_text": "#92400E",
    "banner": "#FEF9C3",
    "banner_border": "#FDE047",
    "banner_text": "#713F12",
    # 顔写真枠
    "photo_bg": "#F3F4F6",
    "photo_border": "#D1D5DB",
    # ステータスバー
    "statusbar": "#F8FAFC",
    "statusbar_border": "#E2E8F0",
    # ログイン画面の閲覧専用ボタン
    "subtle_button": "#F1F5F9",
    "subtle_button_hover": "#E2E8F0",
    "subtle_button_text": "#475569",
}

_DARK = {
    "window": "#1E1F22",
    "base": "#2B2D31",
    "alt_base": "#313338",
    "text": "#E5E7EB",
    "text_muted": "#9CA3AF",
    "text_faint": "#6B7280",
    "border": "#4B5563",
    "border_strong": "#6B7280",
    "selection": "#1E40AF",
    "selection_text": "#FFFFFF",
    "chrome": "#2B2D31",
    "button": "#374151",
    "button_hover": "#1E3A8A",
    "button_hover_border": "#60A5FA",
    "button_hover_text": "#DBEAFE",
    "button_pressed": "#1E40AF",
    "button_pressed_border": "#93C5FD",
    "button_disabled": "#2B2D31",
    "button_disabled_border": "#374151",
    "button_disabled_text": "#6B7280",
    "focus": "#60A5FA",
    "indicator_border": "#9CA3AF",
    "accent": "#93C5FD",
    "accent_border": "#1E40AF",
    "danger": "#F87171",
    "success": "#4ADE80",
    "warning": "#FACC15",
    "info": "#60A5FA",
    "purple": "#C4B5FD",
    "orange": "#FB923C",
    "primary_fill": "#2563EB",
    "danger_fill": "#DC2626",
    "info_fill": "#2563EB",
    "info_fill_hover": "#1D4ED8",
    "success_fill": "#16A34A",
    "success_fill_hover": "#15803D",
    "on_fill": "#FFFFFF",
    "header": "#111827",
    "header_text": "#F3F4F6",
    "header_border": "#374151",
    "tint_green": "#14532D",
    "tint_blue": "#1E3A8A",
    "tint_yellow": "#713F12",
    "tint_red": "#7F1D1D",
    "tint_amber": "#78350F",
    "table_selection": "#1D4ED8",
    "table_selection_text": "#FFFFFF",
    "notice": "#78350F",
    "notice_text": "#FEF3C7",
    "banner": "#422006",
    "banner_border": "#A16207",
    "banner_text": "#FEF08A",
    "photo_bg": "#313338",
    "photo_border": "#4B5563",
    "statusbar": "#1E1F22",
    "statusbar_border": "#374151",
    "subtle_button": "#313338",
    "subtle_button_hover": "#3F4147",
    "subtle_button_text": "#D1D5DB",
}

_GLOBAL_STYLE = """
QPushButton {
    background-color: ${button};
    border: 1px solid ${border_strong};
    border-radius: 4px;
    padding: 4px 10px;
    color: ${text};
    min-height: 26px;
}
QPushButton:hover {
    background-color: ${button_hover};
    border-color: ${button_hover_border};
    color: ${button_hover_text};
}
QPushButton:pressed {
    background-color: ${button_pressed};
    border-color: ${button_pressed_border};
}
QPushButton:disabled {
    background-color: ${button_disabled};
    border-color: ${button_disabled_border};
    color: ${button_disabled_text};
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit {
    border: 1px solid ${border};
    border-radius: 3px;
    padding: 3px 6px;
    background-color: ${base};
    color: ${text};
    selection-background-color: ${selection};
    selection-color: ${selection_text};
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: ${focus};
}
QGroupBox {
    font-weight: bold;
    border: 1px solid ${border};
    border-radius: 4px;
    margin-top: 6px;
    padding-top: 4px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
"""

_STYLE_PROPERTY = "_theme_style_template"
_watching = False


def is_dark() -> bool:
    hints = QGuiApplication.styleHints()
    return hints is not None and hints.colorScheme() == Qt.ColorScheme.Dark


def colors() -> dict[str, str]:
    return _DARK if is_dark() else _LIGHT


def color(name: str) -> str:
    """配色名から現在のモードの色（#RRGGBB）を返す。"""
    return colors()[name]


def qcolor(name: str) -> QColor:
    return QColor(color(name))


def render(template: str) -> str:
    """${名前} を現在のモードの色に置き換えたスタイルシートを返す。"""
    return Template(template).substitute(colors())


def style(widget: QWidget, template: str) -> None:
    """配色名入りのスタイルシートを設定する。モード切替時にも塗り直される。"""
    widget.setProperty(_STYLE_PROPERTY, template)
    widget.setStyleSheet(render(template))


def _build_palette() -> QPalette:
    c = colors()
    p = QPalette()
    role = QPalette.ColorRole
    p.setColor(role.Window, QColor(c["window"]))
    p.setColor(role.WindowText, QColor(c["text"]))
    p.setColor(role.Base, QColor(c["base"]))
    p.setColor(role.AlternateBase, QColor(c["alt_base"]))
    p.setColor(role.Text, QColor(c["text"]))
    p.setColor(role.Button, QColor(c["chrome"]))
    p.setColor(role.ButtonText, QColor(c["text"]))
    p.setColor(role.BrightText, QColor(c["danger"]))
    p.setColor(role.ToolTipBase, QColor(c["base"]))
    p.setColor(role.ToolTipText, QColor(c["text"]))
    p.setColor(role.PlaceholderText, QColor(c["text_faint"]))
    p.setColor(role.Highlight, QColor(c["selection"]))
    p.setColor(role.HighlightedText, QColor(c["selection_text"]))
    p.setColor(role.Link, QColor(c["info"]))
    p.setColor(role.LinkVisited, QColor(c["purple"]))
    p.setColor(role.Light, QColor(c["alt_base"]))
    p.setColor(role.Midlight, QColor(c["border"]))
    p.setColor(role.Mid, QColor(c["border_strong"]))
    p.setColor(role.Dark, QColor(c["border_strong"]))
    p.setColor(role.Shadow, QColor("#000000"))
    disabled = QPalette.ColorGroup.Disabled
    for r in (role.WindowText, role.Text, role.ButtonText):
        p.setColor(disabled, r, QColor(c["text_faint"]))
    return p


class _AppStyle(QProxyStyle):
    """Fusion のチェックボックス等は枠が薄く見落としやすいため、枠線を描き足す。"""

    _CHECK_ELEMENTS = (
        QStyle.PrimitiveElement.PE_IndicatorCheckBox,
        QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck,
    )

    def drawPrimitive(self, element, option, painter, widget=None):
        super().drawPrimitive(element, option, painter, widget)
        is_check = element in self._CHECK_ELEMENTS
        is_radio = element == QStyle.PrimitiveElement.PE_IndicatorRadioButton
        if not (is_check or is_radio):
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(qcolor("indicator_border"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(option.rect).adjusted(0.5, 0.5, -0.5, -0.5)
        if is_radio:
            painter.drawEllipse(rect.adjusted(1, 1, -1, -1))
        else:
            painter.drawRoundedRect(rect, 2, 2)
        painter.restore()


def _apply_global(app: QApplication) -> None:
    app.setPalette(_build_palette())
    app.setStyleSheet(render(_GLOBAL_STYLE))


def _restyle_widgets() -> None:
    for widget in QApplication.allWidgets():
        template = widget.property(_STYLE_PROPERTY)
        if template:
            widget.setStyleSheet(render(template))


def _on_color_scheme_changed(_scheme) -> None:
    app = QApplication.instance()
    if app is None:
        return
    _apply_global(app)
    _restyle_widgets()


def apply_theme(app: QApplication) -> None:
    """起動時に1回呼ぶ。Windows のライト／ダーク設定に合わせて配色する。"""
    global _watching
    # Windows 標準スタイルはダーク配色に追従しないため、配色を細かく指定できる Fusion を使う。
    app.setStyle(_AppStyle("Fusion"))
    _apply_global(app)
    if not _watching:
        QGuiApplication.styleHints().colorSchemeChanged.connect(
            _on_color_scheme_changed)
        _watching = True
