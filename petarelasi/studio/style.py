STYLE = '''
QWidget { color: #203b3a; font-family: "Segoe UI", "DejaVu Sans", sans-serif; font-size: 13px; }
QMainWindow { background: #f6f7f3; }
QWidget#header { background: #fcfdf9; border-bottom: 1px solid #dce4db; }
QLabel#brand { font-size: 25px; font-weight: 700; letter-spacing: -0.7px; }
QLabel#eyebrow { color: #6b7d70; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#subtitle { color: #728077; font-size: 12px; }
QLabel#pill { background: #e4eee4; color: #3d6754; padding: 6px 11px; border-radius: 10px; font-size: 11px; }
QWidget#inputPanel, QWidget#notesPanel { background: #fcfdf9; }
QLabel#section { font-size: 16px; font-weight: 700; }
QLabel#muted { color: #78867c; font-size: 12px; }
QLabel#counter { color: #597566; font-size: 12px; }
QPushButton { background: #f5f7f1; border: 1px solid #d1dbcf; border-radius: 7px; padding: 8px 13px; font-weight: 600; }
QPushButton:hover { background: #e9f1e8; border-color: #91ae9b; }
QPushButton:pressed { background: #dce9dd; }
QPushButton:disabled { color: #a3ada5; background: #eef1eb; border-color: #e0e5dc; }
QPushButton#primary { background: #087d72; color: white; border-color: #087d72; }
QPushButton#primary:hover { background: #076a61; }
QPushButton#primary:disabled { background: #8db9ad; border-color: #8db9ad; }
QPushButton#quiet { background: transparent; border: none; color: #087d72; padding: 5px; }
QLineEdit, QComboBox, QSpinBox { background: #ffffff; border: 1px solid #d0dbd1; border-radius: 6px; padding: 7px; selection-background-color: #b8dcd1; }
QComboBox QAbstractItemView { background: white; selection-background-color: #dcefe5; color: #203b3a; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #087d72; }
QPlainTextEdit { background: #f3f6f1; border: 1px solid #dbe3d8; border-radius: 7px; padding: 8px; font-family: "Consolas", "DejaVu Sans Mono", monospace; font-size: 11px; selection-background-color: #b9ddd2; }
QTextBrowser { background: transparent; border: none; padding: 0; }
QTabWidget::pane { border: none; }
QTabBar::tab { padding: 8px 10px; background: transparent; color: #7a887d; border-bottom: 2px solid #dce4db; }
QTabBar::tab:selected { color: #087d72; border-bottom: 2px solid #087d72; font-weight: 700; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 9px 10px; border-radius: 6px; margin: 2px 0; }
QListWidget::item:selected { background: #dfefe4; color: #076d62; }
QListWidget::item:hover { background: #edf3e9; }
QSplitter::handle { background: #dce4db; width: 1px; }
QStatusBar { background: #edf2e9; color: #647967; border-top: 1px solid #dce4db; font-size: 11px; }
QProgressBar { border: none; background: #deeadf; max-height: 3px; }
QProgressBar::chunk { background: #087d72; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #cbd8ca; min-height: 30px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QToolTip { background: #203b3a; color: white; padding: 7px; border: none; }
'''

NOTES_STYLE = '''body { color:#334d42; font-family:Segoe UI,DejaVu Sans,sans-serif; font-size:13px; }
h2 { font-size:20px; font-weight:600; margin-top:8px; margin-bottom:12px; color:#203b3a; }
h3 { font-size:12px; color:#087d72; margin-top:20px; margin-bottom:4px; }
p { line-height:1.5; margin-top:7px; margin-bottom:12px; }
code { font-family:Consolas,monospace; color:#087d72; }
th { color:#657b69; font-size:11px; }
td { font-size:12px; }
'''
