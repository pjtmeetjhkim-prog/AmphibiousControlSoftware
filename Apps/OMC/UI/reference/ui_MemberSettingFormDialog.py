# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'MemberSettingFormDialog.ui'
##
## Created by: Qt User Interface Compiler version 6.7.2
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
    QSizePolicy, QTextEdit, QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(375, 165)
        self.btnMemberInsert = QPushButton(Dialog)
        self.btnMemberInsert.setObjectName(u"btnMemberInsert")
        self.btnMemberInsert.setGeometry(QRect(280, 40, 79, 24))
        self.txtJobLank = QTextEdit(Dialog)
        self.txtJobLank.setObjectName(u"txtJobLank")
        self.txtJobLank.setGeometry(QRect(90, 20, 161, 31))
        self.label = QLabel(Dialog)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(10, 20, 71, 31))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txtMemberName = QTextEdit(Dialog)
        self.txtMemberName.setObjectName(u"txtMemberName")
        self.txtMemberName.setGeometry(QRect(90, 70, 161, 31))
        self.label_2 = QLabel(Dialog)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(10, 70, 71, 31))
        self.label_2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txtMemberContact = QTextEdit(Dialog)
        self.txtMemberContact.setObjectName(u"txtMemberContact")
        self.txtMemberContact.setGeometry(QRect(90, 120, 161, 31))
        self.label_3 = QLabel(Dialog)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setGeometry(QRect(10, 120, 71, 31))
        self.label_3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btnMemberDelete = QPushButton(Dialog)
        self.btnMemberDelete.setObjectName(u"btnMemberDelete")
        self.btnMemberDelete.setGeometry(QRect(280, 90, 79, 24))

        self.retranslateUi(Dialog)

        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.btnMemberInsert.setText(QCoreApplication.translate("Dialog", u"\ub4f1\ub85d", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"\uc9c1\ud568", None))
        self.label_2.setText(QCoreApplication.translate("Dialog", u"\uc131\ud568", None))
        self.label_3.setText(QCoreApplication.translate("Dialog", u"\uc5f0\ub77d\ucc98", None))
        self.btnMemberDelete.setText(QCoreApplication.translate("Dialog", u"\uc0ad\uc81c", None))
    # retranslateUi

