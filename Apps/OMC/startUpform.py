import sys
from PySide6.QtWidgets import QApplication ,QWidget ,QLabel
# from PySide6.QtCore import Signal

from UI.reference import StartUpForm

class setupForm(QWidget,StartUpForm.Ui_StartUpForm):
    
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setupUi(self)
        
         # 버전 정보 추가 - 좌상단에 작은 글씨로 표시
        self.version_label = QLabel(self)
        self.version_label.setText("v1.1.0 [OMC-PC]")  # 원하는 버전 번호로 변경하세요
        self.version_label.setGeometry(10, 10, 120, 20)  # 좌상단 위치 (x, y, 너비, 높이)
        
        # 작은 글씨로 표시
        font = self.version_label.font()
        font.setPointSize(8)  # 폰트 크기 설정
        self.version_label.setFont(font)
        
        # 반투명 효과 (선택 사항)
        self.version_label.setStyleSheet("color: rgba(0, 0, 0, 180);")
        
        self.btnStart.clicked.connect(self.gotoMain)
        self.btnSetup.clicked.connect(self.gotoSetup)
        self.btnExit.clicked.connect(self.gotoExit)
        
    
    def gotoMain(self):
        print("gotoMain")
    
    def gotoSetup(self):
        print("gotoSetup")
    
    def gotoExit(self):
        print("gotoExit")
    
        

if __name__ == '__main__':
    
    theApp = QApplication(sys.argv)
    form = setupForm()
    form.show()
    sys.exit(theApp.exec())
    
    