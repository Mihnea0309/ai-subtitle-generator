import sys
import whisper
import math
import os
import vlc
import torch
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QFrame,
                             QStackedWidget, QMainWindow, QSizePolicy, QComboBox, QToolBar, QAction, QMenu,
                             QMessageBox, QSlider, QHBoxLayout)
from PyQt5.QtCore import QTimer, Qt
from deep_translator import GoogleTranslator
from langdetect import detect


class SubtitlingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generare Subtitrări")
        self.setGeometry(750, 400, 800, 500)

        self.model_type = "base"
        self.device_type = "cuda"

        self.toolbar = QToolBar("Toolbar")
        self.toolbar.setStyleSheet("QToolBar { background-color: white; } "
                                   "QToolButton { color: black; background-color: white; border: 1px solid lightgray; padding: 5px; } "
                                   "QToolButton:hover { background-color: #f0f0f0; }")
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        preferences_action = QAction("Preferinte", self)
        preferences_action.triggered.connect(self.show_preferences_menu)
        self.toolbar.addAction(preferences_action)
        help_action = QAction("Indrumari", self)
        help_action.triggered.connect(self.show_help_dialog)
        self.toolbar.addAction(help_action)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.instance = vlc.Instance('--no-xlib')
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
        file_path, _ = QFileDialog.getOpenFileName(self, "Alege fișier video", "",
                                                   "Video Files (*.mp4 *.avi *.mkv *.mov)")
        if file_path:
            self.label.setText(f"Fișier selectat: {file_path}")
            self.video_file = file_path
            self.process_video(file_path)

    def process_video(self, file_path):
        try:
            model = whisper.load_model(self.model_type).to(self.device_type)
            result = model.transcribe(file_path)
            name = os.path.splitext(os.path.basename(file_path))[0]
            srt_filename = f"{name}.srt"
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
        if result["segments"] and len(result["segments"]) > 0:
            sample_text = " ".join(
                [segment["text"] for segment in result["segments"][:min(5, len(result["segments"]))]])
            try:
                source_lang = detect(sample_text)
                print(f"Limba detectată a videoclipului: {source_lang}")
            except Exception as e:
                print(f"Eroare la detectarea limbii: {e}")
                source_lang = None

        same_language = source_lang == target_lang
        if same_language:
            print(
                f"Limba sursei ({source_lang}) este aceeași cu limba țintă ({target_lang}). Nu se va aplica traducerea.")

        def format_time(seconds):
            hours = math.floor(seconds // 3600)
            minutes = math.floor((seconds % 3600) // 60)
            seconds_int = math.floor(seconds % 60)
            milliseconds = math.floor((seconds - int(seconds)) * 1000)
            return f"{hours:02}:{minutes:02}:{seconds_int:02},{milliseconds:03}"

        translator = None
        if not same_language:
            translator = GoogleTranslator(source='auto', target=target_lang)

        srt_content = ""

        for i, segment in enumerate(result["segments"]):
            start_time = segment["start"]
            end_time = segment["end"]
            subtitle_text = segment["text"]

            if not same_language and translator:
                try:
                    translated_text = translator.translate(subtitle_text)
                except Exception as e:
                    print(f"Eroare la traducere: {e}")
                    translated_text = subtitle_text
            else:
                translated_text = subtitle_text

            srt_content += f"{i + 1}\n{format_time(start_time)} --> {format_time(end_time)}\n{translated_text}\n\n"

        with open(filename, "w", encoding="utf-8") as file:
            file.write(srt_content)

    def show_video_page(self):
        self.stack.setCurrentWidget(self.video_page)
        self.play_video()

    def play_video(self):
        if not self.video_file:
            return

        self.slider.setValue(0)
        self.time_label.setText("00:00:00 / 00:00:00")

        media = self.instance.media_new(self.video_file)

        if self.subtitle_file and os.path.exists(self.subtitle_file):
            media.add_option(f":sub-file={self.subtitle_file}")
            print(f"Subtitrare încărcată: {self.subtitle_file}")
        else:
            print("Subtitrare indisponibilă.")

        self.media_player.set_media(media)

        self.show()
        QApplication.processEvents()

        if sys.platform.startswith('linux'):
            self.media_player.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":
            self.media_player.set_hwnd(self.video_frame.winId())
        elif sys.platform == "darwin":
            self.media_player.set_nsobject(int(self.video_frame.winId()))

        self.timer.start()

        if self.media_player.play() == -1:
            print("Eroare la redare")
            self.timer.stop()
            QMessageBox.warning(self, "Eroare", "Nu s-a putut reda videoclipul.")
        else:
            print("Redarea a început cu succes")
            self.play_pause_button.setText("Pauză")

    def format_time_video(self, ms):
        if ms <= 0:
            return "00:00:00"

        seconds = int(ms / 1000)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def update_slider(self):
        if not self.media_player or not hasattr(self, 'slider') or not self.slider:
            return

        is_playing = self.media_player.is_playing()

        try:
            length = self.media_player.get_length()

            if length <= 0:
                return

            if not self.user_is_seeking:
                current_time = self.media_player.get_time()

                position = int(1000 * current_time / length) if length > 0 else 0

                if 0 <= position <= 1000:
                    self.slider.blockSignals(True)
                    self.slider.setValue(position)
                    self.slider.blockSignals(False)

                if hasattr(self, 'time_label') and self.time_label:
                    current_formatted = self.format_time_video(current_time)
                    total_formatted = self.format_time_video(length)
                    self.time_label.setText(f"{current_formatted} / {total_formatted}")

        except Exception as e:
            print(f"Eroare la actualizarea UI: {str(e)}")

    def show_select_page(self):
        if self.media_player:
            if self.media_player.is_playing():
                self.media_player.stop()

        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()

        self.stack.setCurrentWidget(self.select_page)

    def toggle_play_pause(self):
        if not self.media_player:
            return

        if self.media_player.is_playing():
            self.media_player.pause()
            self.play_pause_button.setText("Play")
        else:
            self.media_player.play()
            self.play_pause_button.setText("Pauză")

    def stop_video(self):
        if not self.media_player:
            return

        self.media_player.stop()
        self.play_pause_button.setText("Play")

        if hasattr(self, 'slider') and self.slider:
            self.slider.setValue(0)

        if hasattr(self, 'time_label') and self.time_label:
            self.time_label.setText("00:00:00 / 00:00:00")

    def slider_pressed(self):
        self.user_is_seeking = True

        self.was_playing = self.media_player and self.media_player.is_playing()

        if self.was_playing:
            self.media_player.pause()

    def slider_moved(self):
        try:
            if not self.media_player:
                return

            pos = self.slider.value()

            length = self.media_player.get_length()

            if length > 0:
                new_time = int(pos / 1000.0 * length)

                if hasattr(self, 'time_label') and self.time_label:
                    current_formatted = self.format_time_video(new_time)
                    total_formatted = self.format_time_video(length)
                    self.time_label.setText(f"{current_formatted} / {total_formatted}")

        except Exception as e:
            print(f"Eroare la slider moved: {str(e)}")

    def slider_released(self):
        try:
            if not self.media_player:
                return

            pos = self.slider.value()

            length = self.media_player.get_length()

            if length > 0:
                new_time = int(pos / 1000.0 * length)

                self.media_player.set_time(new_time)

                if hasattr(self, 'time_label') and self.time_label:
                    current_formatted = self.format_time_video(new_time)
                    total_formatted = self.format_time_video(length)
                    self.time_label.setText(f"{current_formatted} / {total_formatted}")

            if self.was_playing:
                self.media_player.play()
                self.play_pause_button.setText("Pauză")

        except Exception as e:
            print(f"Eroare la slider release: {str(e)}")
        finally:
            self.user_is_seeking = False

    def show_preferences_menu(self):
        menu = QMenu(self)
        model_menu = QMenu("Model Whisper", self)
        models = ["base", "base.en", "small", "small.en", "medium", "medium.en", "large"]
        for model in models:
            action = QAction(model, self)
            action.setCheckable(True)
            action.setChecked(self.model_type == model)
            action.triggered.connect(lambda checked, m=model: self.set_model_type(m))
            model_menu.addAction(action)
        menu.addMenu(model_menu)

        device_menu = QMenu("Device", self)
        for device in ["cuda", "cpu"]:
            action = QAction(device.upper(), self)
            action.setCheckable(True)
            action.setChecked(self.device_type == device)
            action.triggered.connect(lambda checked, d=device: self.set_device_type(d))
            device_menu.addAction(action)
        menu.addMenu(device_menu)

        style = """
            QMenu {
                background-color: white;
                color: black;
                border: 1px solid lightgray;
            }
            QMenu::item {
                padding: 6px 25px;
            }
            QMenu::item:selected {
                background-color: #e0e0e0;
                color: black;
            }
        """
        menu.setStyleSheet(style)
        model_menu.setStyleSheet(style)
        device_menu.setStyleSheet(style)

        menu.exec_(self.mapToGlobal(self.toolbar.geometry().bottomLeft()))

    def set_model_type(self, model_name):
        try:
            self.model_type = model_name
            if self.media_player and self.media_player.is_playing():
                self.media_player.stop()
                if hasattr(self, 'timer') and self.timer.isActive():
                    self.timer.stop()
        except Exception as e:
            print(f"Eroare la schimbarea modelului: {e}")

    def set_device_type(self, device):
        try:
            if device == "cuda" and not torch.cuda.is_available():
                print("CUDA nu este disponibil. Se revine la CPU.")
                self.device_type = "cpu"
                QMessageBox.warning(self, "Avertisment", "CUDA nu este disponibil. Se va folosi CPU.")
            else:
                self.device_type = device

            if self.media_player and self.media_player.is_playing():
                self.media_player.stop()
                if hasattr(self, 'timer') and self.timer.isActive():
                    self.timer.stop()
        except Exception as e:
            print(f"Eroare la schimbarea dispozitivului: {e}")

    def show_help_dialog(self):
        help_text = (
            "Această aplicație generează automat subtitrări pentru fișiere video folosind modelul Whisper.\n\n"
            "1. Selectează un fișier video.\n"
            "2. Alege limba în care vrei să fie traduse subtitrările.\n"
            "3. Apasă 'Redă video' pentru a viziona videoclipul cu subtitrări.\n"
            "4. Folosește slider-ul pentru a naviga în videoclip.\n"
            "5. Poți schimba modelul sau dispozitivul de procesare (CPU/GPU) din meniul de preferințe.\n\n"
            "Sfaturi:\n"
            "- dacă calculatorul nu are GPU, aplicația trebuie să ruleze pe CPU\n"
            "- pentru o performanță mai bună, să se aleagă GPU\n"
            "- modelul base are o acuratețe slabă, dar viteza de procesare este rapidă\n"
            "- modelul medium are o acuratețe mai bună, dar viteza de procesare mai lentă\n"
            "- modelele care contin .en la final sunt mai performante pe videoclipurile in engleza\n\n"
            "Subtitrările generate vor fi salvate automat în format .srt.\n\n"
            "Notă: Aplicația va detecta automat limba sursei și nu va traduce textul dacă limba selectată "
            "este aceeași cu cea detectată în video."
        )
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Ajutor - Cum funcționează")
        msg.setText(help_text)
        msg.setStyleSheet("""
            QMessageBox { background-color: white; }
            QLabel { color: black; font-family: Arial; font-size: 13pt; }
            QPushButton { background-color: lightgray; color: black; font-weight: bold; }
        """)
        msg.exec_()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    color = QPalette()
    color.setColor(QPalette.Window, QColor(30, 30, 30))
    color.setColor(QPalette.WindowText, QColor(255, 255, 255))
    color.setColor(QPalette.Button, QColor(50, 50, 50))
    color.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    app.setPalette(color)

    app.setStyleSheet("""
        QSlider::groove:horizontal {
            border: 1px solid #999999;
            height: 8px;
            background: #4A4A4A;
            margin: 2px 0;
            border-radius: 4px;
        }

        QSlider::handle:horizontal {
            background: #CCCCCC;
            border: 1px solid #5c5c5c;
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }

        QSlider::handle:horizontal:hover {
            background: white;
        }

        QPushButton {
            background-color: #505050;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
        }

        QPushButton:hover {
            background-color: #606060;
        }

        QPushButton:pressed {
            background-color: #404040;
        }

        QPushButton:disabled {
            background-color: #303030;
            color: #808080;
        }
    """)

    window = SubtitlingApp()
    window.show()
    sys.exit(app.exec_())
