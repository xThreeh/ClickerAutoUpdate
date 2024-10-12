import sys
import json
import pyautogui
from pynput import keyboard
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings, QPropertyAnimation, QRect, QEasingCurve, QDate, QPoint, QSize, QObject, QRectF
from PyQt6.QtGui import QCursor, QKeySequence, QColor, QIcon, QPainter, QBrush, QPainterPath, QFont, QPen
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, 
                             QWidget, QMessageBox, QComboBox, QMenu, QSpinBox, QRadioButton, 
                             QLineEdit, QCheckBox, QMenuBar, QStyleFactory, QColorDialog, QGroupBox,
                             QScrollArea, QGridLayout)
import ctypes
import logging
import win32api  # Asegúrate de que esto esté presente
import win32con  # Asegúrate de que esto esté presente

pyautogui.FAILSAFE = False

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class GlobalHotKeys(QObject):
    f6_pressed = pyqtSignal()
    f11_pressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        logger.debug("GlobalHotKeys inicializado")

    def on_press(self, key):
        if key == keyboard.Key.f6:
            logger.debug("F6 presionado - Emitiendo señal")
            self.f6_pressed.emit()
        elif key == keyboard.Key.f11:
            logger.debug("F11 presionado - Emitiendo señal")
            self.f11_pressed.emit()

class ThemeSwitch(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 30)
        self._is_checked = False
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(300)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 15, 15)
        if self._is_checked:
            painter.fillPath(path, QColor(52, 199, 89))
        else:
            painter.fillPath(path, QColor(200, 200, 200))

        circle_rect = QRectF(2 if not self._is_checked else self.width() - 28, 2, 26, 26)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(circle_rect)

    def set_checked(self, checked):
        if self._is_checked != checked:
            self._is_checked = checked
            self.update()

    def is_checked(self):
        return self._is_checked

    def mousePressEvent(self, event):
        self.set_checked(not self._is_checked)
        super().mousePressEvent(event)

class OverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.parent_app = parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)  # Márgenes para el texto

        self.label = QLabel(
            "Haz clic en cualquier lugar para seleccionar\n"
            "Presiona ESC para cancelar\n\n"
            "F6: Iniciar/Detener clicker\n"
            "F11: Cerrar aplicación",
            self
        )
        self.label.setStyleSheet("""
            color: #FFFFFF; 
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 14px; 
            background-color: rgba(0, 0, 0, 150); 
            padding: 15px;
            border-radius: 5px;
        """)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(255, 0, 0, 50))  # Fondo rojo semitransparente

    def mousePressEvent(self, event):
        # Obtener las coordenadas globales del mouse usando mapToGlobal
        global_pos = self.mapToGlobal(event.pos())
        self.parent_app.on_overlay_click(global_pos)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

class AutoClickerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clicker AutoUpdate")
        self.setGeometry(100, 100, 600, 400)
        
        self.init_variables()
        self.init_ui()
        self.load_config()
        
        self.click_timer = QTimer(self)
        self.click_timer.timeout.connect(self.perform_click)
        
        self.cursor_update_timer = QTimer(self)
        self.cursor_update_timer.timeout.connect(self.update_current_cursor_position)
        self.cursor_update_timer.start(500)

        self.setup_hotkeys()
        self.apply_theme()
        self.init_menu()
        self.load_window_position()
        self.set_tooltips()

    def init_variables(self):
        self.settings = QSettings("NikoHuman Solution", "AutoClickerz")
        self.theme = self.settings.value("theme", "light")
        self.custom_color = self.settings.value("custom_color", "#FFFFFF")
        
        self.is_clicking = False
        self.click_count = 0
        self.total_clicks = int(self.settings.value("total_clicks", 0))
        self.session_clicks = 0
        self.today_clicks = int(self.settings.value("today_clicks", 0))
        
        self.last_click_date = QDate.fromString(self.settings.value("last_click_date", QDate.currentDate().toString(Qt.DateFormat.ISODate)), Qt.DateFormat.ISODate)
        
        if self.last_click_date != QDate.currentDate():
            self.today_clicks = 0
        
        # Inicializar interval_spinboxes aquí
        self.interval_spinboxes = [self.create_spinbox(label) for label in ["Horas:", "Minutos:", "Segundos:", "Milisegundos:"]]

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Control principal
        control_group = QGroupBox("Control principal")
        control_layout = QVBoxLayout()
        
        # Botón de Iniciar/Detener
        self.start_stop_button = QPushButton("Iniciar (F6)")
        self.start_stop_button.clicked.connect(self.toggle_clicking)
        control_layout.addWidget(self.start_stop_button)

        # Nuevo botón para elegir posición
        self.choose_position_button = QPushButton("Elegir posición")
        self.choose_position_button.setStyleSheet("background-color: red; color: white;")  # Estilo rojo
        self.choose_position_button.clicked.connect(self.choose_cursor_position)
        control_layout.addWidget(self.choose_position_button)

        cps_layout = QHBoxLayout()
        cps_layout.addWidget(QLabel("CPS:"))
        self.cps_spinbox = QSpinBox()
        self.cps_spinbox.setRange(1, 1000)
        self.cps_spinbox.setValue(int(self.settings.value("cps", 10)))
        self.cps_spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # Eliminar flechas
        self.cps_spinbox.valueChanged.connect(self.update_interval)
        cps_layout.addWidget(self.cps_spinbox)
        control_layout.addLayout(cps_layout)

        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        # Configuración de intervalo
        interval_group = QGroupBox("Configuración de intervalo")
        interval_layout = QHBoxLayout()
        
        for spinbox in self.interval_spinboxes:
            spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # Eliminar flechas
            interval_layout.addWidget(spinbox)  # Agregar cada spinbox individualmente
        interval_group.setLayout(interval_layout)
        main_layout.addWidget(interval_group)

        # Posición del cursor
        cursor_group = QGroupBox("Posición del cursor")
        cursor_layout = QVBoxLayout()
        
        # Cambiar a diseño horizontal
        cps_layout = QHBoxLayout()
        
        self.current_cursor_radio = QRadioButton("Posición Actual")
        self.chosen_cursor_radio = QRadioButton("Posición Seleccionada")
        
        # Aplicar estilo moderno
        for radio in [self.current_cursor_radio, self.chosen_cursor_radio]:
            radio.setStyleSheet("""
                QRadioButton {
                    font-size: 14px;
                    color: #333;
                    padding: 5px;
                }
                QRadioButton::indicator {
                    width: 20px;
                    height: 20px;
                }
                QRadioButton::indicator:checked {
                    background-color: #007ACC;
                    border: 2px solid #007ACC;
                }
                QRadioButton::indicator:unchecked {
                    background-color: #fff;
                    border: 2px solid #ccc;
                }
                QRadioButton:hover {
                    color: #007ACC;
                }
            """)
        
        cps_layout.addWidget(self.current_cursor_radio)
        cps_layout.addWidget(self.chosen_cursor_radio)
        
        cursor_layout.addLayout(cps_layout)

        coord_layout = QHBoxLayout()
        self.cursor_x_input = QLineEdit()  # Definición de cursor_x_input
        self.cursor_y_input = QLineEdit()  # Definición de cursor_y_input
        coord_layout.addWidget(QLabel("X:"))
        coord_layout.addWidget(self.cursor_x_input)
        coord_layout.addWidget(QLabel("Y:"))
        coord_layout.addWidget(self.cursor_y_input)
        cursor_layout.addLayout(coord_layout)

        self.coordinates_label = QLabel("X: 0, Y: 0")
        cursor_layout.addWidget(self.coordinates_label)

        cursor_group.setLayout(cursor_layout)
        main_layout.addWidget(cursor_group)

        # Barra inferior
        bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(bottom_bar)

        # Contadores de clicks
        clicks_layout = QHBoxLayout()
        self.total_clicks_label = QLabel("Total de clics: 0")  # Actualizar texto
        self.last_24h_clicks_label = QLabel("Clics en las últimas 24h: 0")  # Nuevo contador
        self.today_clicks_label = QLabel("Hoy: 0")  # Actualizar texto
        self.session_clicks_label = QLabel("Sesión: 0")  # Definición de session_clicks_label
        self.version_label = QLabel("Versión: 0.0.1")  # Mover la versión al final
        
        clicks_layout.addWidget(self.total_clicks_label)
        clicks_layout.addWidget(self.last_24h_clicks_label)
        clicks_layout.addWidget(self.today_clicks_label)
        clicks_layout.addWidget(self.session_clicks_label)  # Agregar session_clicks_label
        bottom_layout.addLayout(clicks_layout)
        
        # Agregar la versión en una nueva línea
        bottom_layout.addWidget(self.version_label)  # Mover la versión al final
        
        bottom_layout.addStretch()

        # Checkbox de ayuda
        self.help_checkbox = QCheckBox("Mostrar ayuda")  # Definición de help_checkbox
        self.help_checkbox.setChecked(True)
        self.help_checkbox.stateChanged.connect(self.toggle_tooltips)
        bottom_layout.addWidget(self.help_checkbox)

        # ThemeSwitch
        self.theme_switch = ThemeSwitch(self)
        self.theme_switch.set_checked(self.theme == "dark")
        self.theme_switch.mousePressEvent = lambda event: self.toggle_theme(event)
        bottom_layout.addWidget(self.theme_switch)

        main_layout.addWidget(bottom_bar)

    def update_version(self, version):
        self.version_label.setText(f"Versión: {version}")

    def create_spinbox(self, label):
        spinbox = QSpinBox()
        spinbox.setRange(0, 999 if label == "Milisegundos:" else 59)
        spinbox.setFixedWidth(50)
        spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        return spinbox

    def load_config(self):
        self.cps_spinbox.setValue(int(self.settings.value("cps", 10)))
        self.cursor_x_input.setText(self.settings.value("chosen_x", "0"))
        self.cursor_y_input.setText(self.settings.value("chosen_y", "0"))
        
        cursor_mode = self.settings.value("cursor_mode", "current")
        if cursor_mode == "chosen":
            self.chosen_cursor_radio.setChecked(True)
        else:
            self.current_cursor_radio.setChecked(True)
        
        for i, spinbox in enumerate(self.interval_spinboxes):
            spinbox.setValue(int(self.settings.value(f"interval_{['hours', 'minutes', 'seconds', 'milliseconds'][i]}", 0)))
        
        show_help = self.settings.value("show_help", "true") == "true"
        self.help_checkbox.setChecked(show_help)
        self.toggle_tooltips(Qt.CheckState.Checked if show_help else Qt.CheckState.Unchecked)

    def save_config(self):
        self.settings.setValue("theme", self.theme)
        self.settings.setValue("custom_color", self.custom_color)
        self.settings.setValue("window_position", self.pos())
        self.settings.setValue("chosen_x", self.cursor_x_input.text())
        self.settings.setValue("chosen_y", self.cursor_y_input.text())
        self.settings.setValue("cursor_mode", "chosen" if self.chosen_cursor_radio.isChecked() else "current")
        self.settings.setValue("cps", self.cps_spinbox.value())
        
        for i, spinbox in enumerate(self.interval_spinboxes):
            self.settings.setValue(f"interval_{['hours', 'minutes', 'seconds', 'milliseconds'][i]}", spinbox.value())
        
        self.settings.setValue("total_clicks", self.total_clicks)
        self.settings.setValue("today_clicks", self.today_clicks)
        self.settings.setValue("last_click_date", self.last_click_date.toString(Qt.DateFormat.ISODate))
        self.settings.setValue("show_help", self.help_checkbox.isChecked())
        
        self.settings.sync()

    def setup_hotkeys(self):
        self.global_hotkeys = GlobalHotKeys()
        self.global_hotkeys.f6_pressed.connect(self.safe_toggle_clicking)
        self.global_hotkeys.f11_pressed.connect(self.close)

    def safe_toggle_clicking(self):
        logger.debug("safe_toggle_clicking llamado")
        QTimer.singleShot(0, self.toggle_clicking)

    def toggle_clicking(self):
        self.is_clicking = not self.is_clicking
        if self.is_clicking:
            self.start_clicking()
            self.start_stop_button.setText("Detener (F6)")
        else:
            self.stop_clicking()
            self.start_stop_button.setText("Iniciar (F6)")
        self.update_ui_state()
        logger.debug(f"Clicking {'iniciado' if self.is_clicking else 'detenido'}")

    def start_clicking(self):
        interval = self.get_interval()
        self.click_timer.start(interval)
        logger.debug(f"Clicking iniciado con intervalo de {interval}ms")

    def stop_clicking(self):
        self.click_timer.stop()
        logger.debug("Clicking detenido")

    def perform_click(self):
        if self.is_clicking:
            if self.chosen_cursor_radio.isChecked():
                x = int(self.cursor_x_input.text())
                y = int(self.cursor_y_input.text())
            else:
                x, y = win32api.GetCursorPos()
            
            # Obtener las dimensiones de la pantalla
            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            
            # Asegurarse de que las coordenadas estén dentro de la pantalla
            x = max(0, min(x, screen_width - 1))
            y = max(0, min(y, screen_height - 1))
            
            # Mover el cursor y realizar el clic
            win32api.SetCursorPos((x, y))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
            
            self.click_count += 1
            self.total_clicks += 1
            self.session_clicks += 1
            self.today_clicks += 1
            self.update_click_count()
            print(f"Clic realizado en ({x}, {y}). Total: {self.click_count}")

    def update_click_count(self):
        self.update_click_labels()
        self.save_config()

    def update_click_labels(self):
        self.total_clicks_label.setText(f"Total: {self.total_clicks}")
        self.session_clicks_label.setText(f"Sesión: {self.session_clicks}")
        self.today_clicks_label.setText(f"Hoy: {self.today_clicks}")

    def get_interval(self):
        cps = self.cps_spinbox.value()
        if cps > 0:
            return max(1, int(1000 / cps))
        else:
            hours, minutes, seconds, milliseconds = [spinbox.value() for spinbox in self.interval_spinboxes]
            return max(1, (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds)

    def update_interval(self):
        interval = self.get_interval()
        if self.is_clicking:
            self.click_timer.setInterval(interval)
        logger.debug(f"Intervalo actualizado a {interval} ms")

    def update_current_cursor_position(self):
        x, y = pyautogui.position()
        self.coordinates_label.setText(f"X: {x}, Y: {y}")
        if self.current_cursor_radio.isChecked():
            self.cursor_x_input.setText(str(x))
            self.cursor_y_input.setText(str(y))

    def choose_cursor_position(self):
        print("Iniciando selección de posición")
        self.is_selecting = True
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.close()
        self.overlay = OverlayWidget(self)
        self.overlay.showFullScreen()
        print("Overlay creado y mostrado en pantalla completa")

    def on_overlay_click(self, pos):
        self.cursor_x_input.setText(str(pos.x()))
        self.cursor_y_input.setText(str(pos.y()))
        self.chosen_cursor_radio.setChecked(True)
        self.update_cursor_mode()
        self.overlay.close()
        self.is_selecting = False
        print(f"Posición seleccionada: X={pos.x()}, Y={pos.y()}")

    def update_cursor_mode(self):
        is_chosen_mode = self.chosen_cursor_radio.isChecked()
        self.cursor_x_input.setEnabled(is_chosen_mode)
        self.cursor_y_input.setEnabled(is_chosen_mode)
        self.choose_position_button.setEnabled(is_chosen_mode)

    def toggle_theme(self, event):
        self.theme = "dark" if self.theme == "light" else "light"
        self.theme_switch.set_checked(self.theme == "dark")
        self.apply_theme()
        self.update_ui_state()
        self.save_config()

    def apply_theme(self):
        if self.theme == "dark":
            self.setStyleSheet("""
                QWidget {
                    background-color: #1E1E1E;
                    color: #D4D4D4;
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 12px;
                }
                QGroupBox {
                    border: 1px solid #3E3E3E;
                    border-radius: 3px;
                    margin-top: 0.5em;
                    padding-top: 0.5em;
                }
                QPushButton {
                    background-color: #007ACC;
                    color: #FFFFFF;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 2px;
                }
                QPushButton:hover {
                    background-color: #005A9E;
                }
                QLineEdit, QSpinBox {
                    background-color: #252526;
                    border: 1px solid #3E3E3E;
                    color: #D4D4D4;
                    padding: 2px;
                }
                QRadioButton::indicator:checked {
                    background-color: #007ACC;
                    border: 2px solid #D4D4D4;
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget {
                    background-color: #f2f2f7;
                    color: #000000;
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 12px;
                }
                QGroupBox {
                    border: 1px solid #c7c7cc;
                    border-radius: 3px;
                    margin-top: 0.5em;
                    padding-top: 0.5em;
                }
                QPushButton {
                    background-color: #007aff;
                    color: #ffffff;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 2px;
                }
                QPushButton:hover {
                    background-color: #005ecb;
                }
                QLineEdit, QSpinBox {
                    background-color: #ffffff;
                    border: 1px solid #c7c7cc;
                    color: #000000;
                    padding: 2px;
                }
                QRadioButton::indicator:checked {
                    background-color: #007aff;
                    border: 2px solid #ffffff;
                }
            """)

    def update_ui_state(self):
        if self.is_clicking:
            self.start_stop_button.setText("Detener (F6)")
            self.start_stop_button.setStyleSheet("background-color: #FF4136;")
        else:
            self.start_stop_button.setText("Iniciar (F6)")
            self.start_stop_button.setStyleSheet("")
        
        self.cps_spinbox.setEnabled(not self.is_clicking)
        for spinbox in self.interval_spinboxes:
            spinbox.setEnabled(not self.is_clicking)

    def set_tooltips(self):
        self.start_stop_button.setToolTip("Inicia o detiene el autoclicker. También puedes usar F6 como atajo de teclado.")
        self.cps_spinbox.setToolTip("Ajusta los clics por segundo.")
        for i, spinbox in enumerate(self.interval_spinboxes):
            spinbox.setToolTip(f"Ajusta los {'horas' if i == 0 else 'minutos' if i == 1 else 'segundos' if i == 2 else 'milisegundos'} entre clics.")
        self.current_cursor_radio.setToolTip("El clic se realizará en la posición actual del cursor en cada intervalo.")
        self.chosen_cursor_radio.setToolTip("El clic se realizará siempre en la posición fija que hayas elegido.")
        self.cursor_x_input.setToolTip("Coordenada X de la posición elegida.")
        self.cursor_y_input.setToolTip("Coordenada Y de la posición elegida.")
        self.choose_position_button.setToolTip("Haz clic aquí y luego en cualquier parte de la pantalla para elegir la posición fija.")
        self.help_checkbox.setToolTip("Activa o desactiva estos mensajes de ayuda.")
        self.theme_switch.setToolTip("Cambia entre el tema claro y oscuro de la interfaz.")
        self.total_clicks_label.setToolTip("Número total de clics realizados desde que se instaló la aplicación.")
        self.session_clicks_label.setToolTip("Número de clics realizados en esta sesión de uso.")
        self.today_clicks_label.setToolTip("Número de clics realizados hoy.")
        self.coordinates_label.setToolTip("Muestra la posición actual del cursor en la pantalla.")

    def toggle_tooltips(self, state):
        duration = -1 if state == Qt.CheckState.Checked else 0
        for widget in self.findChildren(QWidget):
            if hasattr(widget, 'setToolTipDuration'):
                widget.setToolTipDuration(duration)
        # Asegúrate de que el checkbox mantenga su estado
        self.help_checkbox.setChecked(state == Qt.CheckState.Checked)

    def init_menu(self):
        menu_bar = self.menuBar()
        
        file_menu = QMenu("Archivo", self)
        close_item = file_menu.addAction("Cerrar")
        close_item.triggered.connect(self.close)
        menu_bar.addMenu(file_menu)

        help_menu = QMenu("Ayuda", self)
        about_item = help_menu.addAction("Acerca de")
        about_item.triggered.connect(self.show_about)
        menu_bar.addMenu(help_menu)

    def show_about(self):
        about_text = ("¡Bienvenido a Clicker AutoUpdate!\n\n"
                      "Esta es una herramienta avanzada de automatización diseñada para simplificar tareas repetitivas "
                      "y mejorar la eficiencia en diversas aplicaciones y juegos.\n\n"
                      "Optimiza tu experiencia en juegos como Cookie Clicker, Adventure Capitalist y Clicker Heroes, "
                      "realizando clics automáticos de manera eficiente.\n\n"
                      "Esta aplicación está en constante desarrollo para ofrecerte nuevas funcionalidades y mejoras.\n\n"
                      "Desarrollada por xThreeh.")
        QMessageBox.about(self, "Acerca de Clicker AutoUpdate", about_text)  # Cambiado el título de la ventana

    def load_window_position(self):
        pos = self.settings.value("window_position")
        if pos:
            self.move(pos)

    def closeEvent(self, event):
        self.save_config()
        if hasattr(self, 'global_hotkeys'):
            self.global_hotkeys.listener.stop()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = AutoClickerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()