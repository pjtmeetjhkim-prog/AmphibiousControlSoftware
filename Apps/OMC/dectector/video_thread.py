"""
filename: video_thread.py
author: gbox3d

비디오 스트림 처리를 위한 스레드 클래스
"""
import os
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal


class VideoThread(QThread):
    """RTSP 비디오 스트림을 처리하는 스레드"""
    change_pixmap_signal = Signal(np.ndarray)

    def __init__(self, rtsp_url):
        super().__init__()
        self.rtsp_url = rtsp_url
        self._run_flag = True
        self._cap = None

    def run(self):
        """스레드 실행 메서드"""
        # RTSP가 종료 시 블로킹되지 않도록 타임아웃/버퍼 최소화
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS",
                              "rtsp_transport;tcp|stimeout;2000000")  # 2초
        self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        try:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            print("VideoThread: CAP_PROP_BUFFERSIZE 설정 실패, FFMPEG 버전이 낮을 수 있습니다.")
        
        print(f"VideoThread: RTSP URL: {self.rtsp_url}")
        
        while self._run_flag:
            if not self._cap.isOpened():
                self.msleep(50)
                continue
            ret, cv_img = self._cap.read()
            if not ret:
                self.msleep(10)
                continue
            self.change_pixmap_signal.emit(cv_img)
            
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def stop(self):
        """스레드 정지"""
        self._run_flag = False
        self.wait()
