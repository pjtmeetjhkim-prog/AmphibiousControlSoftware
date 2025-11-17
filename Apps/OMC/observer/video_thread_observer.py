import os
import cv2
import numpy as np
import time
import threading
from queue import Queue, Empty
from PySide6.QtCore import QThread, Signal

# 환경 변수 설정 (TCP 전송 강제, 지연 시간 최소화)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay"

class VideoThread(QThread):
    """
    RTSP 비디오 스트림을 처리하는 스레드 (개선된 버전)
    - 별도의 스레드에서 프레임을 계속 읽어 큐에 최신 프레임만 유지
    """
    change_pixmap_signal = Signal(np.ndarray)
    connection_lost_signal = Signal() # 연결 끊김 신호

    def __init__(self, rtsp_url=""):
        super().__init__()
        self.rtsp_url = rtsp_url
        self._run_flag = False
        self._cap = None
        self._frame_queue = Queue(maxsize=1) # 최신 1장만 유지
        self._reader_thread = None

    def set_url(self, url):
        self.rtsp_url = url

    def _reader_worker(self):
        """ OpenCV VideoCapture로 프레임을 계속 읽는 백그라운드 워커 """
        print(f"Video Reader started for {self.rtsp_url}")
        while self._run_flag:
            if self._cap is None or not self._cap.isOpened():
                 # 재연결 시도
                 time.sleep(1)
                 continue

            ret, frame = self._cap.read()
            if not ret:
                print("Video Reader: Frame read failed")
                # 연결이 끊긴 것으로 간주
                with self._frame_queue.mutex:
                    self._frame_queue.queue.clear()
                time.sleep(1) # 재연결 대기
                continue
                
            # 큐가 꽉 찼으면 오래된 프레임 비우기 (최신성 유지)
            if not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except Empty:
                    pass
            
            self._frame_queue.put(frame)
        
        print("Video Reader stopped")

    def run(self):
        self._run_flag = True
        
        # 1. 캡처 객체 초기화
        self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        if not self._cap.isOpened():
            print(f"Failed to open RTSP: {self.rtsp_url}")
            self.connection_lost_signal.emit()
            return

        # 2. 프레임 읽기 스레드 시작
        self._reader_thread = threading.Thread(target=self._reader_worker, daemon=True)
        self._reader_thread.start()

        # 3. 메인 루프: 큐에서 프레임을 꺼내 UI로 전달
        while self._run_flag:
            try:
                # 30ms 정도 대기하며 프레임 가져오기 (약 30fps)
                frame = self._frame_queue.get(timeout=0.1)
                self.change_pixmap_signal.emit(frame)
            except Empty:
                # 프레임이 안 들어오면 연결 상태 확인
                if self._cap is None or not self._cap.isOpened():
                     self.connection_lost_signal.emit()
                     break
                continue
            except Exception as e:
                print(f"VideoThread Error: {e}")
                break

        # 정리
        if self._cap:
            self._cap.release()
        self._cap = None

    def stop(self):
        """ 스레드 종료 """
        self._run_flag = False
        if self._reader_thread and self._reader_thread.is_alive():
             self._reader_thread.join(timeout=1.0)
        self.wait()