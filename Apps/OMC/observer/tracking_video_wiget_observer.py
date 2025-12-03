from PySide6.QtWidgets import QLabel, QApplication
from PySide6.QtCore import Signal, QRect, QPoint, Qt
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap

class TrackingVideoWidget(QLabel):
    """
    RTSP 영상(QPixmap)을 표시하며,
    마우스 드래그로 추적 영역을 선택할 수 있는 위젯.
    """
    # 마우스 릴리즈 시, 선택된 영역(QRect)을 방출(emit)
    tracking_box_selected = Signal(QRect)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True) # 마우스 움직임 감지
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("No Video Feed") # 기본 텍스트
        
        self._tracking_enabled = False # '추적 설정' 버튼으로 활성화
        self._is_dragging = False
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        
        self.current_pixmap = None # 현재 비디오 프레임

    def set_pixmap(self, pixmap: QPixmap):
        """ 외부(RTSP 스레드)에서 비디오 프레임을 업데이트할 때 호출 """
        self.current_pixmap = pixmap
        # 위젯 크기에 맞게 스케일링하여 표시 (원본 좌표 유지를 위해)
        scaled_pixmap = pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        super().setPixmap(scaled_pixmap)

    def set_tracking_mode(self, enabled: bool):
        """ '추적 설정' 버튼 클릭 시 호출 """
        self._tracking_enabled = enabled
        if self._tracking_enabled:
            self.setCursor(Qt.CursorShape.CrossCursor) # 십자 커서
            self.setToolTip("추적할 영역을 드래그하세요.")
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip("")
            self._is_dragging = False
            self.start_pos = QPoint()
            self.end_pos = QPoint()
            self.update() # 화면 갱신 (그려진 사각형 지우기)

    def get_tracking_mode(self) -> bool:
        return self._tracking_enabled

    def _get_scaled_rect(self) -> QRect:
        """ 현재 드래그 중인 영역을 QRect로 반환 """
        return QRect(self.start_pos, self.end_pos).normalized()

    # --- Qt Mouse Events ---

    def mousePressEvent(self, event):
        if self._tracking_enabled and event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.position().toPoint()
            self.end_pos = self.start_pos
            self._is_dragging = True
            event.accept()

    def mouseMoveEvent(self, event):
        if self._tracking_enabled and self._is_dragging:
            self.end_pos = event.position().toPoint()
            self.update() # paintEvent() 강제 호출
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._tracking_enabled and self._is_dragging and event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            
            # [!] 최종 선택된 영역(화면 좌표)
            screen_rect = self._get_scaled_rect()
            
            # [!!] 원본 영상 좌표로 변환 (중요)
            original_rect = self.map_rect_to_pixmap(screen_rect)
            
            if original_rect.width() > 10 and original_rect.height() > 10:
                # 너무 작은 박스는 무시
                self.tracking_box_selected.emit(original_rect)
            
            # 모드 자동 해제
            self.set_tracking_mode(False)
            event.accept()

    def paintEvent(self, event):
        """ 위젯을 다시 그릴 때 호출됨 (비디오 프레임 + 추적 상자) """
        # 1. 부모(QLabel)의 paintEvent 호출 (비디오 프레임 그리기)
        super().paintEvent(event)
        
        # 2. 추적 모드이고 드래그 중일 때, 상자 그리기
        if self._tracking_enabled and self._is_dragging:
            painter = QPainter(self)
            rect = self._get_scaled_rect()
            
            # 반투명 녹색
            pen = QPen(QColor(0, 255, 0, 200), 2, Qt.PenStyle.SolidLine)
            brush = QBrush(QColor(0, 255, 0, 80)) 
            
            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawRect(rect)
            
            # (W x H) 텍스트 표시
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(rect.bottomLeft(), f" {rect.width()} x {rect.height()}")

    def map_rect_to_pixmap(self, screen_rect: QRect) -> QRect:
        """
        화면에 그려진 QRect를 원본 Pixmap (예: 1920x1080) 좌표로 변환합니다.
        (RTSP 영상이 위젯 크기에 맞게 스케일링 되었기 때문)
        """
        if self.current_pixmap is None or self.current_pixmap.isNull():
            return QRect() # 비디오 없음
            
        widget_size = self.size()
        pixmap_size = self.current_pixmap.size()
        
        if widget_size.width() == 0 or widget_size.height() == 0:
            return QRect()
            
        # KeepAspectRatio 비율 계산
        scale_w = pixmap_size.width() / widget_size.width()
        scale_h = pixmap_size.height() / widget_size.height()
        
        # 레터박스/필러박스 계산
        if (pixmap_size.width() / widget_size.width()) > (pixmap_size.height() / widget_size.height()):
            # 레터박스 (위아래 검은 바)
            scale = scale_w
            offset_x = 0
            offset_y = (widget_size.height() - (pixmap_size.height() / scale)) / 2
        else:
            # 필러박스 (좌우 검은 바)
            scale = scale_h
            offset_x = (widget_size.width() - (pixmap_size.width() / scale)) / 2
            offset_y = 0
            
        # 화면 좌표 -> 원본 영상 좌표
        orig_x = (screen_rect.x() - offset_x) * scale
        orig_y = (screen_rect.y() - offset_y) * scale
        orig_w = screen_rect.width() * scale
        orig_h = screen_rect.height() * scale

        # 원본 영상 범위(0~Width, 0~Height) 내로 클리핑
        orig_x = max(0, min(orig_x, pixmap_size.width()))
        orig_y = max(0, min(orig_y, pixmap_size.height()))
        orig_w = max(0, min(orig_w, pixmap_size.width() - orig_x))
        orig_h = max(0, min(orig_h, pixmap_size.height() - orig_y))
        
        return QRect(int(orig_x), int(orig_y), int(orig_w), int(orig_h))