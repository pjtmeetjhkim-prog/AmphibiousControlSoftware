import sys
from PySide6.QtWidgets import QApplication ,QWidget
from PySide6.QtCore import Signal

from configMng import ConfigManager

import UI.reference.setupForm

class setupForm(QWidget,UI.reference.setupForm.Ui_SetupForm):
    
    closedSignal = Signal()
    backSignal = Signal()
    
    
    
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setupUi(self)
        
        self.configMng = ConfigManager()
        self.configMng.load_config()
        
        self.textEditCar1ip.setText(self.configMng.get_car_ip(0))
        self.textEditCar1port.setText(str(self.configMng.get_car_port(0)))        
        self.textEditCar1Camurl_rgb.setText(self.configMng.get_car_cam_url(0))
        self.textEditCar1Camurl_IR.setText(self.configMng.get_car_cam_url_ir(0))
        self.cbUnit_1_Enable.setChecked(self.configMng.get_unit_enable(0))
        
        self.textEditCar2ip.setText(self.configMng.get_car_ip(1))
        self.textEditCar2port.setText(str(self.configMng.get_car_port(1)))
        self.textEditCar2Camurl_rgb.setText(self.configMng.get_car_cam_url(1))
        self.textEditCar2Camurl_IR.setText(self.configMng.get_car_cam_url_ir(1))
        self.cbUnit_2_Enable.setChecked(self.configMng.get_unit_enable(1))

        self.textEditCar3ip.setText(self.configMng.get_car_ip(2))
        self.textEditCar3port.setText(str(self.configMng.get_car_port(2)))
        self.textEditCar3Camurl_rgb.setText(self.configMng.get_car_cam_url(2))
        self.textEditCar3Camurl_IR.setText(self.configMng.get_car_cam_url_ir(2))    
        self.cbUnit_3_Enable.setChecked(self.configMng.get_unit_enable(2))

        self.lineEdit_detecter_ip.setText(self.configMng.get_detection_server_ip())
        self.lineEdit_detecter_port.setText(str(self.configMng.get_detection_server_port()))
        self.cbEnableImgDetection.setChecked(self.configMng.get_detection_server_enable())        
        
        self.btnBack.clicked.connect(self.onClick_btnBack)
        self.pushButton_saveSetup.clicked.connect(self.onClick_btnSaveSetup)

        self.lineEditSelectUnitIndex.setText( str( self.configMng.get_current_select_unit()) )
        self.lineEditSelectUnitIndex_Sub.setText( str( self.configMng.get_current_select_unit_sub()) )

        self.checkBox_fullScreen.setChecked(self.configMng.is_fullscreen())
        
    def onClick_btnBack(self):
        print("onClick_btnBack")
        # self.closedSignal.emit()
        self.backSignal.emit()
        
    def closeEvent(self, event):
        print("closeEvent")
        self.closedSignal.emit()
        super().closeEvent(event)
    
    def onClick_btnSaveSetup(self):
        
        print("onClick_btnSaveSetup")
        
        self.configMng.set_car_ip(self.textEditCar1ip.text(),car_idx=0)
        self.configMng.set_car_port(self.textEditCar1port.text(),car_idx=0)
        self.configMng.set_car_cam_url(self.textEditCar1Camurl_rgb.text(),car_idx=0)
        self.configMng.set_car_cam_url_ir(self.textEditCar1Camurl_IR.text(),car_idx=0)
        
        self.configMng.set_car_ip(self.textEditCar2ip.text(),1)
        self.configMng.set_car_port(self.textEditCar2port.text(),1)
        self.configMng.set_car_cam_url(self.textEditCar2Camurl_rgb.text(),1)
        self.configMng.set_car_cam_url_ir(self.textEditCar2Camurl_IR.text(),1)
        
        self.configMng.set_car_ip(self.textEditCar3ip.text(),2)
        self.configMng.set_car_port(self.textEditCar3port.text(),2)
        self.configMng.set_car_cam_url(self.textEditCar3Camurl_rgb.text(),2)
        self.configMng.set_car_cam_url_ir(self.textEditCar3Camurl_IR.text(),2)

        
        self.configMng.set_detection_server_ip(self.lineEdit_detecter_ip.text())
        self.configMng.set_detection_server_port(self.lineEdit_detecter_port.text())
        self.configMng.set_detection_server_enable(self.cbEnableImgDetection.isChecked())

        self.configMng.set_unit_enable(self.cbUnit_1_Enable.isChecked(), 0)
        self.configMng.set_unit_enable(self.cbUnit_2_Enable.isChecked(), 1)
        self.configMng.set_unit_enable(self.cbUnit_3_Enable.isChecked(), 2)

        self.configMng.set_current_select_unit(int(self.lineEditSelectUnitIndex.text()))
        self.configMng.set_current_select_unit_sub(int(self.lineEditSelectUnitIndex_Sub.text()))

        self.configMng.set_fullscreen(self.checkBox_fullScreen.isChecked())
        
        # 설정 파일 저장
        self.configMng.save_config()
        
        print("설정 저장 완료")
        
        # self.closedSignal.emit()
        self.backSignal.emit()  # 설정 저장 후 뒤로가기 신호 발생
        
if __name__ == '__main__':
    
    theApp = QApplication(sys.argv)
    form = setupForm()
    form.show()
    sys.exit(theApp.exec())
    
    