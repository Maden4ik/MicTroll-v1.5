# Импортируем необходимые модули
import sys
import pyaudio
import numpy as np
import random
import json
import wave
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QSlider, QLabel, QPushButton, QLineEdit, 
                             QComboBox, QFileDialog, QCheckBox, QMessageBox)
from PyQt5.QtCore import Qt, QThread, QUrl
from PyQt5.QtGui import QDesktopServices, QIcon, QPixmap

# Константы для аудио
CHUNK = 1024
FORMAT = pyaudio.paFloat32
CHANNELS = 1
RATE = 44100


class AudioThread(QThread):
    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.params = params
        self.running = True
        self.background_audio = None
        self.background_playing = False

    def run(self):
        p = pyaudio.PyAudio()

        virtual_cable_index = self.find_virtual_cable(p)
        if virtual_cable_index is None:
            self.error_message()
            return
        
        self.setup_streams(p, virtual_cable_index)

        while self.running:
            data = self.stream_in.read(CHUNK, exception_on_overflow=False)
            audio_data = self.process_audio(data)
            self.stream_out.write(audio_data.astype(np.float32).tobytes())

        self.cleanup(p)

    def setup_streams(self, p, virtual_cable_index):
        self.stream_in = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        self.stream_out = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, output_device_index=virtual_cable_index, frames_per_buffer=CHUNK)

    def find_virtual_cable(self, p):
        for i in range(p.get_device_count()):
            dev_info = p.get_device_info_by_index(i)
            if "CABLE Input" in dev_info["name"]:
                return i
        return None
    
    def error_message(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Ошибка: Виртуальный кабель не установлен")
        msg.setInformativeText("Пожалуйста, установите Virtual Audio Cable и перезагрузите ПК.")
        msg.setWindowTitle("Ошибка")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.buttonClicked.connect(self.open_install_page)
        msg.exec_()

    def open_install_page(self, button):
        if button.text() == "Перейти на сайт установки":
            QDesktopServices.openUrl(QUrl("https://vb-audio.com/Cable/"))

    def process_audio(self, data):
        audio_data = np.frombuffer(data, dtype=np.float32).copy()

        if random.random() < self.params['break_chance']:
            audio_data.fill(0)
        elif random.random() < self.params['distort_chance']:
            audio_data = self.apply_distortion(audio_data)

        noise = self.generate_noise(self.params['noise_type'], CHUNK)
        audio_data += noise * self.params['noise_amount']
        audio_data = self.apply_effects(audio_data)

        return np.clip(audio_data, -1, 1)

    def generate_noise(self, noise_type, length):
        if noise_type == 'White':
            return np.random.uniform(-1, 1, length)
        elif noise_type == 'Square':
            return np.sign(np.sin(np.linspace(0, 2 * np.pi, length)))
        elif noise_type == 'Triangle':
            return 2 * np.abs(2 * (np.linspace(0, 1, length) - np.floor(0.5 + np.linspace(0, 1, length)))) - 1
        return np.zeros(length)

    def apply_distortion(self, audio):
        return np.clip(audio * (1 + self.params['distort_amount']), -1, 1)

    def apply_effects(self, audio_data):
        audio_data = self.apply_bit_crush(audio_data, self.params['bit_crush'])
        audio_data = self.apply_bass_boost(audio_data, self.params['bass_boost'])
        return audio_data

    def apply_bit_crush(self, audio, bits):
        if bits < 16:
            steps = 2 ** bits
            return np.round(audio * steps) / steps
        return audio

    def apply_bass_boost(self, audio, boost):
        if boost > 0:
            return np.clip(audio * (1 + boost * 10), -1, 1)
        return audio

    def cleanup(self, p):
        self.stream_in.stop_stream()
        self.stream_in.close()
        self.stream_out.stop_stream()
        self.stream_out.close()
        p.terminate()


class ControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.params = self.default_params()
        self.audio_thread = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('MicTroll v1.5 - By Maden4ik')
        self.setWindowIcon(QIcon('icon.png'))
        self.setStyleSheet(self.load_style_sheet())
        self.resize(500, 400)

        main_layout = QVBoxLayout()

        # Шапка приложения
        header_layout = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap("logo.png").scaled(40, 40, Qt.KeepAspectRatio))
        header_layout.addWidget(logo, alignment=Qt.AlignLeft)
        header_layout.addStretch()
        self.telegram_btn = QPushButton('Telegram канал')
        self.telegram_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/Maden4ikArts")))
        header_layout.addWidget(QLabel('Разработчик: Maden4ik'), alignment=Qt.AlignRight)
        self.github_btn = QPushButton('Github')
        self.github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/Maden4ik")))
        main_layout.addWidget(self.telegram_btn)
        main_layout.addWidget(self.github_btn)
        main_layout.addLayout(header_layout)

        # Основные настройки
        settings_layout = QVBoxLayout()
        
        # Эффекты
        effects_label = QLabel('Эффекты')
        effects_label.setAlignment(Qt.AlignCenter)
        settings_layout.addWidget(effects_label)

        self.break_slider = self.create_slider('Шанс прерывания', 0, 100, 10)
        self.distort_slider = self.create_slider('Шанс искажения', 0, 100, 20)
        self.amount_slider = self.create_slider('Степень искажения', 0, 100, 50)
        settings_layout.addWidget(self.break_slider)
        settings_layout.addWidget(self.distort_slider)
        settings_layout.addWidget(self.amount_slider)

        # Шум и качество
        noise_label = QLabel('Настройки шума')
        noise_label.setAlignment(Qt.AlignCenter)
        settings_layout.addWidget(noise_label)

        self.noise_combo = QComboBox()
        self.noise_combo.addItems(['None', 'White', 'Square', 'Triangle'])
        self.noise_amount_slider = self.create_slider('Количество шума', 0, 100, 10)
        self.bit_crush_slider = self.create_slider('Bit Crush', 1, 16, 16)
        self.bass_boost_slider = self.create_slider('Bass Boost', 0, 100, 0)
        
        settings_layout.addWidget(QLabel('Тип шума:'))
        settings_layout.addWidget(self.noise_combo)
        settings_layout.addWidget(self.noise_amount_slider)
        settings_layout.addWidget(self.bit_crush_slider)
        settings_layout.addWidget(self.bass_boost_slider)

        # Основные кнопки
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton('Старт')
        self.stop_btn = QPushButton('Стоп')
        self.start_btn.clicked.connect(self.start_audio)
        self.stop_btn.clicked.connect(self.stop_audio)
        
        control_layout.addStretch()
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addStretch()
        
        main_layout.addLayout(settings_layout)
        main_layout.addLayout(control_layout)
        self.setLayout(main_layout)
        self.show()

    def default_params(self):
        return {
            'break_chance': 0,
            'distort_chance': 0,
            'distort_amount': 0,
            'noise_type': 'None',
            'noise_amount': 0,
            'bit_crush': 0,
            'bass_boost': 0
        }

    def load_style_sheet(self):
        return """
        QWidget {
            background-color: #1E1E2E;  /* Глубокий темно-синий фон */
            color: #D0D0E0;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QPushButton {
            background-color: #4A4A6A; 
            color: #E0E0F0;
            border: none;
            border-radius: 4px;
            padding: 8px 15px;
            font-weight: 500;
            transition: background-color 0.3s;
        }
        QPushButton:hover {
            background-color: #5A5A7A;
        }
        QPushButton:pressed {
            background-color: #3A3A5A;
        }
        QSlider::groove:horizontal {
            background: #3A3A4A;
            height: 6px;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #7A6ABA;
            border: none;
            width: 14px;
            height: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }
        QLineEdit, QComboBox {
            background-color: #2A2A3A;
            color: #D0D0E0;
            border: 1px solid #3A3A4A;
            border-radius: 4px;
            padding: 6px;
        }
        QLabel {
            color: #A0A0C0;
        }
        """

    def create_slider(self, name, min_val, max_val, default):
        layout = QVBoxLayout()
        label = QLabel(name)
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        slider.valueChanged.connect(self.update_params)
        layout.addWidget(label)
        layout.addWidget(slider)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def update_params(self):
        self.params['break_chance'] = self.break_slider.findChild(QSlider).value() / 100
        self.params['distort_chance'] = self.distort_slider.findChild(QSlider).value() / 100
        self.params['distort_amount'] = self.amount_slider.findChild(QSlider).value() / 100
        self.params['noise_type'] = self.noise_combo.currentText()
        self.params['noise_amount'] = self.noise_amount_slider.findChild(QSlider).value() / 100
        self.params['bit_crush'] = self.bit_crush_slider.findChild(QSlider).value()
        self.params['bass_boost'] = self.bass_boost_slider.findChild(QSlider).value() / 100
        if self.audio_thread:
            self.audio_thread.params = self.params

    def start_audio(self):
        if not self.audio_thread:
            self.audio_thread = AudioThread(self.params, self)
            self.audio_thread.start()

    def stop_audio(self):
        if self.audio_thread:
            self.audio_thread.running = False
            self.audio_thread.wait()
            self.audio_thread = None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ControlPanel()
    sys.exit(app.exec_())