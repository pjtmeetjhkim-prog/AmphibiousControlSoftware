from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

import UI.reference.videoFrame

class VideoDialog(QDialog,UI.reference.videoFrame.Ui_Dialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        
        self.setWindowTitle("확대된 비디오")
        self.setGeometry(0, 0, 1920, 1080)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)  # 프레임 없는 창 설정
        
        # 레이아웃 설정
        self.layout = QVBoxLayout()
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)  # 이미지가 중앙에 배치되도록 설정
        self.layout.addWidget(self.video_label)
        self.setLayout(self.layout)
        
        # btnZoomOut 버튼 위치 설정 (우하단 기준으로 100, 100)
        self.widgetBtnZoomOut.setParent(self)
        self.widgetBtnZoomOut.setGeometry(self.width() - 100 - self.btnZoomOut.width(), self.height() - 100 - self.btnZoomOut.height(), 128, 128)
        # self.btnZoomOut.setStyleSheet("background-color:transparent;")
        
        self.btnZoomOut.clicked.connect(self.close)
        
        # video_label을 뒤로 보내고, btnZoomOut 버튼을 앞으로 보냄
        self.video_label.lower()  # video_label을 뒤로 보냄
        self.widgetBtnZoomOut.raise_()  # btnZoomOut 버튼을 앞으로 보냄
    

    def update_video_frame(self, pixmap: QPixmap):
        """
        비디오 프레임을 업데이트합니다.
        :param pixmap: QPixmap 형태의 비디오 프레임
        """
        # self.video_label.setPixmap(pixmap)
        scaled_pixmap = pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled_pixmap)

        
