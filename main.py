import sys
import math
import os
import vlc
import torch
import whisper
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QFrame,
    QStackedWidget, QMainWindow, QSizePolicy, QComboBox, QToolBar, QAction, QMenu,
    QMessageBox, QSlider, QHBoxLayout
)
from PyQt5.QtCore import QTimer, Qt
from deep_translator import GoogleTranslator
from langdetect import detect


class SubtitlingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generare Subtitrări")
        self.setGeometry(750, 400, 800, 500)

        self.model_type = "base"
        self.device_type = "cuda" if torch.cuda.is_available() else "cpu"

        self.toolbar = QToolBar("Toolbar")
        self.toolbar.setStyleSheet(
            "QToolBar { background-color: white; } "
            "QToolButton { color: black; background-color: white; border: 1px solid lightgray; padding: 5px; } "
            "QToolButton:hover { background-color: #f0f0f0; }"
        )
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        preferences_action = QAction("Preferinte", self)
        preferences_action.triggered.connect(self.show_preferences_menu)
        self.toolbar.addAction(preferences_action)

        help_action = QAction("Indrumari", self)
        help_action.triggered.connect(self.show_help_dialog)
        self.toolbar.addAction(help_action)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        vlc_args = ['--no-xlib'] if sys.platform.startswith('linux') else []
        self.instance = vlc.Instance(*vlc_args)
        self.media_player = self.instance.media_player_new()

        self.video_file = None
        self.subtitle_file = None
        self.user_is_seeking = False
        self.was_playing = False

        self.init_select_page()
        self.init_video_page()

        self.stack.setCurrentWidget(self.select_page)

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_slider)

    def init_select_page(self):
        self.select_page = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.label = QLabel("Apasă pe butonul de mai jos pentru a selecta un fișier video.")
        self.label.setStyleSheet("font-size: 16px;")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.select_button = QPushButton("Selectează fișier video")
        self.select_button.setStyleSheet("font-size: 16px;")
        self.select_button.clicked.connect(self.select_file)
        layout.addWidget(self.select_button)

        self.language_selector = QComboBox()
        self.language_selector.setStyleSheet("font-size: 14px;")
        self.languages = {
            "Engleză": "en",
            "Română": "ro",
            "Franceză": "fr",
            "Spaniolă": "es",
            "Germană": "de",
            "Italiană": "it"
        }
        self.iso_to_name = {v: k for k, v in self.languages.items()}

        self.language_selector.addItems(self.languages.keys())
        layout.addWidget(QLabel("Selectează limba pentru subtitrare:"))
        layout.addWidget(self.language_selector)

        self.play_button = QPushButton("Redă video")
        self.play_button.setStyleSheet("font-size: 16px;")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.show_video_page)
        layout.addWidget(self.play_button)

        self.select_page.setLayout(layout)
        self.stack.addWidget(self.select_page)

    def init_video_page(self):
        self.video_page = QWidget()
        main_layout = QVBoxLayout(self.video_page)

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(10, 10, 10, 0)

        self.back_button = QPushButton("Back")
        self.back_button.setStyleSheet("font-size: 16px; padding: 5px;")
        self.back_button.setMaximumWidth(80)
        self.back_button.clicked.connect(self.show_select_page)
        top_layout.addWidget(self.back_button, alignment=Qt.AlignLeft)

        main_layout.addWidget(top_widget)

        self.video_frame = QFrame(self.video_page)
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_frame.setMinimumHeight(400)
        main_layout.addWidget(self.video_frame)

        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(10, 10, 10, 10)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(0)
        controls_layout.addWidget(self.slider)

        self.slider.sliderPressed.connect(self.slider_pressed)
        self.slider.sliderReleased.connect(self.slider_released)
        self.slider.sliderMoved.connect(self.slider_moved)

        time_layout = QHBoxLayout()
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setStyleSheet("color: white; font-size: 12px;")
        self.time_label.setAlignment(Qt.AlignCenter)
        time_layout.addWidget(self.time_label)
        controls_layout.addLayout(time_layout)

        main_layout.addWidget(controls_widget)

        playback_controls = QWidget()
        playback_layout = QHBoxLayout(playback_controls)
        playback_layout.setContentsMargins(10, 0, 10, 10)

        self.play_pause_button = QPushButton("Pauză")
        self.play_pause_button.setStyleSheet("font-size: 14px; padding: 5px 15px;")
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        playback_layout.addWidget(self.play_pause_button, alignment=Qt.AlignCenter)

        main_layout.addWidget(playback_controls)

        self.video_page.setLayout(main_layout)
        self.stack.addWidget(self.video_page)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Alege fișier video", "", "Video Files (*.mp4 *.avi *.mkv *.mov)"
        )
        if file_path:
            self.label.setText(f"Fișier selectat: {os.path.basename(file_path)}")
            self.video_file = file_path
            self.process_video(file_path)

    def process_video(self, file_path):
        try:
            model = whisper.load_model(self.model_type).to(self.device_type)
            result = model.transcribe(file_path)
            name = os.path.splitext(os.path.basename(file_path))[0]
            srt_filename = os.path.abspath(f"{name}.srt")
            self.save_subtitles(result, srt_filename)
            self.subtitle_file = srt_filename
            self.play_button.setEnabled(True)
        except Exception as e:
            print(f"Eroare: {e}")
            QMessageBox.warning(self, "Eroare", f"Nu s-a putut procesa videoclipul: {e}")

    def save_subtitles(self, result, filename):
        selected_lang_name = self.language_selector.currentText()
        target_lang = self.languages[selected_lang_name]

        source_lang = None
        if result["segments"]:
            sample_text = " ".join(
                segment["text"] for segment in result["segments"][:min(5, len(result["segments"]))]
            )
            try:
                source_lang = detect(sample_text)
                print(f"Limba detectată a videoclipului: {source_lang}")
            except Exception as e:
                print(f"Eroare la detectarea limbii: {e}")

        same_language = source_lang == target_lang
        if same_language:
            print(f"Limba sursei ({source_lang}) este aceeași cu limba țintă ({target_lang}). Nu se va aplica traducerea.")

        def format_time(seconds):
            hours = math.floor(seconds // 3600)
            minutes = math.floor((seconds % 3600) // 60)
            seconds_int = math.floor(seconds % 60)
            milliseconds = math.floor((seconds - int(seconds)) * 1000)
            return f"{hours:02}:{minutes:02}:{seconds_int:02},{milliseconds:03}"

        translator = Google
