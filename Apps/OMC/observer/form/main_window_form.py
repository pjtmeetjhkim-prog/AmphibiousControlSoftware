import sys
import cv2
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QGroupBox, QFormLayout, QLabel, QTextEdit,
    QTabWidget, QGridLayout, QListWidget
)
from PySide6.QtCore import Slot, QRect, QTimer, Qt
from PySide6.QtGui import QPixmap, QColor, QImage  # (예시용)

from network_thread_observer import NetworkThread
from tracking_video_wiget_observer import TrackingVideoWidget 
from joystick_thread import JoystickThread
from video_thread_observer import VideoThread
from rtsp_img_sender_observer import ImageSender
from packet_protocol_observer import *
"""
from packet_protocol_observe import (
    PacketProtocol, CommandType, #GenericContentType, 
    # ..제어에 필요한 Enum 임포트    
    TrackingChannel, TrackingCommand,
    MotorMode,MotorPanControl,MotorTiltControl,
    CameraZoomMode, CameraZoomControl, CameraDigitalZoom, NO_COMMAND_POS,
    CameraFocusMode, CameraFocusControl, IRCameraZoom,
)
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("감시장비 통합 제어 시스템 (1, 2호기)")
        self.setGeometry(100, 100, 1920, 700)
        
        # 1. 네트워크 스레드 2개 생성
        self.network_thread_1 = NetworkThread(robot_id=1)
        self.network_thread_2 = NetworkThread(robot_id=2)        
        self.threads = {1: self.network_thread_1, 2: self.network_thread_2}
         
         # [!] 2. 조이스틱 스레드
        self.joystick_thread = JoystickThread()
        self.current_gimbal_move = (0, 0) # 조이스틱 HAT 중복 전송 방지
        self.current_zoom_dir = 0        # 조이스틱 줌 중복 전송 방지
                
        # [!] 3. 배율(Zoom) 상태 저장 변수
        # (채널이 EO/IR인지 알아야 정확한 배율 전송 가능)
        self.current_channel = {1: "EO", 2: "EO"} # (임시: 1,2호기 모두 EO로 시작)
        self.eo_zoom_count = {1: 1, 2: 1} # 1~5 (x1,x2,x4,x8,x12)
        self.ir_zoom_count = {1: 1, 2: 1} # 1~3 (x1,x2,x4)
                
        # [!] 영상 관련 초기화
        self.video_thread = VideoThread()
        self.image_sender = ImageSender()
        self.current_video_source = "EO" # or "IR"
         
        # 4. UI 초기화
        self._init_ui()
        
        # 5. 시그널/슬롯 연결
        self._connect_signals()
        
        # 6. (예시) Heartbeat 타이머 - 1초마다 Heartbeat 전송
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self.send_heartbeats)
        self.heartbeat_timer.start(1000)
        
        # 7. 조이스틱 스레드 시작
        self.joystick_thread.start()

    def _init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        
        # --- 왼쪽: 제어 패널 (1호기, 2호기 탭) ---
        control_panel = QTabWidget()
        control_panel.setFixedWidth(400)
        
        self.robot_1_widget = self._create_robot_control_widget(robot_id=1)
        self.robot_2_widget = self._create_robot_control_widget(robot_id=2)
        
        control_panel.addTab(self.robot_1_widget, "🤖 1호기")
        control_panel.addTab(self.robot_2_widget, "🤖 2호기")
        self.control_panel = control_panel # 조이스틱용 (활성 탭 확인)
        
        # --- 중앙: 비디오 패널 ---
        video_group = QGroupBox("영상 처리")
        video_layout = QVBoxLayout(video_group)
                 
        # 1. RTSP 및 서버 설정 UI
        settings_layout = QFormLayout()
        #default_rtsp_eo = "rtsp://192.168.10.81:3000/eo" if robot_id == 1 else "rtsp://192.168.10.82:4000/eo"
        #default_rtsp_ir = "rtsp://192.168.10.81:4000/ir" if robot_id == 1 else "rtsp://192.168.10.82:4000/ir"     
        self.le_rtsp_eo = QLineEdit("rtsp://192.168.10.81:3000/eo") # 예시
        self.le_rtsp_ir = QLineEdit("rtsp://192.168.10.81:4000/ir")
        self.le_server_ip = QLineEdit("127.0.0.1")
        self.le_server_port = QLineEdit("9999")
        
        self.btn_server_connect = QPushButton("서버 연결")
        self.btn_server_connect.setCheckable(True)
        
        settings_layout.addRow("RTSP (EO):", self.le_rtsp_eo)
        settings_layout.addRow("RTSP (IR):", self.le_rtsp_ir)
        settings_layout.addRow("표적 서버 IP:", self.le_server_ip)
        settings_layout.addRow("표적 서버 Port:", self.le_server_port)
        settings_layout.addRow(self.btn_server_connect)

        # 2. EO/IR 전환 및 상태
        source_layout = QHBoxLayout()
        self.btn_view_eo = QPushButton("EO 영상 보기")
        self.btn_view_ir = QPushButton("IR 영상 보기")                
        self.btn_view_stop = QPushButton("영상 중지") # [!] 영상 중지 버튼 추가
        self.lbl_video_source = QLabel("소스: N/A")
        self.lbl_video_source.setStyleSheet("color: gray; font-weight: bold;")
        source_layout.addWidget(self.btn_view_eo)
        source_layout.addWidget(self.btn_view_ir)
        source_layout.addWidget(self.btn_view_stop) # [!] 레이아웃에 추가
        source_layout.addWidget(self.lbl_video_source)
 
        # [!] TrackingVideoWidget 사용
        self.video_widget = TrackingVideoWidget() 
        
        ## (RTSP/OpenCV 스레드에서 받은 프레임을 여기에 넣어야 함)
        ## (예시: 1920x1080 검은 화면)
        self.dummy_pixmap = QPixmap(1920, 1080)
        self.dummy_pixmap.fill(QColor("black"))
        self.video_widget.set_pixmap(self.dummy_pixmap)
        #video_layout.addWidget(self.video_widget)
        video_layout.addLayout(settings_layout)
        video_layout.addLayout(source_layout)
        video_layout.addWidget(self.video_widget, 1) # stretch factor 1

        # --- 오른쪽: 로그 및 탐지 결과  ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 탐지 결과 그룹
        detect_group = QGroupBox("표적 처리 결과")
        detect_layout = QVBoxLayout(detect_group)
        self.detect_list = QListWidget() # 로그 형식으로 표시
        detect_layout.addWidget(self.detect_list)

        # 시스템 로그 그룹
        log_group = QGroupBox("시스템 로그")
        log_layout = QVBoxLayout(log_group)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        log_layout.addWidget(self.log_edit)
        
        right_layout.addWidget(detect_group, 1)
        right_layout.addWidget(log_group, 1)

        # 메인 레이아웃 조립
        main_layout.addWidget(control_panel)
        main_layout.addWidget(video_group, 2) # 비디오 영역을 더 넓게
        main_layout.addWidget(right_panel, 1)

    def _create_robot_control_widget(self, robot_id: int) -> QWidget:
        """ 각 로봇별 제어 UI 생성 """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 1. 연결 설정
        conn_group = QGroupBox("네트워크 및 상태")
        conn_layout = QFormLayout(conn_group)
        
        default_ip = "192.168.10.81" if robot_id == 1 else "192.168.10.82"
        default_port = "13301" if robot_id == 1 else "13302"
        
        ##default_rtsp_eo = "rtsp://192.168.10.81:3000/eo" if robot_id == 1 else "rtsp://192.168.10.82:4000/eo"
        ##default_rtsp_ir = "rtsp://192.168.10.81:4000/ir" if robot_id == 1 else "rtsp://192.168.10.82:4000/ir"
        
        le_ip = QLineEdit(default_ip)
        le_port = QLineEdit(default_port)
        btn_connect = QPushButton("연결")
        btn_connect.setCheckable(True)
        lbl_conn_status = QLabel("● 미연결")
        lbl_conn_status.setStyleSheet("color: red; font-weight: bold;") 
        ## rtsp 연결 주소값 QLabel
        ##self.le_rtsp_eo  = QLineEdit(default_rtsp_eo)
        ##self.le_rtsp_ir  = QLineEdit(default_rtsp_ir)      
         
        # [!] 수신 데이터 표시용 QLabel 추가
        lbl_motor_status = QLabel("Pan: --, Tilt: --")
        lbl_power_status = QLabel("EO: ?, IR: ?")
        
        conn_layout.addRow("서버 IP:", le_ip)
        conn_layout.addRow("포트:", le_port)
        conn_layout.addRow(lbl_conn_status, btn_connect)        
        conn_layout.addRow("전원 상태:", lbl_power_status) # [!] 추가
        conn_layout.addRow("모터 상태:", lbl_motor_status) # [!] 추가
        #conn_layout.addRow("EO 카메라 RTSP:", eo_rtsp) # [!] 추가
        #conn_layout.addRow("IR 카메라 RTSP:", ir_rtsp) # [!] 추가
        
        # 2. 추적 설정
        track_group = QGroupBox("추적")
        track_layout = QHBoxLayout(track_group)
        btn_track_mode = QPushButton("추적 영역 설정")
        btn_track_mode.setCheckable(True)
        btn_track_stop = QPushButton("추적 정지")
        lbl_track_status = QLabel("미추적")
        
        track_layout.addWidget(btn_track_mode)
        track_layout.addWidget(btn_track_stop)
        track_layout.addWidget(lbl_track_status)
        
        # [!] 3. EO 카메라 제어 (이미지 기반)
        eo_group = QGroupBox("EO 카메라")
        eo_layout = QGridLayout(eo_group) # QGridLayout으로 변경        
        btn_eo_zoom_in = QPushButton("Zoom In")
        btn_eo_zoom_out = QPushButton("Zoom Out")
        btn_eo_focus_near = QPushButton("Focus Near")
        btn_eo_focus_far = QPushButton("Focus Far")        
        eo_layout.addWidget(QLabel("줌(Zoom)"), 0, 0)
        eo_layout.addWidget(btn_eo_zoom_in, 0, 1)
        eo_layout.addWidget(btn_eo_zoom_out, 0, 2)
        eo_layout.addWidget(QLabel("초점(Focus)"), 1, 0)
        eo_layout.addWidget(btn_eo_focus_near, 1, 1)
        eo_layout.addWidget(btn_eo_focus_far, 1, 2)

        # [!] 4. IR 카메라 제어 (이미지 기반)
        ir_group = QGroupBox("IR 카메라")
        ir_layout = QHBoxLayout(ir_group) # IR은 버튼이 2개이므로 QHBoxLayout        
        btn_ir_zoom_in = QPushButton("Zoom In (x2)")
        btn_ir_zoom_out = QPushButton("Zoom Out (x1)")                
        ir_layout.addWidget(QLabel("줌(Zoom)"))
        ir_layout.addWidget(btn_ir_zoom_in)
        ir_layout.addWidget(btn_ir_zoom_out)
        
        # [!] 5. 모터 제어 속도 (UI 추가)
        camera_motor_speed_group = QGroupBox("모터 속도 (조이스틱)")
        camera_motor_speed_layout = QFormLayout(camera_motor_speed_group)        
        # UI에서 속도를 기입받는 Text Edit
        le_pan_speed = QLineEdit("15.0") # 15.0 deg/s
        le_tilt_speed = QLineEdit("10.0") # 10.0 deg/s        
        camera_motor_speed_layout.addRow("방위각 속도 (deg/s):", le_pan_speed)
        camera_motor_speed_layout.addRow("고각 속도 (deg/s):", le_tilt_speed)
        
        #layout added        
        layout.addWidget(conn_group)        
        layout.addWidget(track_group)
        layout.addWidget(eo_group)
        layout.addWidget(ir_group)
        layout.addWidget(camera_motor_speed_group) # [!] 카메라 모터 속도 UI 추가
        layout.addStretch()
        
        # 나중에 접근할 수 있도록 위젯들을 저장
         # (연결)
        setattr(self, f"le_ip_{robot_id}", le_ip)
        setattr(self, f"le_port_{robot_id}", le_port)
        setattr(self, f"btn_connect_{robot_id}", btn_connect)
        setattr(self, f"lbl_conn_status_{robot_id}", lbl_conn_status)
        setattr(self, f"lbl_power_status_{robot_id}", lbl_power_status) # [!] 저장
        # (추적)
        setattr(self, f"btn_track_mode_{robot_id}", btn_track_mode)
        setattr(self, f"btn_track_stop_{robot_id}", btn_track_stop)
        setattr(self, f"lbl_track_status_{robot_id}", lbl_track_status)
        # (EO 카메라)
        setattr(self, f"btn_eo_zoom_in_{robot_id}", btn_eo_zoom_in)
        setattr(self, f"btn_eo_zoom_out_{robot_id}", btn_eo_zoom_out)
        setattr(self, f"btn_eo_focus_near_{robot_id}", btn_eo_focus_near)
        setattr(self, f"btn_eo_focus_far_{robot_id}", btn_eo_focus_far)        
        #setattr(self, f"{robot_id}", eo_rtsp) 
        
        # (IR 카메라)
        setattr(self, f"btn_ir_zoom_in_{robot_id}", btn_ir_zoom_in)
        setattr(self, f"btn_ir_zoom_out_{robot_id}", btn_ir_zoom_out)        
        #setattr(self, f"{robot_id}", ir_rtsp) 
        
        # [!] 카메라 모터 속도 QLineEdit 저장
        setattr(self, f"le_pan_speed_{robot_id}", le_pan_speed)
        setattr(self, f"le_tilt_speed_{robot_id}", le_tilt_speed)
        setattr(self, f"lbl_motor_status_{robot_id}", lbl_motor_status) # [!] 저장
        return widget

    def _connect_signals(self):
        # 1. 1호기/2호기 연결 버튼
        self.btn_connect_1.clicked.connect(lambda: self.on_connect_clicked(1))
        self.btn_connect_2.clicked.connect(lambda: self.on_connect_clicked(2))

        # 2. 네트워크 스레드 -> GUI (2개 스레드 모두 연결)
        for thread in self.threads.values():
            thread.connection_status.connect(self.on_connection_status)
            thread.log_message.connect(self.log)
            thread.received_motor_info.connect(self.on_motor_info_update)
            thread.received_tracking_status.connect(self.on_tracking_status)
            thread.received_power_status.connect(self.on_power_status_update)
            thread.received_heartbeat.connect(self.on_heartbeat_received)

        # 3. 1호기/2호기 추적 버튼
        self.btn_track_mode_1.clicked.connect(
            lambda checked: self.on_track_mode_toggled(1, checked)
        )
        self.btn_track_mode_2.clicked.connect(
            lambda checked: self.on_track_mode_toggled(2, checked)
        )
        self.btn_track_stop_1.clicked.connect(lambda: self.on_track_stop(1))
        self.btn_track_stop_2.clicked.connect(lambda: self.on_track_stop(2))

        # 4. [!] 비디오 위젯의 '영역 선택 완료' 시그널 -> 슬롯 연결
        self.video_widget.tracking_box_selected.connect(self.on_tracking_box_sent)
        
        # 5. [!] 1호기/2호기 카메라 제어 버튼 연결 (루프 사용)
        for robot_id in [1, 2]:
            # --- EO 카메라 (Press/Release) ---
            # (Zoom In)
            getattr(self, f"btn_eo_zoom_in_{robot_id}").pressed.connect(
                lambda rid=robot_id: self.send_eo_command(rid, zoom_control=CameraZoomControl.ZOOM_IN)
            )
            getattr(self, f"btn_eo_zoom_in_{robot_id}").released.connect(
                lambda rid=robot_id: self.send_eo_command(rid, zoom_control=CameraZoomControl.STOP)
            )
            # (Zoom Out)
            getattr(self, f"btn_eo_zoom_out_{robot_id}").pressed.connect(
                lambda rid=robot_id: self.send_eo_command(rid, zoom_control=CameraZoomControl.ZOOM_OUT)
            )
            getattr(self, f"btn_eo_zoom_out_{robot_id}").released.connect(
                lambda rid=robot_id: self.send_eo_command(rid, zoom_control=CameraZoomControl.STOP)
            )
            # (Focus Near)
            getattr(self, f"btn_eo_focus_near_{robot_id}").pressed.connect(
                lambda rid=robot_id: self.send_eo_command(rid, focus_control=CameraFocusControl.NEAR)
            )
            getattr(self, f"btn_eo_focus_near_{robot_id}").released.connect(
                lambda rid=robot_id: self.send_eo_command(rid, focus_control=CameraFocusControl.STOP)
            )
            # (Focus Far)
            getattr(self, f"btn_eo_focus_far_{robot_id}").pressed.connect(
                lambda rid=robot_id: self.send_eo_command(rid, focus_control=CameraFocusControl.FAR)
            )
            getattr(self, f"btn_eo_focus_far_{robot_id}").released.connect(
                lambda rid=robot_id: self.send_eo_command(rid, focus_control=CameraFocusControl.STOP)
            )
            
            # --- IR 카메라 (Clicked - 이산 제어) ---
            # (IR Zoom In -> x2)
            getattr(self, f"btn_ir_zoom_in_{robot_id}").clicked.connect(
                lambda rid=robot_id: self.send_ir_command(rid, zoom_mode=IRCameraZoom.X2)
            )
            # (IR Zoom Out -> x1)
            getattr(self, f"btn_ir_zoom_out_{robot_id}").clicked.connect(
                lambda rid=robot_id: self.send_ir_command(rid, zoom_mode=IRCameraZoom.X1)
            )
        
        # [!] 6. 조이스틱 스레드 -> GUI (신규)
        self.joystick_thread.log_message.connect(self.log)
        self.joystick_thread.joystick_status.connect(
            lambda connected, name: 
            self.log(f"조이스틱: {name} {'연결됨' if connected else '연결 해제'}")
        )
        self.joystick_thread.gimbal_move.connect(self.on_joystick_gimbal_move)
        self.joystick_thread.gimbal_zoom_continuous.connect(self.on_joystick_zoom_continuous)
        self.joystick_thread.gimbal_zoom_digital.connect(self.on_joystick_zoom_digital)
        self.joystick_thread.gimbal_focus_auto.connect(self.on_joystick_focus_auto)
        self.joystick_thread.robot_move.connect(self.on_joystick_robot_move)
        self.joystick_thread.robot_estop.connect(self.on_joystick_robot_estop)
        
        # [!] 7. 영상 관련 시그널 연결
        self.btn_server_connect.clicked.connect(self.on_server_connect_clicked)
        self.btn_view_eo.clicked.connect(lambda: self.change_video_source("EO"))
        self.btn_view_ir.clicked.connect(lambda: self.change_video_source("IR"))
        self.btn_view_stop.clicked.connect(self.on_video_stop_clicked) # [!] 중지 버튼 시그널 연결

        self.video_thread.change_pixmap_signal.connect(self.update_video_frame)
        self.video_thread.connection_lost_signal.connect(self.on_video_connection_lost)

        self.image_sender.connection_signal.connect(self.on_server_connection_status)
        self.image_sender.log_signal.connect(self.log)
        self.image_sender.detection_result_signal.connect(self.on_detection_result)

        
    def closeEvent(self, event):
        self.log("프로그램 종료 중... 스레드 정리...")
        self.heartbeat_timer.stop()
        self.network_thread_1.stop()
        self.network_thread_2.stop()
        self.joystick_thread.stop() # [!] 조이스틱 스레드 종료
        self.video_thread.stop()  # [!] 영상 스레드 종료
        self.image_sender.disconnect() # [!] 서버 연결 해제
        event.accept()
        
    # --- 활성 로봇 ID (탭) 확인 헬퍼 ---
    def get_active_robot_id(self) -> int:
        """ 현재 선택된 탭의 로봇 ID (1 또는 2)를 반환 """
        # (control_panel은 _init_ui에서 생성했다고 가정)
        if hasattr(self, 'control_panel'):
            return self.control_panel.currentIndex() + 1
        return 1 # 기본값
        
    # --- 슬롯 (Slot) 메소드 ---
    
    @Slot(str)
    def log(self, message: str):
        self.log_edit.append(message)

    @Slot()
    def send_heartbeats(self):
        """ 1초마다 연결된 로봇에게 Heartbeat 전송 """
        payload = PacketProtocol.build_heartbeat_payload()
        for robot_id, thread in self.threads.items():
            if thread.isRunning() and thread._is_running: # (연결 상태 확인)
                thread.send_command(CommandType.CMD_HEARTBEAT,payload)
                #thread.send_command(GenericContentType.CMD_HEARTBEAT, payload)

    @Slot(int)
    def on_connect_clicked(self, robot_id: int):
        btn = getattr(self, f"btn_connect_{robot_id}")
        
        if btn.isChecked():
            ip = getattr(self, f"le_ip_{robot_id}").text()
            port = int(getattr(self, f"le_port_{robot_id}").text())
            self.threads[robot_id].connect_to_server(ip, port)
        else:
            self.threads[robot_id].stop()
            
    @Slot(int, bool)
    def on_connection_status(self, robot_id: int, connected: bool):
        lbl = getattr(self, f"lbl_conn_status_{robot_id}")
        btn = getattr(self, f"btn_connect_{robot_id}")
        
        if connected:
            lbl.setText("● 연결됨")
            lbl.setStyleSheet("color: green; font-weight: bold;")
            btn.setChecked(True)
            btn.setText("연결 해제")
        else:
            lbl.setText("● 미연결")
            lbl.setStyleSheet("color: red; font-weight: bold;")
            btn.setChecked(False)
            btn.setText("연결")
            
            # [!] 연결 해제 시 상태 라벨 초기화
            getattr(self, f"lbl_power_status_{robot_id}").setText("EO: ?, IR: ?")
            getattr(self, f"lbl_motor_status_{robot_id}").setText("Pan: --, Tilt: --")
            getattr(self, f"lbl_track_status_{robot_id}").setText("미추적")

    @Slot(int, bool)
    def on_track_mode_toggled(self, robot_id: int, checked: bool):
        """ '추적 영역 설정' 버튼 클릭 시 """
        if checked:
            # (RTSP 영상 소스를 해당 로봇의 영상으로 교체하는 로직 필요)
            # 예: self.video_widget.set_rtsp_source(robot_id)
            
            # 다른 로봇의 추적 설정 버튼은 비활성화
            other_id = 2 if robot_id == 1 else 1
            getattr(self, f"btn_track_mode_{other_id}").setChecked(False)
            
            # 비디오 위젯을 추적 모드로 변경
            self.video_widget.set_tracking_mode(True)
            # (현재 활성화된 로봇 ID 저장)
            setattr(self.video_widget, "active_robot_id", robot_id)
        else:
            # 버튼이 (스스로 또는 코드로) 풀렸을 때
            if self.video_widget.get_tracking_mode():
                self.video_widget.set_tracking_mode(False)

    @Slot(int)
    def on_track_stop(self, robot_id: int):
        """ '추적 정지' 버튼 클릭 시 """
        self.log(f"[로봇 {robot_id}] 추적 정지 명령 전송")
        
        # '정지' 명령 패킷 생성 (좌표는 0, 채널은 EO(1)로 임의 설정)
        payload = PacketProtocol.build_tracking_set_payload(
            x=0, y=0, width=0, height=0,
            channel=TrackingChannel.EO, # (혹은 현재 채널)
            command=TrackingCommand.STOP
        )
        self.threads[robot_id].send_command(CommandType.CMD_TRACKING_SET, payload)
        #self.threads[robot_id].send_command(GenericContentType.CMD_TRACKING_SET, payload)
        
    @Slot(QRect)
    def on_tracking_box_sent(self, original_rect: QRect):
        """
        [!] video_widget에서 마우스 드래그가 끝나면 호출됨
        original_rect는 원본 영상(1920x1080) 기준 좌표
        """
        # 어떤 로봇에 대해 추적을 시작했는지 ID를 가져옴
        robot_id = getattr(self.video_widget, "active_robot_id", 0)
        if robot_id not in self.threads:
            self.log("오류: 추적 대상 로봇이 지정되지 않았습니다.")
            return

        # '추적 설정' 버튼을 비활성화(off) 상태로 되돌림
        getattr(self, f"btn_track_mode_{robot_id}").setChecked(False)

        # (현재 영상이 EO/IR인지 판단하는 로직 필요)
        current_channel = TrackingChannel.EO # (임시)

        self.log(f"[로봇 {robot_id}] 추적 시작 명령 전송 "
                 f"({current_channel.name} / {original_rect.x()},{original_rect.y()})")

        # '시작' 명령 패킷 생성
        payload = PacketProtocol.build_tracking_set_payload(
            x=original_rect.x(),
            y=original_rect.y(),
            width=original_rect.width(),
            height=original_rect.height(),
            channel=current_channel,
            command=TrackingCommand.START
        )
        self.threads[robot_id].send_command(CommandType.CMD_TRACKING_SET,payload)
        #self.threads[robot_id].send_command(GenericContentType.CMD_TRACKING_SET, payload)

     # --- 카메라 제어용 슬롯 ---
   
    @Slot()
    def send_eo_command(self, robot_id, 
                        zoom_mode=CameraZoomMode.NO_OP, 
                        zoom_control=CameraZoomControl.NO_OP,
                        reserve3: int = 0, # [!] 수정: Field 3(reserve) 인수를 받도록 추가
                        digital_zoom=CameraDigitalZoom.NO_OP,
                        focus_mode=CameraFocusMode.CONTINUOUS,
                        focus_control=CameraFocusControl.AUTO):
        """
        EO 카메라 명령을 전송합니다.
        버튼 Press/Release에 대응하여 연속 제어(Continuous)를 기본으로 합니다.
          # [!] 기본값을 '연속 제어'가 아닌 '명령 없음'으로 변경
        """
        try:
            payload = PacketProtocol.build_eo_camera_control_payload(
                zoom_mode=zoom_mode,
                zoom_control=zoom_control,
                reserve3=reserve3, # [!] 수정: Field 3 전달
                digital_zoom=digital_zoom, # 디지털 줌은 이 버튼들과 연동되지 않음
                focus_mode=focus_mode,
                focus_control=focus_control
            )
            self.threads[robot_id].send_command(
                CommandType.CMD_EO_CAMERA_CONTROL,payload                
            )
            #GenericContentType.CMD_EO_CAMERA_CONTROL, payload
            
            # self.log(f"Send EO cmd {robot_id}: Z({zoom_control.name}) F({focus_control.name})")
        except Exception as e:
            self.log(f"EO 명령 전송 오류: {e}")

    @Slot()
    def send_ir_command(self, robot_id, zoom_mode=IRCameraZoom.NO_OP):
        """ IR 카메라 명령을 전송합니다. (이산 제어) """
        try:
            payload = PacketProtocol.build_ir_camera_control_payload(
                zoom_mode=zoom_mode
            )
            self.threads[robot_id].send_command(
                CommandType.CMD_IR_CAMERA_CONTROL,payload
                #GenericContentType.CMD_IR_CAMERA_CONTROL, payload
            )
            self.log(f"[로봇 {robot_id}] IR 줌 명령 전송: {zoom_mode.name}")
        except Exception as e:
            self.log(f"IR 명령 전송 오류: {e}")


    # --- 수신 슬롯 ---
    @Slot(int, dict)
    def on_motor_info_update(self, robot_id: int, info: dict):
        # (20hz) 1호기/2호기 상태창 업데이트        pass
        """ (10Hz) 모터 및 카메라 구동 정보 수신 """
        if "error" in info: return
        try:
            lbl = getattr(self, f"lbl_motor_status_{robot_id}")
            # (pan_angle, tilt_angle은 parse_motor_camera_info에서 deg*100이 변환된 값)
            pan = info.get('pan_angle', 0.0)
            tilt = info.get('tilt_angle', 0.0)
            lbl.setText(f"Pan: {pan:.2f}°, Tilt: {tilt:.2f}°")
        except AttributeError:
            pass # 위젯이 아직 없거나 삭제된 경우

    @Slot(int, dict)
    def on_tracking_status(self, robot_id: int, status: dict):
        """ (1Hz) 추적 상태 수신 """
        if "error" in status: return

        try:
            lbl = getattr(self, f"lbl_track_status_{robot_id}")
            channel_val = status.get('channel', 0)
            state_val = status.get('status', 0)
            
            channel = "EO" if channel_val == 1 else ("IR" if channel_val == 2 else "N/A")
            state = "추적 중" if state_val == 1 else "미추적"
            
            lbl.setText(f"{channel} / {state}")
            lbl.setStyleSheet("color: green;" if state_val == 1 else "color: gray;")
        except AttributeError:
            pass

        '''
        lbl = getattr(self, f"lbl_track_status_{robot_id}")
        channel = "EO" if status['channel'] == TrackingChannel.EO else "IR"
        state = "추적 중" if status['status'] == 1 else "미추적"
        lbl.setText(f"{channel} / {state}")
        '''
   
    @Slot(int, dict)
    def on_power_status_update(self, robot_id: int, info: dict):
        """ (1Hz) 카메라 전원 상태 수신 """
        if "error" in info: return
        try:
            lbl = getattr(self, f"lbl_power_status_{robot_id}")
            eo = "On" if info.get('eo_power', 0) == 1 else "Off"
            ir = "On" if info.get('ir_power', 0) == 1 else "Off"
            
            lbl.setText(f"EO: {eo}, IR: {ir}")
            lbl.setStyleSheet("color: green;" if eo == "On" else "color: red;")
        except AttributeError:
            pass
    
    @Slot(int)
    def on_heartbeat_received(self, robot_id: int, info: dict):
        # (1hz) lbl_conn_status를 잠시 깜빡이게 하는 등        pass
        if "error" in info: return
        try:
            lbl = getattr(self, f"lbl_power_status_{robot_id}")
            eo = "On" if info.get('eo_power', 0) == 1 else "Off"
            ir = "On" if info.get('ir_power', 0) == 1 else "Off"
            
            lbl.setText(f"EO: {eo}, IR: {ir}")
            lbl.setStyleSheet("color: green;" if eo == "On" else "color: red;")
        except AttributeError:
            pass


    # [!] --- 조이스틱 신규 슬롯 ---
    
    @Slot(int, int)
    def on_joystick_gimbal_move(self, pan: int, tilt: int):
        """ 조이스틱 HAT[0] (모터 구동) """
        if (pan, tilt) == self.current_gimbal_move:
            return # 중복 명령 무시
        self.current_gimbal_move = (pan, tilt)

        robot_id = self.get_active_robot_id()
        
        try:
            # 1. UI에서 속도 값 읽기 (요청 사항)
            pan_speed_dps = float(getattr(self, f"le_pan_speed_{robot_id}").text())
            tilt_speed_dps = float(getattr(self, f"le_tilt_speed_{robot_id}").text())
        except ValueError:
            pan_speed_dps = 10.0 # 기본값
            tilt_speed_dps = 10.0
        
        # 2. Pan(방위각) 제어
        pan_ctrl = MotorPanControl.STOP
        pan_val = 0.0
        if pan == -1:
            pan_ctrl = MotorPanControl.LEFT
            pan_val = pan_speed_dps
        elif pan == 1:
            pan_ctrl = MotorPanControl.RIGHT
            pan_val = pan_speed_dps
        elif pan == 0: #(pygame:stop =0)
            pan_ctrl = MotorPanControl.STOP
            pan_val = 0.0
            
        # 3. Tilt(고각) 제어
        tilt_ctrl = MotorTiltControl.STOP
        tilt_val = 0.0
        if tilt == 1: # (pygame: Up = 1)
            tilt_ctrl = MotorTiltControl.UP
            tilt_val = tilt_speed_dps
        elif tilt == -1: # (pygame: Down = -1)
            tilt_ctrl = MotorTiltControl.DOWN
            tilt_val = tilt_speed_dps
        elif tilt == 0: #(pygame:stop =0)
            tilt_ctrl = MotorTiltControl.STOP
            tilt_val = 0.0

        # 4. 패킷 생성 및 전송
        payload = PacketProtocol.build_motor_control_payload(
            mode=MotorMode.SPEED_CONTROL,
            pan_control=pan_ctrl,
            pan_speed_dps=pan_val,
            pan_position_deg=0.0,#NO_COMMAND_POS,
            tilt_control=tilt_ctrl,
            tilt_speed_dps=tilt_val,
            tilt_position_deg=0.0,#NO_COMMAND_POS
        )
        self.threads[robot_id].send_command(
            CommandType.CMD_MOTOR_CONTROL,payload
            #GenericContentType.CMD_MOTOR_CONTROL, payload
        )

    @Slot(int)
    def on_joystick_zoom_continuous(self, zoom_dir: int):
        """ 조이스틱 줌 (BTN[0], BTN[3]) """
        if zoom_dir == self.current_zoom_dir:
            return # 중복 명령 무시
        self.current_zoom_dir = zoom_dir
        robot_id = self.get_active_robot_id()
        
        zoom_ctrl = CameraZoomControl.STOP
        if zoom_dir == 1:
            zoom_ctrl = CameraZoomControl.ZOOM_IN
        elif zoom_dir == -1:
            zoom_ctrl = CameraZoomControl.ZOOM_OUT
        
        # (send_eo_command는 이전에 구현된 헬퍼 슬롯)
        # [!] 수정: reserve3=0xFFFF (hex) = 65535 (decimal)
        # 헥스 예시에 있던 0xFFFF 값을 전달
        #self.send_eo_command(robot_id, zoom_control=zoom_ctrl)
        self.send_eo_command(
            robot_id, 
            zoom_mode=CameraZoomMode.CONTINUOUS, 
            zoom_control=zoom_ctrl,
            reserve3=0xFFFF 
        )

    @Slot()
    def on_joystick_zoom_digital(self):
        """ 조이스틱 배율 조정 (BTN[3]) """
        robot_id = self.get_active_robot_id()
        #channel = self.current_channel[robot_id]
        channel = self.current_video_source
        
        if channel == "EO":
            self.log(f"[로봇 {robot_id}] EO 채널에서는 디지털 줌(BTN[2])이 지원되지 않습니다.")
            return # 여기서 함수 종료
            '''
            count = (self.eo_zoom_count[robot_id] % 5) + 1
            self.eo_zoom_count[robot_id] = count
            zoom_map = {1: CameraDigitalZoom.X1, 2: CameraDigitalZoom.X2, 3: CameraDigitalZoom.X4, 4: CameraDigitalZoom.X8, 5: CameraDigitalZoom.X12}
            d_zoom_cmd = zoom_map.get(count, CameraDigitalZoom.X1)
            
            # [!] 버그 수정: 디지털 줌(Field 4)을 보낼 때
            # 줌 모드(Field 1)를 'POSITION'(2)으로 설정
            self.send_eo_command(
                robot_id, 
                zoom_mode=CameraZoomMode.CONTINUOUS, # 
                digital_zoom=d_zoom_cmd,# [!] 디지털 줌 값                
                focus_mode=CameraFocusMode.NO_OP,
                focus_control=CameraFocusControl.NO_OP
            )
            self.log(f"[로봇 {robot_id}] EO 배율 변경: {d_zoom_cmd.name}")
            '''

        elif channel == "IR": # 'elif'로 변경
            count = (self.ir_zoom_count[robot_id] % 3) + 1
            self.ir_zoom_count[robot_id] = count
            zoom_map = {1: IRCameraZoom.X1, 2: IRCameraZoom.X2, 3: IRCameraZoom.X4}
            d_zoom_cmd = zoom_map.get(count, IRCameraZoom.X1)
            
            # IR 카메라는 패킷 구조가 다르므로 send_ir_command 사용
            self.send_ir_command(robot_id, zoom_mode=d_zoom_cmd)
            self.log(f"[로봇 {robot_id}] IR 배율 변경: {d_zoom_cmd.name}")
        else:
            self.log("배율 변경 실패: 영상 소스가 선택되지 않았습니다 (N/A).")
        
        '''
        if channel == "EO":
            count = self.eo_zoom_count[robot_id] + 1
            if count > 5: count = 1 # 1~5 순환
            self.eo_zoom_count[robot_id] = count
            
            # 1:x1, 2:x2, 3:x4, 4:x8, 5:x12
            zoom_map = {
                1: CameraDigitalZoom.X1, 2: CameraDigitalZoom.X2,
                3: CameraDigitalZoom.X4, 4: CameraDigitalZoom.X8,
                5: CameraDigitalZoom.X12
            }
            d_zoom_cmd = zoom_map.get(count, CameraDigitalZoom.X1)
            self.send_eo_command(robot_id, digital_zoom=d_zoom_cmd)
            self.log(f"[로봇 {robot_id}] EO 배율 변경: {d_zoom_cmd.name}")

        else: # "IR"
            count = self.ir_zoom_count[robot_id] + 1
            if count > 3: count = 1 # 1~3 순환
            self.ir_zoom_count[robot_id] = count
            
            # 1:x1, 2:x2, 3:x4
            zoom_map = {
                1: IRCameraZoom.X1, 2: IRCameraZoom.X2, 3: IRCameraZoom.X4
            }
            d_zoom_cmd = zoom_map.get(count, IRCameraZoom.X1)
            self.send_ir_command(robot_id, zoom_mode=d_zoom_cmd)
            self.log(f"[로봇 {robot_id}] IR 배율 변경: {d_zoom_cmd.name}")
        '''
        
    @Slot()
    def on_joystick_focus_auto(self):
        """ 조이스틱 자동 초점 (BTN[4]) """
        robot_id = self.get_active_robot_id()
        self.log(f"[로봇 {robot_id}] 자동 초점(AF) 명령")
        # (send_eo_command는 이전에 구현된 헬퍼 슬롯)
        # (packet_protocol에 AUTO = 4 추가 필요)
        # [!] 수정: 'focus_mode'와 'focus_control'을 명시적으로 지정
        self.send_eo_command(robot_id,
                             focus_mode=CameraFocusMode.CONTINUOUS, 
                             focus_control=CameraFocusControl.AUTO)
        #self.send_eo_command(robot_id, focus_control=CameraFocusControl.AUTO)

    @Slot(float, float)
    def on_joystick_robot_move(self, steering: float, throttle: float):
        """ 조이스틱 로봇(차량) 주행 (AXIS[0], AXIS[1]) """
        robot_id = self.get_active_robot_id()
        
        # (프로토콜 정의가 없으므로 로깅만)
        # (요청 사항: 6553600 * 조이스틱 값)
        enc_steering = 6553600 * steering
        
        # (throttle은 -1.0 ~ 1.0)
        self.log(f"[로봇 {robot_id}] 주행: 조향={enc_steering:.0f}, 속도={throttle*100.0:.1f}%")
        
        # TODO: 로봇 주행용 패킷 생성 및 전송
        # payload = PacketProtocol.build_robot_drive_payload(enc_steering, throttle)
        # self.threads[robot_id].send_command(GenericContentType.CMD_ROBOT_DRIVE, payload)

    @Slot()
    def on_joystick_robot_estop(self):
        """ 조이스틱 비상 정지 (BTN[1]) """
        robot_id = self.get_active_robot_id()
        self.log(f"🚨 [로봇 {robot_id}] 비상 정지 (E-STOP) 🚨")
        
        # (모터 정지 명령으로 비상 정지 구현)
        payload = PacketProtocol.build_motor_control_payload(
            mode=MotorMode.SPEED_CONTROL,
            pan_control=MotorPanControl.STOP,
            pan_speed_dps=0.0,
            pan_position_deg=0, #NO_COMMAND_POS
            tilt_control=MotorTiltControl.STOP,
            tilt_speed_dps=0.0,
            tilt_position_deg=0,#NO_COMMAND_POS
        )
        self.threads[robot_id].send_command(
            CommandType.CMD_MOTOR_CONTROL,payload
            #GenericContentType.CMD_MOTOR_CONTROL, payload
        )
 
    # [!] --- 신규 영상/서버 관련 슬롯 ---
    @Slot(bool)
    def on_server_connect_clicked(self, checked):
        if checked:
            ip = self.le_server_ip.text()
            try:
                port = int(self.le_server_port.text())
                self.image_sender.connect_to_server(ip, port)
            except ValueError:
                self.log("잘못된 포트 번호입니다.")
                self.btn_server_connect.setChecked(False)
        else:
            self.image_sender.disconnect()

    @Slot(bool)
    def on_server_connection_status(self, connected):
        self.btn_server_connect.setChecked(connected)
        self.btn_server_connect.setText("서버 연결 해제" if connected else "서버 연결")
        # 현재 실행 중인 비디오 스레드 중지 후 재시작
        if self.video_thread.isRunning():
            self.video_thread.stop()
          
    @Slot(str)
    def change_video_source(self, source):
        """ EO/IR 영상 소스 변경 """
        self.current_video_source = source
        self.lbl_video_source.setText(f"현재 소스: {source}")        
        self.lbl_video_source.setStyleSheet(f"color: {'blue' if source == 'EO' else 'orange'}; font-weight: bold;")
        
        # 현재 활성 로봇의 채널 정보도 업데이트
        try:
            active_robot_id = self.get_active_robot_id()
            self.current_channel[active_robot_id] = source
        except Exception as e:
            self.log(f"활성 로봇 채널 업데이트 실패: {e}")
            
        # 현재 실행 중인 비디오 스레드 중지 후 재시작
        if self.video_thread.isRunning():
            self.video_thread.stop()
            
        url = self.le_rtsp_eo.text() if source == "EO" else self.le_rtsp_ir.text()
        self.video_thread.set_url(url)
        self.video_thread.start()
        self.log(f"영상 소스 변경: {source} ({url})")

    @Slot(np.ndarray)
    def update_video_frame(self, frame_cv):
        """ VideoThread로부터 받은 프레임을 UI에 표시하고 서버로 전송 """
        # 1. 표적 처리 서버로 전송
        self.image_sender.send_frame(frame_cv)
        
        # 2. UI 표시를 위해 QPixmap 변환
        rgb_frame = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        # 3. 위젯에 표시
        self.video_widget.set_pixmap(pixmap)

    @Slot()
    def on_video_stop_clicked(self):
        """ [!] 영상 중지 버튼 """
        self.log("RTSP 영상 수신을 수동으로 중지합니다.")
        if self.video_thread.isRunning():
            self.video_thread.stop()
     
        self.video_widget.set_pixmap(self.dummy_pixmap)
        self.video_widget.update()
        
        self.lbl_video_source.setText("소스: N/A")
        self.lbl_video_source.setStyleSheet("color: gray; font-weight: bold;")
        self.current_video_source = "N/A" # 현재 소스 상태 초기화
        
    @Slot()
    def on_video_connection_lost(self):
        #self.log("RTSP 영상 연결이 끊어졌습니다.")
        self.log(f"RTSP 영상 연결이 끊어졌습니다: {self.current_video_source}")
        self.lbl_video_source.setText(f"{self.current_video_source} 연결 실패")
        self.lbl_video_source.setStyleSheet("color: red; font-weight: bold;")
        self.video_widget.set_pixmap(self.dummy_pixmap) # [!] 연결 실패 시 검은 화면
        self.current_video_source = "N/A" # 상태 초기화

    @Slot(dict)
    def on_detection_result(self, result):
        """ 표적 처리 서버로부터 받은 결과 처리 """       
        try:
            msg = f"[{result.get('timestamp', '?')}] {len(result.get('detections', []))} objects detected"
            self.detect_list.addItem(msg)
            self.detect_list.scrollToBottom()
            # (결과를 video_widget으로 전달하여 바운딩 박스 그리기)
            # self.video_widget.set_detections(result.get('detections', []))
        except Exception as e:
            self.log(f"Detection 결과 처리 오류: {e}")
        
# --- 실행 ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())