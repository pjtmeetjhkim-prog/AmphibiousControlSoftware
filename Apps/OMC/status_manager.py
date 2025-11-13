"""
filename: status_manager.py
author: gbox3d

시스템 상태 관리 및 업데이트
"""
from random import randint
from PySide6.QtCore import QObject, QTimer, Slot, QDateTime
from PySide6.QtGui import QPixmap
from utils.my_qt_utils import limit_plaintext_lines

class StatusManager(QObject):
    """시스템 상태 관리 및 업데이트 담당"""
    
    def __init__(self):
        super().__init__()
        self.system_begin_time = QDateTime.currentDateTime()
        self.clock_timer = None
        self.status_timer = None
    
    def initialize_timers(self, clock_callback, status_callback):
        """
        타이머 초기화
        
        Args:
            clock_callback: 시계 업데이트 콜백
            status_callback: 상태 업데이트 콜백
        """
        # 시계 업데이트 타이머 (1초마다)
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(clock_callback)
        self.clock_timer.start(1000)
        
        # # 상태 업데이트 타이머 (10초마다)
        # self.status_timer = QTimer()
        # self.status_timer.timeout.connect(status_callback)
        # self.status_timer.start(10000)
        
        # # 즉시 업데이트
        # clock_callback()
        # status_callback()
    
    def get_current_time_string(self):
        """현재 시간 문자열 반환"""
        current_time = QDateTime.currentDateTime()
        return current_time.toString("yyyy-MM-dd hh:mm:ss")
    
    def get_elapsed_time_string(self):
        """시스템 시작 후 경과 시간 문자열 반환"""
        current_time = QDateTime.currentDateTime()
        elapsed_time = self.system_begin_time.secsTo(current_time)
        hours = elapsed_time // 3600
        minutes = (elapsed_time % 3600) // 60
        seconds = elapsed_time % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def update_clock_widgets(self, time_label, operation_time_label):
        """
        시계 위젯 업데이트
        
        Args:
            time_label: 현재 시간 표시 레이블
            operation_time_label: 운영 시간 표시 레이블
        """
        time_label.setText(self.get_current_time_string())
        operation_time_label.setText(self.get_elapsed_time_string())
    
    def update_status_widgets(self, wifi_label, network_label, battery_label,
                             area_label, weather_label, temp_label, rain_label,
                             windy_label, humidity_label, precip_label, wave_label,
                             log_widget):
        """
        상태 위젯 업데이트 (WiFi, 네트워크, 배터리, 날씨 등)
        
        Args:
            wifi_label: WiFi 상태 레이블
            network_label: 네트워크 상태 레이블
            battery_label: 배터리 상태 레이블
            area_label: 지역명 레이블
            weather_label: 날씨 레이블
            temp_label: 온도 레이블
            rain_label: 강수량 레이블
            windy_label: 풍속 레이블
            humidity_label: 습도 레이블
            precip_label: 강수확률 레이블
            wave_label: 파고 레이블
            log_widget: 로그 텍스트 위젯
        """
        # 연결 상태 업데이트 (랜덤)
        wifi_status = randint(1, 4)
        wifi_label.setPixmap(QPixmap(f":/와이파이{wifi_status}.png"))
        
        network_status = randint(1, 5)
        network_label.setPixmap(QPixmap(f":/네트워크{network_status}.png"))
        
        battery_status = randint(1, 5)
        battery_label.setPixmap(QPixmap(f":/배터리{battery_status}.png"))
        
        # 날씨 정보 업데이트 (랜덤)
        area_label.setText("전주시 경원동")
        weather_label.setText("맑음 또는 흐림 그리고 비 또는 눈")
        
        temperature = randint(-10, 40)
        rain_size = randint(0, 100)
        windy = randint(0, 100)
        humidity = randint(0, 100)
        precipitation = randint(0, 100)
        wave_height = randint(0, 100)
        
        temp_label.setText(f"기온: {temperature}℃")
        rain_label.setText(f"강수량: {rain_size}mm")
        windy_label.setText(f"풍속: {windy}m/s")
        humidity_label.setText(f"습도: {humidity}%")
        precip_label.setText(f"강수확률: {precipitation}%")
        wave_label.setText(f"파고: {wave_height}m")
        
        # 로그 추가
        current_time = QDateTime.currentDateTime()
        log_msg = (f"{current_time.toString('yyyy-MM-dd hh:mm:ss')} - "
                  f"기온: {temperature}℃, 강수량: {rain_size}mm, "
                  f"풍속: {windy}m/s, 습도: {humidity}%, "
                  f"강수확률: {precipitation}%, 파고: {wave_height}m")
        log_widget.appendPlainText(log_msg)
        limit_plaintext_lines(log_widget, 10)
    
    def cleanup(self):
        """리소스 정리"""
        if self.clock_timer:
            self.clock_timer.stop()
        if self.status_timer:
            self.status_timer.stop()
