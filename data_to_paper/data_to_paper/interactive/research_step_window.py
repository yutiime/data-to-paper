from functools import partial
from typing import Optional, List, Collection, Dict, Callable

from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QLabel, QPushButton, QWidget, \
    QHBoxLayout, QSplitter, QTextEdit
from PySide6.QtCore import Qt, QEventLoop, QMutex, QWaitCondition, QThread, Signal, Slot

from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers.python import PythonLexer

from data_to_paper.interactive.base_app import BaseApp
from data_to_paper.interactive.types import PanelNames


class Worker(QThread):
    # Signal now carries a string payload for initial text
    request_input_signal = Signal(PanelNames, str, str, dict)
    show_text_signal = Signal(PanelNames, str)

    def __init__(self, mutex, condition, func_to_run=None):
        super().__init__()
        self.mutex = mutex
        self.condition = condition
        self.func_to_run = func_to_run
        self._text_input = None
        self._panel_name_input = None

    def run(self):
        if self.func_to_run is not None:
            self.func_to_run()

    def edit_text_in_panel(self, panel_name: PanelNames, initial_text: str = '',
                     title: Optional[str] = None, optional_suggestions: Dict[str, str] = None) -> str:
        self.mutex.lock()
        self.request_input_signal.emit(panel_name, initial_text, title, optional_suggestions)
        self.condition.wait(self.mutex)
        input_text = self._text_input
        self.mutex.unlock()
        return input_text

    def show_text_in_panel(self, panel_name: PanelNames, text: str):
        self.show_text_signal.emit(panel_name, text)

    @Slot(PanelNames, str)
    def set_text_input(self, panel_name, text):
        self.mutex.lock()
        self._text_input = text
        self._panel_name_input = panel_name
        self.condition.wakeAll()
        self.mutex.unlock()


class Panel(QWidget):
    def __init__(self, heading: Optional[str] = None):
        """
        A panel that displays text and allows editing.
        """
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.heading = heading
        self.heading_label = QLabel()
        self.layout.addWidget(self.heading_label)
        self.heading_label.setText(self.heading)

    def reset_heading(self):
        if self.heading is not None:
            self.heading_label.setText(self.heading)

    def set_text(self, text):
        pass

    def get_text(self):
        pass


class EditableTextPanel(Panel):
    def __init__(self, heading: Optional[str] = None,
                 suggestion_button_names: Optional[Collection[str]] = None):
        super().__init__(heading)
        if suggestion_button_names is None:
            suggestion_button_names = []
        self.suggestion_button_names = suggestion_button_names
        self.suggestion_buttons = []
        self.suggestion_texts = [''] * len(suggestion_button_names)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.layout.addWidget(self.text_edit)

        self.buttons_tray = QHBoxLayout()
        self.layout.addLayout(self.buttons_tray)

        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.on_submit)
        self.buttons_tray.addWidget(self.submit_button)

        for i, button_text in enumerate(suggestion_button_names):
            button = QPushButton(button_text)
            button.clicked.connect(self.on_suggestion_button_click)
            self.buttons_tray.addWidget(button)
            self.suggestion_buttons.append(button)
        self._set_buttons_visibility(False)

        self.loop = None
    
    def _set_buttons_visibility(self, visible: bool):
        self.submit_button.setVisible(visible)
        for button in self.suggestion_buttons:
            button.setVisible(visible)

    def on_suggestion_button_click(self):
        button = self.sender()
        suggestion_index = self.suggestion_buttons.index(button)
        if suggestion_index < len(self.suggestion_texts):
            self.text_edit.setPlainText(self.suggestion_texts[suggestion_index])

    def set_text(self, text):
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(text)
        self._set_buttons_visibility(False)

    def edit_text(self, text: Optional[str] = '', title: Optional[str] = None,
                  suggestion_texts: Optional[List[str]] = None):
        self.text_edit.setReadOnly(False)
        self.text_edit.setPlainText(text)
        self._set_buttons_visibility(True)
        if suggestion_texts is not None:
            self.suggestion_texts = suggestion_texts
        if title is not None:
            if self.heading is not None:
                heading = self.heading + ' - ' + title
            else:
                heading = title
            self.heading_label.setText(heading)
        self.loop = QEventLoop()
        self.loop.exec()

    def on_submit(self):
        self.text_edit.setReadOnly(True)
        self._set_buttons_visibility(False)
        self.reset_heading()
        if self.loop is not None:
            self.loop.exit()

    def get_text(self):
        return self.text_edit.toPlainText()


class HtmlPanel(Panel):
    def __init__(self, heading: Optional[str] = None):
        super().__init__(heading)
        self.text_browser = QTextEdit()
        self.text_browser.setReadOnly(True)
        self.layout.addWidget(self.text_browser)

    def set_text(self, text):
        self.text_browser.setHtml(text)

    def get_text(self):
        return self.text_browser.toPlainText()


class ResearchStepApp(QMainWindow, BaseApp):
    send_text_signal = Signal(str, PanelNames)

    def __init__(self, mutex, condition):
        super().__init__()
        self.panels = {
            PanelNames.SYSTEM_PROMPT: EditableTextPanel("System Prompt", ("Default", )),
            PanelNames.MISSION_PROMPT: EditableTextPanel("Mission Prompt", ("Default", )),
            PanelNames.PRODUCT: HtmlPanel("Product"),
            PanelNames.FEEDBACK: EditableTextPanel("Feedback", ("AI Review", "No comments")),
        }

        main_splitter = QSplitter(Qt.Horizontal)
        left_splitter = QSplitter(Qt.Vertical)
        right_splitter = QSplitter(Qt.Vertical)

        left_splitter.addWidget(self.panels[PanelNames.SYSTEM_PROMPT])
        left_splitter.addWidget(self.panels[PanelNames.MISSION_PROMPT])
        right_splitter.addWidget(self.panels[PanelNames.PRODUCT])
        right_splitter.addWidget(self.panels[PanelNames.FEEDBACK])

        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_splitter)

        self.setCentralWidget(main_splitter)

        # Worker thread setup
        self.worker = Worker(mutex, condition)
        # Slot now accepts a string argument for the initial text
        self.worker.request_input_signal.connect(self.edit_text_in_panel)
        self.worker.show_text_signal.connect(self.show_text_in_panel)

        # Define the request_text and show_text methods
        self.request_text = self.worker.edit_text_in_panel
        self.show_text = self.worker.show_text_in_panel

        # Connect UI elements
        for panel_name in PanelNames:
            if panel_name == PanelNames.PRODUCT:
                continue
            self.panels[panel_name].submit_button.clicked.connect(partial(self.submit_text, panel_name=panel_name))

        # Connect the MainWindow signal to the worker's slot
        self.send_text_signal.connect(self.worker.set_text_input)

    @classmethod
    def get_instance(cls):
        if cls.instance is None:
            mutex = QMutex()
            condition = QWaitCondition()
            cls.instance = cls(mutex, condition)
        return cls.instance

    def start_worker(self, func_to_run: Callable = None):
        # Start the worker thread
        self.worker.func_to_run = func_to_run
        self.worker.start()

    def initialize(self):
        self.show()

    def set_window_title(self, title):
        self.setWindowTitle(title)

    @Slot(PanelNames, str, str, dict)
    def edit_text_in_panel(self, panel_name: PanelNames, initial_text: str = '',
                     title: Optional[str] = None, optional_suggestions: Dict[str, str] = None) -> str:
        panel = self.panels[panel_name]
        if optional_suggestions is None:
            optional_suggestions = {}
        panel.edit_text(initial_text, title, list(optional_suggestions.values()))

    @Slot(PanelNames)
    def submit_text(self, panel_name: PanelNames):
        panel = self.panels[panel_name]
        text = panel.get_text()
        self.send_text_signal.emit(panel_name, text)

    @Slot(PanelNames, str)
    def show_text_in_panel(self, panel_name: PanelNames, text: str):
        panel = self.panels[panel_name]
        panel.set_text(text)


def get_highlighted_code(sample_code: str, style: str = "monokai") -> str:
    """
    Highlight the provided Python code with the specified style and return the HTML code.
    """
    formatter = HtmlFormatter(style=style)
    css = formatter.get_style_defs('.highlight')
    additional_css = ".highlight, .highlight pre { background: #272822; }  /* Use the monokai background color */"
    highlighted_code = highlight(sample_code, PythonLexer(), formatter)
    return f"<style>{css}{additional_css}</style>{highlighted_code}"
