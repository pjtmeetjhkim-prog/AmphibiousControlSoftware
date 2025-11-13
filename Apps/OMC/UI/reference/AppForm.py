# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'AppForm.ui'
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
from PySide6.QtWidgets import (QApplication, QGridLayout, QSizePolicy, QStackedWidget,
    QWidget)

class Ui_AppForm(object):
    def setupUi(self, AppForm):
        if not AppForm.objectName():
            AppForm.setObjectName(u"AppForm")
        AppForm.resize(640, 480)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(AppForm.sizePolicy().hasHeightForWidth())
        AppForm.setSizePolicy(sizePolicy)
        self.gridLayout = QGridLayout(AppForm)
        self.gridLayout.setObjectName(u"gridLayout")
        self.stackedWidget = QStackedWidget(AppForm)
        self.stackedWidget.setObjectName(u"stackedWidget")
        self.page = QWidget()
        self.page.setObjectName(u"page")
        self.stackedWidget.addWidget(self.page)
        self.page_2 = QWidget()
        self.page_2.setObjectName(u"page_2")
        self.stackedWidget.addWidget(self.page_2)

        self.gridLayout.addWidget(self.stackedWidget, 0, 0, 1, 1)


        self.retranslateUi(AppForm)

        QMetaObject.connectSlotsByName(AppForm)
    # setupUi

    def retranslateUi(self, AppForm):
        AppForm.setWindowTitle(QCoreApplication.translate("AppForm", u"Form", None))
    # retranslateUi

