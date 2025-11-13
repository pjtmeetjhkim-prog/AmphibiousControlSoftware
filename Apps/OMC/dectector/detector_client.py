"""
author: gbox3d
date: 2025-05-27
description: 객체 감지 클라이언트 모듈

이 주석은 수정하지 마세요.
version: 1.0.0
"""

import socket
import struct
import json
import numpy as np
import cv2
import threading
import time
from PySide6.QtCore import QObject, Signal, QThread
from typing import Optional, List, Dict, Any

class DetectionClient:
    
    def __init__(self, host='localhost', port=8085):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.detection_thread = None
        self.pending_frames = []  # 대기 중인 프레임들
        self.max_pending_frames = 3  # 최대 대기 프레임 수
        self.processing = False
        
        # 콜백 함수들 (시그널 대신 사용)
        self.on_detection_results = None  # callback(detections, image)
        self.on_status_update = None      # callback(message)
        self.on_connection_status = None  # callback(connected)
        
    def connect_to_server(self) -> bool:
        """서버에 연결"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            if self.on_connection_status:
                self.on_connection_status(True)
            if self.on_status_update:
                self.on_status_update(f"서버 연결 성공: {self.host}:{self.port}")
            return True
        except Exception as e:
            self.connected = False
            if self.on_connection_status:
                self.on_connection_status(False)
            if self.on_status_update:
                self.on_status_update(f"서버 연결 실패: {e}")
            return False
    
    def disconnect_from_server(self):
        """연결 종료"""
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        if self.on_connection_status:
            self.on_connection_status(False)
        if self.on_status_update:
            self.on_status_update(" 서버 연결 종료")
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.connected and self.socket is not None
    
    def detect_objects_async(self, image: np.ndarray):
        """비동기로 객체 감지 요청"""
        if not self.is_connected():
            if not self.connect_to_server():
                return
        
        # 대기 중인 프레임이 너무 많으면 오래된 것 제거
        if len(self.pending_frames) >= self.max_pending_frames:
            self.pending_frames.pop(0)
        
        # 현재 프레임을 대기 목록에 추가
        self.pending_frames.append(image.copy())
        
        # 처리 중이 아니면 새로운 쓰레드 시작
        if not self.processing:
            self.detection_thread = threading.Thread(target=self._process_detection_queue)
            self.detection_thread.daemon = True
            self.detection_thread.start()
    
    def _process_detection_queue(self):
        """감지 큐 처리 (별도 쓰레드에서 실행)"""
        self.processing = True
        
        while self.pending_frames and self.is_connected():
            try:
                # 가장 최신 프레임 가져기
                image = self.pending_frames.pop()
                # 나머지 오래된 프레임들 제거 (최신 것만 처리)
                self.pending_frames.clear()
                
                # 감지 수행
                detections = self._detect_objects_sync(image)
                
                if detections is not None:
                    # 결과를 콜백으로 전달
                    if self.on_detection_results:
                        self.on_detection_results(detections, image)
                
            except Exception as e:
                if self.on_status_update:
                    self.on_status_update(f"감지 처리 중 오류: {e}")
                self.disconnect_from_server()
                break
        
        self.processing = False
    
    def _detect_objects_sync(self, image: np.ndarray) -> Optional[List[Dict[str, Any]]]:
        """동기적으로 객체 감지 수행"""
        try:
            # 이미지 전송
            if not self._send_image(image):
                return None
            
            # 결과 수신
            response = self._receive_response()
            
            if response and 'detections' in response:
                return response['detections']
            else:
                return []
                
        except Exception as e:
            if self.on_status_update:
                self.on_status_update(f"감지 요청 실패: {e}")
            return None
    
    def _send_image(self, image: np.ndarray) -> bool:
        """이미지를 서버로 전송"""
        try:
            if image.dtype != np.uint8:
                image = image.astype(np.uint8)
            
            height, width, channels = image.shape
            data = image.tobytes()
            data_len = len(data)
            dtype_str = str(image.dtype)
            dtype_bytes = dtype_str.encode('utf-8').ljust(10, b'\x00')
            
            # 헤더 패킹 (26 bytes)
            header = struct.pack("<L3I10s", data_len, height, width, channels, dtype_bytes)
            
            # 헤더 + 데이터 전송
            self.socket.sendall(header + data)
            return True
            
        except Exception as e:
            if self.on_status_update:
                self.on_status_update(f"이미지 전송 실패: {e}")
            return False
    
    def _receive_response(self) -> Optional[Dict[str, Any]]:
        """서버 응답 수신"""
        try:
            # 메시지 크기 수신 (4 bytes)
            size_data = self.socket.recv(4)
            if not size_data:
                return None
            
            message_size = struct.unpack("<L", size_data)[0]
            
            # JSON 데이터 수신
            json_data = b''
            while len(json_data) < message_size:
                chunk = self.socket.recv(message_size - len(json_data))
                if not chunk:
                    return None
                json_data += chunk
            
            # JSON 파싱
            response = json.loads(json_data.decode('utf-8'))
            return response
            
        except Exception as e:
            if self.on_status_update:
                self.on_status_update(f"응답 수신 실패: {e}")
            return None

class DetectionThread(QThread):
    """감지를 위한 전용 쓰레드"""
    
    detection_results = Signal(list, np.ndarray)  # 감지 결과, 원본 이미지
    status_update = Signal(str)
    
    def __init__(self, host='localhost', port=8085):
        super().__init__()
        self.host = host
        self.port = port
        self.client = None
        self.running = False
        
    def start_detection(self):
        """감지 시작"""
        self.running = True
        self.start()
    
    def stop_detection(self):
        """감지 중지"""
        self.running = False
        if self.client:
            self.client.disconnect_from_server()
        self.quit()
        self.wait()
    
    def run(self):
        """쓰레드 메인 루프"""
        # 쓰레드 내에서 클라이언트 생성
        self.client = DetectionClient(self.host, self.port)
        
        # 콜백 함수 설정 (시그널 발생)
        self.client.on_detection_results = self._on_detection_results
        self.client.on_status_update = self._on_status_update
        self.client.on_connection_status = self._on_connection_status
        
        # 연결 시도
        if not self.client.connect_to_server():
            return
        
        # 쓰레드 유지 (실제 작업은 다른 메서드에서 수행)
        while self.running:
            self.msleep(100)
        
        self.client.disconnect_from_server()
    
    def _on_detection_results(self, detections, image):
        """감지 결과 콜백 - 시그널 발생"""
        self.detection_results.emit(detections, image)
    
    def _on_status_update(self, message):
        """상태 업데이트 콜백 - 시그널 발생"""
        self.status_update.emit(message)
    
    def _on_connection_status(self, connected):
        """연결 상태 콜백"""
        # 필요하면 추가 처리
        pass
    
    def detect_objects(self, image: np.ndarray):
        """객체 감지 요청"""
        if self.client and self.running:
            self.client.detect_objects_async(image)

def draw_detections(image: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
    """감지 결과를 이미지에 그리기"""
    if not detections:
        return image
    
    result_image = image.copy()
    
    for detection in detections:
        # 바운딩 박스 좌표
        box = detection['box']
        x1, y1, x2, y2 = map(int, box)
        
        # 클래스 이름과 신뢰도
        name = detection['name']
        confidence = detection['confidence']
        
        # 바운딩 박스 그리기 (초록색)
        cv2.rectangle(result_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # 레이블 텍스트
        label = f"{name}: {confidence:.2f}"
        
        # 텍스트 크기 계산
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        
        # 텍스트 배경 그리기
        cv2.rectangle(result_image, (x1, y1 - text_height - 10), 
                     (x1 + text_width, y1), (0, 255, 0), -1)
        
        # 텍스트 그리기
        cv2.putText(result_image, label, (x1, y1 - 5), 
                   font, font_scale, (0, 0, 0), thickness)
    
    return result_image