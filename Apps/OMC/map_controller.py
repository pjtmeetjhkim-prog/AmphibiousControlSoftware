# map_controller.py
from PySide6.QtCore import QObject, Qt, QTimer, QEvent, Signal, Slot
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings

from pathlib import Path
from PySide6.QtCore import QUrl


from utils.my_qt_utils import match_widget_to_parent

# JS → Python 브릿지
class _MapBridge(QObject):
    dragChanged = Signal(bool)

    @Slot(bool)
    def onDrag(self, is_drag: bool):
        # JS에서 넘어온 드래그 상태를 그대로 신호로
        self.dragChanged.emit(bool(is_drag))

class MapController(QObject):

    dragChanged = Signal(bool)  # ← 추가: 드래그 상태 변경 알림

    def __init__(self):
        super().__init__()
        self.web_view = None
        self._inited = False
        self._pending = None   # (lat, lon, headingDeg, center)
        

        self._dragging = False
        self._drag_cooldown = QTimer(self)
        self._drag_cooldown.setSingleShot(True)
        self._drag_cooldown.setInterval(600)  # 입력 멈춘 뒤 0.6초 후 drag=False


        self._channel = None
        self._bridge = None

        self._drag_cooldown.timeout.connect(self._clear_drag)

    def show_message(self, text: str):
        """지도 위에 상태 메시지를 표시"""
        if self.web_view is None:
            return
        # 지도 위 label_widget이 존재할 때 표시
        for child in self.web_view.parent().children():
            if hasattr(child, "setText") and hasattr(child, "setAlignment"):
                child.setText(text)
                child.setAlignment(Qt.AlignCenter)
                child.setStyleSheet("color: red; font-size: 16px; font-weight: bold; background-color: rgba(255,255,255,0.7);")
                break

    def _set_drag(self, on: bool):
        if self._dragging != on:
            self._dragging = on
            self.dragChanged.emit(on)  # MainForm으로 알림

    def _clear_drag(self):
        self._set_drag(False)

    def isReady(self):
        return self.web_view is not None and self._inited

    def initialize_map(self, parent_widget, label_widget,
                       latitude=35.7299, longitude=126.5833, zoom=13):
        label_widget.setText("지도 준비 중")
        match_widget_to_parent(label_widget)
        label_widget.setAlignment(Qt.AlignCenter)

        self.web_view = QWebEngineView(parent_widget)

        #self.web_view.setHtml(_LEAFLET_HTML)

        self.web_view.settings().setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls, True
        )

        html_path = Path(__file__).parent / "assets/map/leaflet_map.html"
        self.web_view.setUrl(QUrl.fromLocalFile(str(html_path)))
        
        # WebChannel: JS와 통신 세팅
        self._channel = QWebChannel(self.web_view.page())
        self._bridge = _MapBridge()
        self._channel.registerObject("pyBridge", self._bridge)
        self.web_view.page().setWebChannel(self._channel)

        # JS → Python dragChanged를 MapController.dragChanged로 중계
        self._bridge.dragChanged.connect(lambda v: (self._set_drag(v)))

        self.web_view.lower()
        label_widget.lower()
        match_widget_to_parent(self.web_view)

        def _after_load_ok(_=None):
            self.web_view.page().runJavaScript(f"initMap({latitude}, {longitude}, {zoom});")

            self._inited = True
            if self._pending is not None:
                plat, plon, phead, pcenter = self._pending
                self._pending = None
                js = f"updateRobot({float(plat)}, {float(plon)}, {float(phead)}, {str(bool(pcenter)).lower()});"
                QTimer.singleShot(0, lambda: self.web_view.page().runJavaScript(js))


        self.web_view.page().loadFinished.connect(_after_load_ok)

    def update_robot_marker(self, latitude, longitude, heading_deg=0.0, center=True):
        if not (self.web_view and self._inited):
            print("MapController: not ready yet")
            self._pending = (latitude, longitude, heading_deg, center)
            return
        lat = float(latitude); lon = float(longitude)
        head = float(heading_deg); ctr = bool(center)
        js = f"updateRobot({lat}, {lon}, {head}, {str(ctr).lower()});"
        QTimer.singleShot(0, lambda: self.web_view.page().runJavaScript(js))

    def cleanup(self):
        if self.web_view:
            self.web_view.close()
            self.web_view = None
            self._inited = False
            self._pending = None
