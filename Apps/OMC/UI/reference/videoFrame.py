# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'videoFrame.ui'
##
## Created by: Qt User Interface Compiler version 6.9.3
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QDialog, QLabel, QPushButton,
    QSizePolicy, QWidget)
#import UI.reference.icons_rc

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(640, 480)
        self.widgetBtnZoomOut = QWidget(Dialog)
        self.widgetBtnZoomOut.setObjectName(u"widgetBtnZoomOut")
        self.widgetBtnZoomOut.setGeometry(QRect(440, 280, 128, 128))
        self.btnZoomOut = QPushButton(self.widgetBtnZoomOut)
        self.btnZoomOut.setObjectName(u"btnZoomOut")
        self.btnZoomOut.setGeometry(QRect(0, 0, 128, 128))
        self.btnZoomOut.setStyleSheet(u"background-color:transparent;")
        self.label = QLabel(self.widgetBtnZoomOut)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(0, 0, 128, 128))
        self.label.setPixmap(QPixmap(u":/\ucd95\uc18c.png"))
        self.label.setScaledContents(True)
        self.label.raise_()
        self.btnZoomOut.raise_()

        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.btnZoomOut.setText("")
        self.label.setText("")
    # retranslateUi

