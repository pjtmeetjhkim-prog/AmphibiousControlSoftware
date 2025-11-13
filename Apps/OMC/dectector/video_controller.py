"""
filename: video_controller.py
author: gbox3d

비디오 스트림 및 감지 기능을 관리하는 컨트롤러
"""
import cv2
import numpy as np
from PySide6.QtCore import QObject, Slot, Qt
from PySide6.QtGui import QImage, QPixmap, QFont

from dectector.video_thread import VideoThread
from dectector.videoFrame import VideoDialog
from dectector.detector_client import DetectionThread, draw_detections
from utils.my_qt_utils import limit_plaintext_lines

class VideoController(QObject):
    """비디오 스트림과 감지 기능을 관리하는 컨트롤러"""
    
    def __init__(self, config_manager, current_unit_index, current_unit_index_sub, font_d2coding):
        super().__init__()
        self.configMng = config_manager
        self.current_unit_index = current_unit_index
        self.current_unit_index_sub = current_unit_index_sub
        self.font_d2coding = font_d2coding
        
        # 비디오 관련 변수
        self.mainCameraThread = None
        self.subCameraThread = None
        self.video_dialog = None
        
        # YOLO 감지 관련 변수
        self.yolo_detection_thread = None
        self.current_detections = []
        self.detection_overlay_enabled = False
        
    def initialize_main_camera(self, main_label, main_screen):
        """메인 카메라 초기화"""
        if not self.configMng.get_unit_enable(self.current_unit_index):
            main_label.setText(f"선택된 {self.current_unit_index+1}호기가 비활성 상태입니다.")
            main_label.setAlignment(Qt.AlignCenter)
            main_label.setFont(QFont(self.font_d2coding, 24, 75))
            return False
        
        # 초기 준비 메시지
        main_label.setText("영상 준비 중...")
        main_label.setAlignment(Qt.AlignCenter)
        main_label.setFont(QFont(self.font_d2coding, 24, 75))
        
        # RTSP 스트림 설정
        rtsp_url = self.configMng.get_car_cam_url(car_idx=self.current_unit_index)
        print(f"Main RTSP URL: {rtsp_url}")
        
        # 메인 카메라 비디오 스레드 생성 및 시작
        self.mainCameraThread = VideoThread(rtsp_url)
        self.mainCameraThread.start()
        
        # VideoDialog 미리 생성
        self.video_dialog = VideoDialog()
        
        return True
    
    def initialize_sub_camera(self, sub_label):
        """서브 카메라 초기화"""
        if not self.configMng.get_unit_enable(self.current_unit_index_sub):
            sub_label.setText(f"선택된 {self.current_unit_index_sub+1}호기가 비활성 상태입니다.")
            sub_label.setAlignment(Qt.AlignCenter)
            return False
        
        sub_label.setText("영상 준비 중")
        sub_label.setAlignment(Qt.AlignCenter)
        
        rtsp_url_sub = self.configMng.get_car_cam_url(car_idx=self.current_unit_index_sub)
        print(f"Sub RTSP URL: {rtsp_url_sub}")
        
        # 서브 카메라 비디오 스레드 생성 및 시작
        self.subCameraThread = VideoThread(rtsp_url_sub)
        self.subCameraThread.start()
        
        return True
    
    def initialize_detection(self, log_widget):
        """이미지 감지 서버 초기화"""
        if not self.configMng.get_detection_server_enable():
            return False
        
        det_ip = self.configMng.get_detection_server_ip()
        det_port = self.configMng.get_detection_server_port()
        
        # YOLO 감지 스레드 생성
        self.yolo_detection_thread = DetectionThread(host=det_ip, port=det_port)
        self.yolo_detection_thread.start_detection()
        
        self.detection_overlay_enabled = True
        log_widget.appendPlainText(f"감지 서버 연결: {det_ip}:{det_port}")
        
        return True
    
    @Slot(np.ndarray)
    def update_main_image(self, cv_img, main_label, main_screen):
        """메인 카메라 이미지 업데이트 (YOLO 감지 포함)"""
        # YOLO 감지 요청 (논블로킹)
        if self.yolo_detection_thread:
            self.yolo_detection_thread.detect_objects(cv_img)
        
        # 현재 감지 결과가 있으면 이미지에 그리기
        display_image = cv_img.copy()
        if self.detection_overlay_enabled and self.current_detections:
            display_image = draw_detections(display_image, self.current_detections)
        
        # Qt 형식으로 변환하여 화면에 표시
        rgb_image = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = qt_image.scaled(main_screen.size(), Qt.KeepAspectRatio)
        main_label.setPixmap(QPixmap.fromImage(pixmap))
        
        # VideoDialog에도 전달
        if self.video_dialog and self.video_dialog.isVisible():
            self.video_dialog.update_video_frame(QPixmap.fromImage(pixmap))
    
    @Slot(np.ndarray)
    def update_sub_image(self, cv_img, sub_label):
        """서브 카메라 이미지 업데이트"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = qt_image.scaled(sub_label.size(), Qt.KeepAspectRatio)
        sub_label.setPixmap(QPixmap.fromImage(pixmap))
    
    @Slot(list, np.ndarray)
    def on_detection_results(self, detections, original_image, log_widget):
        """YOLO 감지 결과 처리"""
        self.current_detections = detections
        
        # 감지 결과 로그
        if detections:
            detection_summary = ", ".join([f"{d['name']}({d['confidence']:.2f})" for d in detections[:3]])
            if len(detections) > 3:
                detection_summary += f" 외 {len(detections)-3}개"
            log_msg = f"[detector] 감지: {detection_summary}"
        else:
            log_msg = "[detector] 객체 감지되지 않음"
            
        log_widget.appendPlainText(log_msg)
        limit_plaintext_lines(log_widget, 10)
    
    @Slot(str)
    def on_detection_status(self, msg, log_widget):
        """YOLO 상태 메시지 처리"""
        log_widget.appendPlainText(f"[Detector] {msg}")
        limit_plaintext_lines(log_widget, 10)
    
    def toggle_detection_overlay(self, enabled: bool):
        """감지 결과 오버레이 표시 토글"""
        self.detection_overlay_enabled = enabled
    
    def clear_detections(self):
        """현재 감지 결과 초기화"""
        self.current_detections = []
    
    def show_video_dialog(self):
        """비디오 다이얼로그 표시"""
        if self.video_dialog and not self.video_dialog.isVisible():
            self.video_dialog.show()
    
    def cleanup(self):
        """리소스 정리"""
        if self.mainCameraThread:
            self.mainCameraThread.stop()
        if self.subCameraThread:
            self.subCameraThread.stop()
        if self.yolo_detection_thread:
            self.yolo_detection_thread.stop_detection()
