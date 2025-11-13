"""
filename: MainForm.py
author: gbox3d

위 주석을 수정하지 마시오
"""
import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Signal, Slot,QTimer, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtGui import QImage, QPixmap

import UI.reference.mainForm
from utils.cssutils import change_background_color, change_text_color
from utils.my_qt_utils import match_widget_to_parent
from configMng import ConfigManager

# --- 상단 import 근처에 추가 ---
from PySide6.QtGui import QTextCursor

# 리팩토링된 컨트롤러 및 매니저 임포트
from dectector.video_controller import VideoController
from map_controller import MapController
# from status_manager import StatusManager

from network.network_adapter import NetworkAdapter_MMS, NetworkAdapter_Robot
from client.client import Client

from dectector.video_thread import VideoThread         
from dectector.videoFrame import VideoDialog       

from utils.utils import parse_command_line

class MainForm(QWidget, UI.reference.mainForm.Ui_mainForm):
    
    gotoHomeSignal = Signal()
    gotoSetupSignal = Signal()
    closedSignal = Signal()

    # mapUpdateRequested = Signal(float, float, bool)  # lat, lon, center
    mapUpdateRequested = Signal(float, float, float, bool)  # lat, lon, headingDeg, center
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._dead = False                      # ✅ 생존 플래그
        self.destroyed.connect(lambda: setattr(self, "_dead", True))  # 파괴 시 보강 가드
        
        # # UI 설정
        self.setupUi(self)

        # 설정 관리자 초기화
        self._initialize_config()  

        ROBOT_HOST = self.configMng.config['robotControlServer']['ip']
        ROBOT_PORT = self.configMng.config['robotControlServer']['port']
        MMS_HOST = self.configMng.config['mmsServer']['ip']
        MMS_PORT = self.configMng.config['mmsServer']['port']
        
        CAM_ENABLE = self.configMng.config['cam']['enable']
        IR_CAMERA_URL = self.configMng.config['cam']['irCameraUrl']
        CAMERA_URL = self.configMng.config['cam']['cameraUrl']

        self.IR_CAMERA_URL = IR_CAMERA_URL
        self.CAMERA_URL = CAMERA_URL

        print(f"Camera Enable: {CAM_ENABLE}, IR Camera URL: {IR_CAMERA_URL}, RGB Camera URL: {CAMERA_URL}")

        self._rtsp_thread = None
        self._video_dialog = None

        if CAM_ENABLE:
            print("Camera streaming is enabled.")
            self.addLog("[UI] Camera streaming is enabled.")
            self._start_rtsp(CAMERA_URL)
        else:
            print("Camera streaming is disabled in config.")
            self.addLog("[UI] Camera streaming is disabled in config.")

        if self.configMng.config['robotControlServer']['enable']:
            print(f"Robot Control Server Enabled: {ROBOT_HOST}:{ROBOT_PORT}")
            self.netRobot = NetworkAdapter_Robot(
                lambda: Client(host=ROBOT_HOST, port=ROBOT_PORT)
            )
        else:
            print("Robot Control Server Disabled in Config.")
            self.netRobot = None

        if self.configMng.config['mmsServer']['enable']:
            print(f"MMS Server Enabled: {MMS_HOST}:{MMS_PORT}")
            self.netMMS = NetworkAdapter_MMS(
                lambda: Client(host=MMS_HOST, port=MMS_PORT)
            )
        else:
            print("MMS Server Disabled in Config.")
            self.netMMS = None

        # 어댑터 시그널 구독 → UI 슬롯
        if self.netMMS:
            self.netMMS.connected.connect(self._ui_on_connected)
            self.netMMS.disconnected.connect(self._ui_on_disconnected)
            self.netMMS.error.connect(self._ui_on_error)
            self.netMMS.message.connect(self._ui_on_message)
            self.netMMS._on_push_update = self._ui_on_push_update

        # 로봇 어댑터 시그널 구독 → UI 슬롯
        if self.netRobot:
            self.netRobot.connected.connect(self._rbot_ui_on_connected)
            self.netRobot.disconnected.connect(self._rbot_ui_on_disconnected)
            self.netRobot.error.connect(self._rbot_ui_on_error)
            self.netRobot.message.connect(self._rbot_ui_on_message)
            self.netRobot._on_push_update = self._rbot_ui_on_push_update

        # 앱 종료 시 안전 정리
        QApplication.instance().aboutToQuit.connect(self.netMMS.shutdown)

        # 자동 연결 (원래 Connect_network에서 하던 동작)
        self.netMMS.start()
        self.netRobot.start() 
        #=======================================================================

        # === 추가: 메타데이터 주기 폴링 타이머 ===
        self._meta_interval_ms = 1000  # 기본 1초 (원하면 옵션화)
        self._meta_timer = QTimer(self)
        self._meta_timer.setInterval(self._meta_interval_ms)
        self._meta_timer.timeout.connect(self._poll_MMS_metadata)

        # === 추가: 하트비트 타이머(서버가 code=100 후 끊는 현상 방지) ===
        # self._hb_interval_ms = 3000          # 서버 요건에 맞게 조정(예: 300~1000ms)
        # self._hb_timer = QTimer(self)
        # self._hb_timer.setInterval(self._hb_interval_ms)
        # self._hb_timer.timeout.connect(self._send_heartbeat)


        self.rb_opmode_auto.clicked.connect(self.onClicked_opmode_Group)
        self.rb_opmode_operator.clicked.connect(self.onClicked_opmode_Group)
        self.rb_opmode_manual.clicked.connect(self.onClicked_opmode_Group)

        self.rb_ms_move.clicked.connect(self.onClicked_mission_mode_Group)
        self.rb_ms_patrol.clicked.connect(self.onClicked_mission_mode_Group)
        self.rb_ms_tracking.clicked.connect(self.onClicked_mission_mode_Group)
        self.rb_ms_return.clicked.connect(self.onClicked_mission_mode_Group)
        self.rb_ms_stop.clicked.connect(self.onClicked_mission_mode_Group)

        self.current_robot_data = {}
        self.current_robot_status = {}

        self.initControlKeyPadUI() # 키패드 UI 초기화

        self._initialize_controllers()

        
        self.mapUpdateRequested.connect(
            lambda lat, lon, heading, center:
                self.mapController.update_robot_marker(lat, lon, heading, center)
        )

        self.btnGoHome.clicked.connect(self.gotoHome)
        self.btnGotoSetup.clicked.connect(self.gotoSetup)

        self.pushButton_cmd_Send.clicked.connect(self.OnSendCustomCommand)
        self.btnZoomIn.clicked.connect(self.onClickedBtnZoomInMainScreen)

    def _start_rtsp(self, url: str):
        """RTSP 스레드를 시작하고 프레임 신호를 UI에 연결"""
        try:
            if self._rtsp_thread:
                self._stop_rtsp()
            self._rtsp_thread = VideoThread(url)
            self._rtsp_thread.change_pixmap_signal.connect(self._on_rtsp_frame)
            self._rtsp_thread.start()
            self.addLog(f"[UI] RTSP started: {url}")
        except Exception as e:
            self.addLog(f"[UI] ❌ RTSP start error: {e}")

    def _stop_rtsp(self):
        """RTSP 스레드를 안전하게 중지"""
        try:
            if self._rtsp_thread:
                self._rtsp_thread.stop()
                self._rtsp_thread = None
                self.addLog("[UI] RTSP stopped")
        except Exception as e:
            self.addLog(f"[UI] ❌ RTSP stop error: {e}")

    @Slot(object)
    def _on_rtsp_frame(self, cv_img):
        """VideoThread에서 온 BGR 프레임을 QLabel/확대창에 반영"""
        try:
            # OpenCV BGR -> RGB
            h, w = cv_img.shape[:2]
            rgb = cv_img[:, :, ::-1].copy()
            qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(qimg)

            # 메인 화면 갱신 (디자이너에 있는 QLabel 이름 사용)
            if hasattr(self, "mainCamScreen_bmpLabel") and self.mainCamScreen_bmpLabel:
                # 라벨 크기에 맞게 유지비율 스케일
                scaled = pix.scaled(self.mainCamScreen_bmpLabel.size(),
                                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.mainCamScreen_bmpLabel.setPixmap(scaled)

            # 확대 다이얼로그가 열려 있으면 동시 업데이트
            if self._video_dialog and self._video_dialog.isVisible():
                self._video_dialog.update_video_frame(pix)
        except Exception as e:
            # 프레임 변환 문제는 조용히 로깅
            print(f"[UI] _on_rtsp_frame error: {e}")

    def camZoomIn(self):
        """카메라 줌 인 (확대)"""
        if self._video_dialog is None:
            self._video_dialog = VideoDialog(self)
        self._video_dialog.show()
        self._video_dialog.raise_()
    def camZoomOut(self):
        """카메라 줌 아웃 (축소)"""
        if self._video_dialog:
            self._video_dialog.close()
            self._video_dialog = None


    # --- MainForm 클래스 내부에 유틸 추가(아무 메서드 위든 OK) ---
    def _is_log_view_at_bottom(self) -> bool:
        """사용자가 현재 로그뷰 맨 아래를 보고 있는지 판단"""
        sb = self.edLogText.verticalScrollBar()
        # 여유 마진 2~3 정도 두면 픽셀 오차에도 안정적
        return sb.value() >= (sb.maximum() - 2)

    # --- 기존 addLog 교체 ---
    def addLog(self, message: str):
        """로그 메시지 추가 (맨 아래 보고 있을 때만 자동 스크롤)"""
        try:
            stick_bottom = self._is_log_view_at_bottom()
            self.edLogText.appendPlainText(message)

            if stick_bottom:
                # 방법 A: 스크롤바 값을 끝으로
                sb = self.edLogText.verticalScrollBar()
                sb.setValue(sb.maximum())
        except Exception as e:
            print(f"[UI] addLog error: {e}")
    def clearLog(self):
        """로그 뷰 클리어"""
        self.edLogText.clear()

    # 키보드
    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_Up:
            print("Key Up Pressed")
        elif key == Qt.Key_Down:
            print("Key Down Pressed")
        elif key == Qt.Key_Left:
            print("Key Left Pressed")
        elif key == Qt.Key_Right:
            print("Key Right Pressed")
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        key = event.key()

        if key == Qt.Key_Up:
            print("Key Up Released")
        elif key == Qt.Key_Down:
            print("Key Down Released")
        elif key == Qt.Key_Left:
            print("Key Left Released")
        elif key == Qt.Key_Right:
            print("Key Right Released")
        else:
            super().keyReleaseEvent(event)
    
    @Slot()
    def onClicked_opmode_Group(self):
        try:
            current_unit_index = self.current_unit_index + 1
            if self.rb_opmode_auto.isChecked():
                print("Operation Mode: Auto")
                self.netMMS.set_json_by_key(f"robot_{current_unit_index}.operation_mode", "auto")

            elif self.rb_opmode_operator.isChecked():
                print("Operation Mode: Operator")
                self.netMMS.set_json_by_key(f"robot_{current_unit_index}.operation_mode", "operator")
            elif self.rb_opmode_manual.isChecked():
                print("Operation Mode: Manual")
                self.netMMS.set_json_by_key(f"robot_{current_unit_index}.operation_mode", "manual")
        except Exception as e:
            print(f"Error in onClicked_opmode_Group: {e}")
    @Slot()
    def onClicked_mission_mode_Group(self):
        try:
            current_unit_index = self.current_unit_index + 1
            if self.rb_ms_move.isChecked():
                print("Mission Mode: Move")
                self.netMMS.set_json_by_key(f"robot_{current_unit_index}.mission_mode", "move")

            elif self.rb_ms_patrol.isChecked():
                print("Mission Mode: Patrol")
                self.netMMS.set_json_by_key(f"robot_{current_unit_index}.mission_mode", "patrol")
            elif self.rb_ms_tracking.isChecked():
                print("Mission Mode: Tracking")
                self.netMMS.set_json_by_key(f"robot_{current_unit_index}.mission_mode", "tracking")
            elif self.rb_ms_return.isChecked():
                print("Mission Mode: Return")
                self.netMMS.set_json_by_key(f"robot_{current_unit_index}.mission_mode", "return")
            elif self.rb_ms_stop.isChecked():
                print("Mission Mode: Stop")
                self.netMMS.set_json_by_key(f"robot_{current_unit_index}.mission_mode", "stop")
        except Exception as e:
            print(f"Error in onClicked_mission_mode_Group: {e}")

    # === 메타데이터 폴링 ===
    def _update_ui_with_robot_data(self, data: dict):
        """로봇 데이터로 UI 업데이트"""
        # 여기에 UI 업데이트 로직 추가
        self.currentTime.setText(data.get("now_time", "N/A"))
        self.operationTime.setText(data.get("elapsed_time", "N/A"))

    @Slot()
    def _poll_MMS_metadata(self):
        # print("[UI] Polling MMS metadata...")
        unit_no = (getattr(self, "current_unit_index", 0) or 0) + 1
        key = f"robot_{unit_no}"
        # print(f"[UI] Polling MMS metadata... key={key}")
        if getattr(self, "netMMS", None) and self.netMMS.is_connected():
            self.netMMS.fetch_json_by_key(key)   # ← 어댑터 래퍼 호출

            self.netMMS.set_json_by_key(
                f"robot_{unit_no}.status_data",
                self.current_robot_status)


    # === 하트비트 전송 ===
    @Slot()
    def _send_heartbeat(self):
        if getattr(self, "netMMS", None) and self.netMMS.is_connected():
            # self.netMMS.send_ping({"ts": self.netMMS.now_ts()})
            self.netMMS.ping_server()
            # print("[UI] Sent heartbeat ping to MMS.")

    # ===== UI 슬롯 =====
    def _initialize_ui_state(self):
        """UI 초기 상태 설정"""

        try : 
            # self._setup_key_button_visibility()
             # 호기 표시
            self.txUnitNuberInfo.setText(f"{self.current_unit_index+1} 호기")
        
        except Exception as e:
            print(f'error occurred while setting up key button visibility : {e}')

    #===================== NetworkAdapter MMS ====================
    
    @Slot(dict)
    def _ui_on_connected(self, json_info: dict):

        self.label_connection_status.setText("Connected")
        self.label_connection_status.setStyleSheet("color: white;background-color: green;")

        if not self._meta_timer.isActive():
            self._meta_timer.start()
            print("[UI] Started MMS metadata polling timer.")

        # if not self._hb_timer.isActive():
        #     self._hb_timer.start()
        #     print("[UI] Started heartbeat timer.")
        print("[UI] Connected:", json_info)
        self.addLog(f"[UI] Connected to MMS server. Info: {json_info}")

        self._initialize_ui_state()  # UI 초기 상태 설정

    @Slot(str)
    def _ui_on_disconnected(self, reason: str):
        print("[UI] Disconnected:", reason)                
        self.addLog(f"[UI] Disconnected from MMS server: {reason}")

    @Slot(str)
    def _ui_on_error(self, msg: str):
        print("[UI] Error:", msg)
        self.addLog(f"[UI] MMS Error: {msg}")

    @Slot(dict)
    def _ui_on_push_update(self, json_info: dict):
        print("[UI] Push Update:", json_info)
        # self.addLog(f"[UI] Push Update: {json_info}")
    

    @Slot(dict)
    def _ui_on_message(self, payload: dict):
        
        if getattr(self, "_dead", False):
            return

        self.current_robot_data = payload.get("data", {})
        _robot_data = self.current_robot_data.get("value", {})

        # print(f"[UI] Received robot data: {_robot_data}")

        if _robot_data:
            
            self._update_ui_with_robot_data(self.current_robot_data)
            
            mission_mode = _robot_data.get("mission_mode", "unknown")
            operation_mode = _robot_data.get("operation_mode", "unknown")

            self.rb_opmode_auto.setChecked(False)
            self.rb_opmode_operator.setChecked(False)
            self.rb_opmode_manual.setChecked(False)

            if operation_mode == "auto":
                self.rb_opmode_auto.setChecked(True)
            if operation_mode == "operator":
                self.rb_opmode_operator.setChecked(True)
            if operation_mode == "manual":
                self.rb_opmode_manual.setChecked(True)


            self.rb_ms_move.setChecked(False)
            self.rb_ms_patrol.setChecked(False)            
            self.rb_ms_tracking.setChecked(False)
            self.rb_ms_return.setChecked(False)
            self.rb_ms_stop.setChecked(False)
            

            if mission_mode == "move":
                self.rb_ms_move.setChecked(True)
            elif mission_mode == "patrol":
                self.rb_ms_patrol.setChecked(True)
            elif mission_mode == "tracking":
                self.rb_ms_tracking.setChecked(True)
            elif mission_mode == "return":
                self.rb_ms_return.setChecked(True)
            elif mission_mode == "stop":
                self.rb_ms_stop.setChecked(True)

            # 로봇에게 미션 운용 데이터 보내기 
            self.netRobot.control_robot_apply_patch(
                mission_mode=mission_mode,
                operation_mode=operation_mode
            )



    #===================== NetworkAdapter Robot ====================
    @Slot(dict)
    def _rbot_ui_on_connected(self, json_info: dict):
        print("[UI] Robot Connected:", json_info)
        self.addLog(f"[UI] Robot Connected. Info: {json_info}")
    @Slot(str)
    def _rbot_ui_on_disconnected(self, reason: str):
        print("[UI] Robot Disconnected:", reason)
        self.addLog(f"[UI] Robot Disconnected: {reason}")
        if self.mapController:
            self.mapController.show_message("🚫 로봇과 연결되지 않았습니다.")
    @Slot(str)
    def _rbot_ui_on_error(self, msg: str):
        print("[UI] Robot Error:", msg)    
        self.addLog(f"[UI] Robot Error: {msg}")
        if self.mapController:
            self.mapController.show_message("🚫 로봇과 연결되지 않았습니다.")

    @Slot(dict)
    def _rbot_ui_on_push_update(self, json_info: dict):
        # print("[UI] Robot Push Update:", json_info)
        """로봇 푸시 업데이트 처리
        {
            'cmd': 'robot_update', 
            'data': {
                'id': 1, 'x': 0, 'y': 0, 'angle': 0, 
                'mode': 'manual', 'mission': 'stop', 
                'wheelbase': 1.2, 'wheelRadius': 0.15, 'steerLimitDeg': 35, 'maxWheelRPM': 300, 
                'WheelSpeed': 0, 'WheelAngle': 0, 'WheelOmega': 2, 'steerDeg': 0, 'v': 0, 
                'longitude': 127, 'latitude': 37.5, 'originLon': 127, 'originLat': 37.5, 
                'metersPerDeg': 111320
            }
        }
        
        """
        cmd = json_info.get("cmd", "")
        if cmd == "robot_update":

            try :
                data = json_info.get("data", {})

                self.current_robot_status = data

                # print("[UI] Robot Update Data:", data)
                self.label_robot_veloX.setText(f"{data.get('vx', 0):.2f} m/s")
                self.label_robot_veloY.setText(f"{data.get('vy', 0):.2f} m/s")
                self.robot_heading_degree.setText(f"{data.get('angle', 0):.2f} °")

                self.label_battery_level.setText(f"{data.get('battPercent', 0)} %")
                self.label_battery_temper.setText(f"{data.get('battTempC', 0)} °C")
                self.label_battery_status.setText(f"{data.get('battState', 'N/A')}")


                # print(f"dragStatus: {self.dragStatus}")

                # _rbot_ui_on_push_update 내부 지도 갱신 부분
                if self.mapController and self.mapController.isReady():
                    lat = data.get("latitude"); lon = data.get("longitude")
                    heading = data.get("angle", 0.0)
                    if lat is not None and lon is not None:
                        self._last_lat = float(lat)
                        self._last_lon = float(lon)
                        self._last_heading = float(heading)
                        # 자동센터 여부는 dragStatus로 제어
                        # if self.centerMap:
                        self.mapUpdateRequested.emit(self._last_lat, self._last_lon, self._last_heading, self.centerMap)


                # 마지막 RPM 저장(이미 작성하신 라인 유지)
                self._last_rpm = int(data.get("WheelSpeed", 0))

            except Exception as e:
                print(f"Error processing robot update data: {e}")
                return

            # # 마지막 RPM 저장
            # self._last_rpm = int(data.get("WheelSpeed", 0))

    @Slot(dict)
    def _rbot_ui_on_message(self, payload: dict):
        print("[UI] Robot Message:", payload)

    #===================== UI 초기화 ====================
    
    def _initialize_config(self):
        """설정 파일 로드 및 초기화"""
        self.configMng = ConfigManager()
        if not self.configMng.load_config():
            print("ConfigManager: 설정 파일 로드 실패")
            sys.exit(-1)
        
        print("ConfigManager: 설정 파일 로드 성공")
        
        self.current_unit_index = self.configMng.get_current_select_unit() - 1
        # self.current_unit_index_sub = self.configMng.get_current_select_unit_sub() - 1
        
        print(f"ConfigManager: 현재 선택된 차량 인덱스: {self.current_unit_index}")
        # print(f"ConfigManager: 현재 선택된 서브 차량 인덱스: {self.current_unit_index_sub}")       
     
    def initControlKeyPadUI(self):
        """키패드 UI 초기화"""
        # 방향키 버튼
        self.btnKeyUp.pressed.connect(self.keyUpPressed)
        self.btnKeyUp.released.connect(self.keyUpReleased)
        self.btnKeyDown.pressed.connect(self.keyDownPressed)
        self.btnKeyDown.released.connect(self.keyDownReleased)
        self.btnKeyLeft.pressed.connect(self.keyLeftPressed)
        self.btnKeyLeft.released.connect(self.keyLeftReleased)
        self.btnKeyRight.pressed.connect(self.keyRightPressed)
        self.btnKeyRight.released.connect(self.keyRightReleased)
          
        self.label_keyup_normal.setVisible(True)
        self.label_keyup_push.setVisible(False)
        self.label_keydown_normal.setVisible(True)
        self.label_keydown_push.setVisible(False)
        self.label_keyleft_normal.setVisible(True)
        self.label_keyleft_push.setVisible(False)
        self.label_keyright_normal.setVisible(True)
        self.label_keyright_push.setVisible(False)
      
    def _initialize_controllers(self):
        """컨트롤러 및 매니저 초기화"""
        # 상태 관리자
        # self.statusManager = StatusManager()
        
        # # 비디오 컨트롤러
        # self.videoController = VideoController(
        #     self.configMng,
        #     self.current_unit_index,
        #     self.current_unit_index_sub,
        #     self.font_d2coding
        # )
        
        # # 메인 카메라 초기화
        # if self.videoController.initialize_main_camera(self.mainCamScreen_bmpLabel, self.mainCamScreen):
        #     # 비디오 스레드 시그널 연결
        #     self.videoController.mainCameraThread.change_pixmap_signal.connect(
        #         lambda img: self.videoController.update_main_image(
        #             img, self.mainCamScreen_bmpLabel, self.mainCamScreen
        #         )
        #     )
            
        #     # 감지 서버 초기화
        #     if self.videoController.initialize_detection(self.edLogText):
        #         self.videoController.yolo_detection_thread.detection_results.connect(
        #             lambda d, i: self.videoController.on_detection_results(d, i, self.edLogText)
        #         )
        #         self.videoController.yolo_detection_thread.status_update.connect(
        #             lambda msg: self.videoController.on_detection_status(msg, self.edLogText)
        #         )
        
        # # 서브 카메라 초기화
        # if self.videoController.initialize_sub_camera(self.labelSubCamera):
        #     match_widget_to_parent(self.labelSubCamera)
        #     self.videoController.subCameraThread.change_pixmap_signal.connect(
        #         lambda img: self.videoController.update_sub_image(img, self.labelSubCamera)
        #     )
        
        # 지도 컨트롤러
        self.mapController = MapController()
        self.mapController.initialize_map(
            self.widgetBottomRightScreen,
            self.labelBottomRightScreen,
            latitude=35.7299,
            longitude=126.5833,
            zoom=18
        )

        self.dragStatus = False
        self.centerMap = True

        # 지도 드래그 상태 신호 연결
        self.mapController.dragChanged.connect(
            lambda is_drag: self._on_map_drag_changed(is_drag)
        )
        self._last_lat = None
        self._last_lon = None
        self._last_heading = 0.0

    @Slot(bool)
    def _on_map_drag_changed(self, is_drag: bool):
        self.dragStatus = is_drag
        if is_drag:
            self.centerMap = False
        print(f"[MAP][UI] dragStatus -> {self.dragStatus}")
    
    
    @Slot()
    def gotoHome(self):
        print("gotoHome")
        self.gotoHomeSignal.emit()
    
    @Slot()
    def gotoSetup(self):
        print("gotoSetup")
        self.gotoSetupSignal.emit()
    
    # 방향키 버튼
    @Slot()
    def keyUpPressed(self):
        self.label_keyup_normal.setVisible(False)
        self.label_keyup_push.setVisible(True)

        self.centerMap = True

         # 로봇 속도 증가 (NetworkAdapter_Robot 방식으로 호출)
        if self.netRobot and self.netRobot.is_connected():
            # rpm: 바퀴 회전 속도, angle_deg: 조향 각도, omega_rad: 조향 변화율
            self.netRobot.control_robot_set_actuators(
                rpm=100,          # 앞으로 가는 속도 (RPM 단위)
                angle_deg=0,      # 조향각 (0이면 직진)
                omega_rad=2.0     # 조향각 변화율 (라디안/초 단위)
            )

        
    
    @Slot()
    def keyUpReleased(self):
        self.label_keyup_normal.setVisible(True)
        self.label_keyup_push.setVisible(False)

        if self.netRobot and self.netRobot.is_connected():
            # WheelSpeed를 0으로 만들어 정지
            self.netRobot.control_robot_set_actuators(
                rpm=0,
                angle_deg=0,
                omega_rad=2.0
            )
    
    @Slot()
    def keyDownPressed(self):
        self.label_keydown_normal.setVisible(False)
        self.label_keydown_push.setVisible(True)

        if self.netRobot and self.netRobot.is_connected():
            # 뒤로 가는 속도 (음수 RPM)
            self.netRobot.control_robot_set_actuators(
                rpm=-100,        # 뒤로 가는 속도 (RPM 단위)
                angle_deg=0,     # 조향각 (0이면 직진)
                omega_rad=2.0    # 조향각 변화율 (라디안/초 단위)
            )
        
    
    @Slot()
    def keyDownReleased(self):
        self.label_keydown_normal.setVisible(True)
        self.label_keydown_push.setVisible(False)

        if self.netRobot and self.netRobot.is_connected():
            # WheelSpeed를 0으로 만들어 정지
            self.netRobot.control_robot_set_actuators(
                rpm=0,
                angle_deg=0,
                omega_rad=2.0
            )
    
    @Slot()
    def keyLeftPressed(self):
        self.label_keyleft_normal.setVisible(False)
        self.label_keyleft_push.setVisible(True)

        if self.netRobot and self.netRobot.is_connected():
        # 현재 속도(self._last_rpm)를 유지한 채로 왼쪽으로 조향
            rpm = self._last_rpm if self._last_rpm != 0 else 100  # 정지상태면 기본 전진값
            self.netRobot.control_robot_set_actuators(
                rpm=rpm,
                angle_deg=25,
                omega_rad=2.0
            )
        
    
    @Slot()
    def keyLeftReleased(self):
        self.label_keyleft_normal.setVisible(True)
        self.label_keyleft_push.setVisible(False)

        if self.netRobot and self.netRobot.is_connected():
        # 각도만 0으로 복귀(속도는 유지)
            rpm = self._last_rpm
            self.netRobot.control_robot_set_actuators(
                rpm=0,
                angle_deg=0,
                omega_rad=2.0
            )        
    
    @Slot()
    def keyRightPressed(self):
        self.label_keyright_normal.setVisible(False)
        self.label_keyright_push.setVisible(True)

        if self.netRobot and self.netRobot.is_connected():
        # 현재 속도(self._last_rpm)를 유지한 채로 오른쪽으로 조향
            rpm = self._last_rpm if self._last_rpm != 0 else 100  # 정지상태면 기본 전진값
            self.netRobot.control_robot_set_actuators(
                rpm=rpm,
                angle_deg=-25,
                omega_rad=2.0
            )
        
    
    @Slot()
    def keyRightReleased(self):
        self.label_keyright_normal.setVisible(True)
        self.label_keyright_push.setVisible(False)

        if self.netRobot and self.netRobot.is_connected():
        # 각도만 0으로 복귀(속도는 유지)
            rpm = self._last_rpm
            self.netRobot.control_robot_set_actuators(
                rpm=0,
                angle_deg=0,
                omega_rad=2.0
            )
        
    
    # 비상정지 버튼
    @Slot()
    def btnAbnormalStopPressed(self):
        print("btnAbnormalStopPressed")
        change_background_color(self.btnAbnormalStop, '#FFFFFF')
        change_text_color(self.btnAbnormalStop, '#FF0000')
    
    @Slot()
    def btnAbnormalStopReleased(self):
        print("btnAbnormalStopReleased")
        change_background_color(self.btnAbnormalStop, '#FF0000')
        change_text_color(self.btnAbnormalStop, '#FFFFFF')
    
    @Slot()
    def btnAbnormalStopClicked(self):
        print("btnAbnormalStopClicked")
    
    # 모드 선택 버튼
    @Slot()
    def onClickedBtnAutoDrv(self):
        change_background_color(self.btnAutoDrv, self.checkBackgroundColor)
        change_text_color(self.btnAutoDrv, self.checkColor)
        change_background_color(self.btnRemoteDrv, self.defaultBackgroundColor)
        change_text_color(self.btnRemoteDrv, self.defaultColor)
        print("onClickedBtnAutoDrv")
    
    @Slot()
    def onClickedBtnRemoteDrv(self):
        change_background_color(self.btnAutoDrv, self.defaultBackgroundColor)
        change_text_color(self.btnAutoDrv, self.defaultColor)
        change_background_color(self.btnRemoteDrv, self.checkBackgroundColor)
        change_text_color(self.btnRemoteDrv, self.checkColor)
        print("onClickedBtnRemoteDrv")
    
    @Slot()
    def onClickedBtnOpticalMode(self):
        change_background_color(self.btnOpticalMode, self.checkBackgroundColor)
        change_text_color(self.btnOpticalMode, self.checkColor)
        change_background_color(self.btnIRMode, self.defaultBackgroundColor)
        change_text_color(self.btnIRMode, self.defaultColor)
        print("onClickedBtnOpticalMode")
    
    @Slot()
    def onClickedBtnIRMode(self):
        change_background_color(self.btnOpticalMode, self.defaultBackgroundColor)
        change_text_color(self.btnOpticalMode, self.defaultColor)
        change_background_color(self.btnIRMode, self.checkBackgroundColor)
        change_text_color(self.btnIRMode, self.checkColor)
        print("onClickedBtnIRMode")
    
    @Slot()
    def onClickedBtnScaleUp(self):
        change_background_color(self.btnScaleUp, self.checkBackgroundColor)
        change_text_color(self.btnScaleUp, self.checkColor)
        change_background_color(self.btnScaleDown, self.defaultBackgroundColor)
        change_text_color(self.btnScaleDown, self.defaultColor)
        print("onClickedBtnScaleUp")
    
    @Slot()
    def onClickedBtnScaleDown(self):
        change_background_color(self.btnScaleUp, self.defaultBackgroundColor)
        change_text_color(self.btnScaleUp, self.defaultColor)
        change_background_color(self.btnScaleDown, self.checkBackgroundColor)
        change_text_color(self.btnScaleDown, self.checkColor)
        print("onClickedBtnScaleDown")
    
    @Slot()
    def onClickedBtnUnLock(self):
        change_background_color(self.labelUnLock, self.checkBackgroundColor)
        change_text_color(self.labelUnLock, self.checkColor)
        change_background_color(self.labelLock, self.defaultBackgroundColor)
        change_text_color(self.labelLock, self.defaultColor)
        print("onClickedBtnUnLock")
    
    @Slot()
    def onClickedBtnLock(self):
        change_background_color(self.labelLock, self.checkBackgroundColor)
        change_text_color(self.labelLock, self.checkColor)
        change_background_color(self.labelUnLock, self.defaultBackgroundColor)
        change_text_color(self.labelUnLock, self.defaultColor)
        print("onClickedBtnLock")
    
    # 줌 버튼
    @Slot()
    def onClickedBtnZoomInMainScreen(self):
        self.camZoomIn()
    
    @Slot()
    def onClickedBtnZoomInBottomScreen(self):
        print("onClickedBtnZoomInBottomScreen")
    
    @Slot()
    def onClickedBtnZoomInBottomRightScreen(self):
        print("onClickedBtnZoomInBottomRightScreen")
    
    # ==================== 종료 처리 ====================    
    def safeDestroy(self):        
        if getattr(self, "_dead", False):
            return
        self._dead = True
        try:
            # RTSP
            if hasattr(self, "_rtsp_thread") and self._rtsp_thread:
                self._stop_rtsp()

            # 타이머
            if hasattr(self, "_meta_timer") and self._meta_timer.isActive():
                self._meta_timer.stop()
                self._meta_timer.deleteLater()

            # MMS
            if getattr(self, "netMMS", None):
                # ✅ 모든 시그널 끊기
                for sig in ("connected", "disconnected", "error", "message"):
                    try:
                        getattr(self.netMMS, sig).disconnect()
                    except Exception:
                        pass
                self.netMMS._on_push_update = None
                self.netMMS.stop()
                self.netMMS.shutdown()

            # ROBOT
            if getattr(self, "netRobot", None):
                for sig in ("connected", "disconnected", "error", "message"):
                    try:
                        getattr(self.netRobot, sig).disconnect()
                    except Exception:
                        pass
                self.netRobot._on_push_update = None
                self.netRobot.stop()
                self.netRobot.shutdown()

            # 컨트롤러
            if getattr(self, "mapController", None):
                self.mapController.cleanup()

        except Exception as e:
            print(f"[safeDestroy] error: {e}")

    @Slot()
    def OnSendCustomCommand(self):
        raw = self.lineEdit_cmd.text().strip()
        if not raw:
            return

        try:
            cmd, pos, opts = parse_command_line(raw)
        except Exception as e:
            self.addLog(f"[UI] ❌ 명령 구문 분석 오류: {e}")
            return

        def _need_robot():
            if self.netRobot and self.netRobot.is_connected():
                return True
            self.addLog("[UI] ❌ 로봇이 연결되어 있지 않습니다.")
            return False

        # ---------------- RCM ----------------
        if cmd == "rcm":
            if not _need_robot():
                return
            payload = {}

            if opts:
                payload.update(opts)

            # 위치 인자 사용: rcm <key> [value]
            if pos:
                key = str(pos[0])
                if len(pos) >= 2:
                    payload[key] = pos[1]
                else:
                    # 값이 없으면 True 토글
                    payload[key] = True

            if not payload:
                self.addLog("[UI] ⚠️ rcm 사용법: rcm <key> [value] | rcm key=value ... | rcm --flag")
                return

            msg = {"rcm": payload}
            self.netRobot.set_json_by_key("custom_command", msg)
            self.addLog(f"[UI] 🚀 RCM command sent → {msg}")
            return

        # ---------------- CLI ----------------
        if cmd == "cli":
            sub = (str(pos[0]).lower() if pos else "")
            if sub == "clear":
                self.clearLog()
                return
            self.addLog(f"[UI] ⚠️ 알 수 없는 cli 명령: {sub}")
            return

        # ---------------- CAM ----------------
        if cmd == "cam":
            # cam zoom [배율], cam ir, cam rgb
            sub = (str(pos[0]).lower() if pos else "")
            if sub == "zoom":
                # 예: cam zoom 2.0  혹은 cam --zoom 2.0
                factor = None
                if len(pos) >= 2 and isinstance(pos[1], (int, float)):
                    factor = float(pos[1])
                elif "zoom" in opts and isinstance(opts["zoom"], (int, float)):
                    factor = float(opts["zoom"])
                self.camZoomIn() if factor is None else self.camZoomIn(factor)
                return
            if sub in ("ir", "infra", "infrared"):
                self._start_rtsp(self.IR_CAMERA_URL)
                return
            if sub in ("rgb", "color"):
                self._start_rtsp(self.CAMERA_URL)
                return
            self.addLog(f"[UI] ⚠️ 알 수 없는 cam 명령: {sub}")
            return

        # ---------------- RTSP ----------------
        if cmd == "rtsp":
            # rtsp start [url] | rtsp start url=<...> | rtsp stop
            sub = (str(pos[0]).lower() if pos else "")
            if sub == "stop":
                self._stop_rtsp()
                return
            if sub == "start":
                # 우선순위: opts['url'] > pos[1] > config
                url = None
                if "url" in opts and isinstance(opts["url"], str):
                    url = opts["url"]
                elif len(pos) >= 2 and isinstance(pos[1], str):
                    url = pos[1]
                else:
                    url = self.configMng.config['cam']['cameraUrl']
                self._start_rtsp(url)
                return
            self.addLog(f"[UI] ⚠️ 알 수 없는 rtsp 명령: {sub}")
            return

        # ---------------- 기타 ----------------
        self.addLog(f"[UI] ⚠️ 알 수 없는 명령 형식: {raw}")

    

#--- 예외 처리 및 로깅 설정 ---
import sys, faulthandler, traceback
from PySide6.QtCore import qInstallMessageHandler, QtMsgType

faulthandler.enable()

def _excepthook(exc_type, exc, tb):
    print("[EXC] Unhandled exception:", exc_type.__name__, exc); traceback.print_tb(tb)
    sys.__excepthook__(exc_type, exc, tb)
sys.excepthook = _excepthook

def _qt_msg_handler(mode, context, message):
    level = {QtMsgType.QtDebugMsg:"DBG", QtMsgType.QtInfoMsg:"INF",
             QtMsgType.QtWarningMsg:"WRN", QtMsgType.QtCriticalMsg:"CRT",
             QtMsgType.QtFatalMsg:"FTL"}.get(mode, "MSG")
    print(f"[QT-{level}] {message}")
qInstallMessageHandler(_qt_msg_handler)



if __name__ == '__main__':
    theApp = QApplication(sys.argv)
    form = MainForm()
    form.show()
    sys.exit(theApp.exec())
