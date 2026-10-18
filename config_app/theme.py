"""Light theme for M75 Config: soft grey page, white cards, blue accent."""

PAGE = "#eef0f4"
CARD = "#ffffff"
LINE = "#e3e6ec"
TEXT = "#1f2733"
MUTED = "#5d6776"
FAINT = "#9aa3b1"
ACCENT = "#3b82f6"
ACCENT_SOFT = "#e8f0fe"
DANGER = "#e5484d"
OK = "#22a06b"

STYLE = f"""
* {{ font-family: "Segoe UI"; font-size: 9.5pt; color: {TEXT}; }}
QMainWindow, QWidget#root {{ background: {PAGE}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: 0; }}
QFrame#card {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 12px; }}
QFrame#rule {{ background: {LINE}; max-height: 1px; min-height: 1px; border: 0; }}
QFrame#vrule {{ background: {LINE}; max-width: 1px; min-width: 1px; border: 0; }}
QWidget#side {{ background: transparent; }}
QLabel {{ background: transparent; }}
QLabel#device {{ font-size: 13pt; font-weight: 700; }}
QLabel#connected {{ color: {OK}; font-size: 8.5pt; }}
QLabel#disconnected {{ color: {DANGER}; font-size: 8.5pt; }}
QLabel#heading {{ font-size: 11pt; font-weight: 600; }}
QLabel#bigheading {{ font-size: 13pt; font-weight: 700; }}
QLabel#num {{ color: {ACCENT}; font-size: 8pt; }}
QLabel#note {{ color: {FAINT}; font-size: 8.5pt; }}
QLabel#warn {{ color: {DANGER}; font-size: 8.5pt; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#caps {{ color: {FAINT}; font-size: 8pt; }}
QLabel#value {{ color: {TEXT}; font-weight: 600; }}
QLabel#badge {{ background: {ACCENT}; color: white; border-radius: 4px; padding: 1px 5px; font-size: 7.5pt; font-weight: 600; }}
QLabel#chip {{ background: #e7f6ee; color: {OK}; border-radius: 4px; padding: 2px 8px; }}
QPushButton {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; padding: 6px 12px; color: {MUTED}; }}
QPushButton:hover {{ color: {TEXT}; border-color: #c7cdd6; background: #f7f8fa; }}
QPushButton:disabled {{ color: #c3c9d2; }}
QPushButton#save[dirty="true"] {{ background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: 600; }}
QPushButton#danger {{ color: {DANGER}; }}
QPushButton#danger:hover {{ border-color: {DANGER}; background: #fdeeee; }}
QPushButton#link {{ background: transparent; border: 0; padding: 0; color: {ACCENT}; }}
QPushButton#link:hover {{ text-decoration: underline; }}
QPushButton#seg {{ padding: 5px 10px; }}
QPushButton#seg:checked {{ color: {ACCENT}; border-color: {ACCENT}; background: {ACCENT_SOFT}; }}
QPushButton#nav {{ text-align: left; padding: 10px 14px; border: 1px solid {LINE}; border-radius: 8px; color: {TEXT}; }}
QPushButton#nav:checked {{ background: #dfe5ee; border-color: #cfd6e1; font-weight: 600; }}
QPushButton#config {{ text-align: left; padding: 9px 12px; border-radius: 8px; color: {TEXT}; }}
QPushButton#config:checked {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; color: {ACCENT}; font-weight: 600; }}
QPushButton#tag {{ border: 0; border-radius: 4px; padding: 2px 6px; font-size: 8pt; font-weight: 600; }}
QComboBox, QSpinBox {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; padding: 5px 8px; min-width: 90px; }}
QComboBox:hover, QSpinBox:hover {{ border-color: #c7cdd6; }}
QComboBox::drop-down {{ border: 0; width: 18px; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid {LINE}; selection-background-color: {ACCENT_SOFT}; selection-color: {TEXT}; outline: 0; }}
QCheckBox {{ color: {MUTED}; spacing: 8px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid #c3c9d2; border-radius: 4px; background: {CARD}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QSlider::groove:horizontal {{ height: 4px; background: {LINE}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: white; border: 2px solid {ACCENT}; width: 12px; height: 12px; margin: -6px 0; border-radius: 8px; }}
QMenu {{ background: {CARD}; border: 1px solid {LINE}; padding: 4px; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: #cfd6e1; min-height: 30px; border-radius: 4px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QDialog {{ background: {CARD}; }}
"""
