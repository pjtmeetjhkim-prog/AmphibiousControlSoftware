import socket
import struct
import json
import numpy as np
import cv2
import threading
from PySide6.QtCore import QObject, Signal, Slot

class ImageSender(QObject):
    """
    표적 처리 서버로 이미지를 전송하고 결과를 수신하는 클래스
    """
    detection_result_signal = Signal(dict) # 탐지 결과 전달
    log_signal = Signal(str)
    connection_signal = Signal(bool)

    def __init__(self):
        super().__init__()
        self.server_ip = ""
        self.server_port = 0
        self.sock = None
        self._is_running = False
        self._send_thread = None
        self._recv_thread = None
        self._latest_frame = None
        self._lock = threading.Lock()

    def connect_to_server(self, ip, port):
        self.server_ip = ip
        self.server_port = port
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.server_ip, self.server_port))
            self.sock.settimeout(None) # 블로킹 모드로 변경
            self._is_running = True
            
            # 수신 스레드 시작
            self._recv_thread = threading.Thread(target=self._receive_worker, daemon=True)
            self._recv_thread.start()
            
            self.connection_signal.emit(True)
            self.log_signal.emit(f"표적 처리 서버 연결 성공: {ip}:{port}")
        except Exception as e:
            self.log_signal.emit(f"서버 연결 실패: {e}")
            self.connection_signal.emit(False)

    def disconnect(self):
        self._is_running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
        self.connection_signal.emit(False)
        self.log_signal.emit("서버 연결 해제됨")

    def send_frame(self, frame: np.ndarray):
        """ 최신 프레임을 저장 (실제 전송은 별도 워커가 처리하거나 직접 호출) """
        if not self._is_running or self.sock is None:
            return
            
        # 너무 빈번한 호출 방지를 위해 바로 전송
        # (성능 문제 시 별도 스레드로 분리 가능)
        try:
            # JPEG 인코딩
            _, img_encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            data = img_encoded.tobytes()
            size = len(data)
            
            # 헤더(4바이트 길이) + 데이터 전송
            self.sock.sendall(struct.pack('>L', size) + data)
            
        except Exception as e:
            self.log_signal.emit(f"이미지 전송 실패: {e}")
            self.disconnect()

    def _receive_worker(self):
        """ 서버로부터 탐지 결과를 수신하는 워커 """
        while self._is_running and self.sock:
            try:
                # 1. 헤더(길이) 수신
                header = self._recv_exact(4)
                if not header: break
                data_len = struct.unpack('>L', header)[0]
                
                # 2. 데이터(JSON) 수신
                json_data = self._recv_exact(data_len)
                if not json_data: break
                
                # 3. 파싱 및 시그널 전달
                result = json.loads(json_data.decode('utf-8'))
                self.detection_result_signal.emit(result)
                
            except (socket.error, json.JSONDecodeError, struct.error) as e:
                self.log_signal.emit(f"데이터 수신 오류: {e}")
                break
                
        self.disconnect()

    def _recv_exact(self, n):
        """ 정확히 n 바이트를 수신하는 헬퍼 함수 """
        data = b''
        while len(data) < n:
            packet = self.sock.recv(n - len(data))
            if not packet: return None
            data += packet
        return data