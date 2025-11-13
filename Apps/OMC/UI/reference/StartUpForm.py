# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'StartUpForm.ui'
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
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

import UI.reference.icons_rc

class Ui_StartUpForm(object):
    def setupUi(self, StartUpForm):
        if not StartUpForm.objectName():
            StartUpForm.setObjectName(u"StartUpForm")
        StartUpForm.resize(767, 630)
        self.verticalLayout = QVBoxLayout(StartUpForm)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalSpacer_3 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_3)

        self.label = QLabel(StartUpForm)
        self.label.setObjectName(u"label")
        self.label.setMinimumSize(QSize(0, 15))
        font = QFont()
        font.setFamilies([u"DungGeunMo"])
        font.setPointSize(24)
        self.label.setFont(font)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout.addWidget(self.label)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_2)

        self.widgetBtnBar = QWidget(StartUpForm)
        self.widgetBtnBar.setObjectName(u"widgetBtnBar")
        self.widgetBtnBar.setMinimumSize(QSize(0, 128))
        self.horizontalLayout = QHBoxLayout(self.widgetBtnBar)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.btnStart = QPushButton(self.widgetBtnBar)
        self.btnStart.setObjectName(u"btnStart")
        self.btnStart.setMinimumSize(QSize(96, 96))
        font1 = QFont()
        font1.setFamilies([u"D2Coding"])
        self.btnStart.setFont(font1)

        self.horizontalLayout.addWidget(self.btnStart)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_2)

        self.btnSetup = QPushButton(self.widgetBtnBar)
        self.btnSetup.setObjectName(u"btnSetup")
        self.btnSetup.setMinimumSize(QSize(96, 96))
        self.btnSetup.setFont(font1)

        self.horizontalLayout.addWidget(self.btnSetup)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_3)

        self.btnExit = QPushButton(self.widgetBtnBar)
        self.btnExit.setObjectName(u"btnExit")
        self.btnExit.setMinimumSize(QSize(96, 96))
        self.btnExit.setFont(font1)

        self.horizontalLayout.addWidget(self.btnExit)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_4)


        self.verticalLayout.addWidget(self.widgetBtnBar)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)


        self.retranslateUi(StartUpForm)

        QMetaObject.connectSlotsByName(StartUpForm)
    # setupUi

    def retranslateUi(self, StartUpForm):
        StartUpForm.setWindowTitle(QCoreApplication.translate("StartUpForm", u"Form", None))
        self.label.setText(QCoreApplication.translate("StartUpForm", u"\uc6b4\uc6a9\ud1b5\uc81c\uc2dc\uc2a4\ud15c", None))
        self.btnStart.setText(QCoreApplication.translate("StartUpForm", u"\uc2dc\uc791", None))
        self.btnSetup.setText(QCoreApplication.translate("StartUpForm", u"\uc124\uc815", None))
        self.btnExit.setText(QCoreApplication.translate("StartUpForm", u"\uc885\ub8cc", None))
    # retranslateUi

