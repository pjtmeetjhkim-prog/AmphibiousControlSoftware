import os
import cv2
import numpy as np
import time
import threading
from queue import Queue, Empty
from PySide6.QtCore import QThread, Signal

# 환경 변수 설정 (TCP 전송 강제, 지연 시간 최소화)
#os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|strict;experimental"

class VideoThread(QThread):
    """
    RTSP 비디오 스트림을 처리하는 스레드 (Expert Modified)
    - Producer(Reader Thread) -> Queue(Max=1) -> Consumer(GUI Thread) 구조 적용
    - 패킷 손실 및 디코딩 에러에 강한 구조
    """
    change_pixmap_signal = Signal(np.ndarray)
    connection_lost_signal = Signal() # 연결 끊김 신호

    def __init__(self, rtsp_url=""):
        super().__init__()
        self.rtsp_url = rtsp_url
        self._run_flag = False
        self._cap = None

        # 디코딩 속도가 표시 속도보다 빠를 때 오래된 프레임을 즉시 폐기하기 위함
        self._frame_queue = Queue(maxsize=1) 
        self._reader_thread = None
        self._lock = threading.Lock()

    def set_url(self, url):
        self.rtsp_url = url

    def _reader_worker(self):
        """ OpenCV VideoCapture로 프레임을 계속 읽는 백그라운드 워커 """
        print(f"Video Reader started for {self.rtsp_url}")
        while self._run_flag:
            if self._cap is None or not self._cap.isOpened():
                 # 재연결 시도
                 time.sleep(0.1)
                 continue
            
            try:
                ret, frame = self._cap.read()
                
                if not ret:
                     print("[VideoThread] Frame read failed (Packet loss or Stream ended)")                     
                     # 연결이 끊긴 것으로 간주
                     ##with self._frame_queue.mutex:
                     ##self._frame_queue.queue.clear()
                     time.sleep(0.1) # 재연결 대기
                     continue                
                # 큐가 꽉 찼으면 오래된 프레임 비우기 (최신성 유지)
                if not self._frame_queue.empty():
                    try:
                        self._frame_queue.get_nowait()
                    except Empty:
                        pass
                self._frame_queue.put(frame)

            except cv2.error as e:
                print(f"[VideoThread] FFmpeg decoding error: {e}")
                time.sleep(0.1)
            except Exception as e:
                print(f"[VideoThread] Unexpected error: {e}")
                time.sleep(0.1)                    
        print("Video Reader stopped")

    def run(self):
        """ 메인 QThread 루프: 큐에서 데이터를 꺼내 GUI로 전달 """
        self._run_flag = True
        
        # 1. RTSP 연결 시도
        self._connect_rtsp()

        # 2. 프레임 리더(Producer) 스레드 시작
        self._reader_thread = threading.Thread(target=self._reader_worker, daemon=True)
        self._reader_thread.start()

        # 3. 컨슈머(Consumer) 루프
        while self._run_flag:
            try:
                # 큐에서 프레임 가져오기 (타임아웃 설정으로 GUI 프리징 방지)
                frame = self._frame_queue.get(timeout=0.5)
                
                # 정상 프레임이면 시그널 전송
                if frame is not None and frame.size > 0:
                    self.change_pixmap_signal.emit(frame)
                    
            except Empty:
                # 프레임이 오랫동안 안 들어옴 -> 연결 상태 확인
                if self._run_flag and (self._cap is None or not self._cap.isOpened()):
                     print("[VideoThread] Connection lost detected in Consumer loop")
                     self.connection_lost_signal.emit()
                     # 자동 재연결을 원하면 여기서 _connect_rtsp() 호출 가능
                     # 여기서는 연결 끊김 신호만 보내고 대기
                     time.sleep(1)
                continue
            except Exception as e:
                print(f"[VideoThread] Consumer Error: {e}")

        # 종료 처리
        self._release_cap()

    def _connect_rtsp(self):
        """ RTSP 연결 초기화 함수 """
        self._release_cap()
        
        if not self.rtsp_url or self.rtsp_url == "N/A":
            return

        print(f"[VideoThread] Connecting to RTSP: {self.rtsp_url}")
        try:
            # API Preference를 CAP_FFMPEG로 명시
            self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            
            # 버퍼 사이즈 설정 (백엔드에 따라 동작하지 않을 수 있으나 시도)
            # self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not self._cap.isOpened():
                print(f"[VideoThread] Failed to open RTSP: {self.rtsp_url}")
                self.connection_lost_signal.emit()
            else:
                print("[VideoThread] RTSP Opened Successfully")
                
        except Exception as e:
            print(f"[VideoThread] Connection Exception: {e}")

    def _release_cap(self):
        if self._cap:
            self._cap.release()
            self._cap = None

    def stop(self):
        """ 스레드 안전 종료 """
        self._run_flag = False
        
        # 리더 스레드 종료 대기
        if self._reader_thread and self._reader_thread.is_alive():
             self._reader_thread.join(timeout=1.0)
        
        self._release_cap()
        self.wait()

    # def run(self):
    #     self._run_flag = True
        
    #     # 1. 캡처 객체 초기화
    #     self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
    #     if not self._cap.isOpened():
    #         print(f"Failed to open RTSP: {self.rtsp_url}")
    #         self.connection_lost_signal.emit()
    #         return

    #     # 2. 프레임 읽기 스레드 시작
    #     self._reader_thread = threading.Thread(target=self._reader_worker, daemon=True)
    #     self._reader_thread.start()

    #     # 3. 메인 루프: 큐에서 프레임을 꺼내 UI로 전달
    #     while self._run_flag:
    #         try:
    #             # 30ms 정도 대기하며 프레임 가져오기 (약 30fps)
    #             frame = self._frame_queue.get(timeout=0.1)
    #             self.change_pixmap_signal.emit(frame)
    #         except Empty:
    #             # 프레임이 안 들어오면 연결 상태 확인
    #             if self._cap is None or not self._cap.isOpened():
    #                  self.connection_lost_signal.emit()
    #                  break
    #             continue
    #         except Exception as e:
    #             print(f"VideoThread Error: {e}")
    #             break

    #     # 정리
    #     if self._cap:
    #         self._cap.release()
    #     self._cap = None

    # def stop(self):
    #     """ 스레드 종료 """
    #     self._run_flag = False
    #     if self._reader_thread and self._reader_thread.is_alive():
    #          self._reader_thread.join(timeout=1.0)
    #     self.wait()