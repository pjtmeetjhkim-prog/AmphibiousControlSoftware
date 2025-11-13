
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QTextCursor


def match_widget_to_parent(widget):
    """
    주어진 위젯을 부모 위젯의 크기에 맞춥니다.
    :param widget: 부모 크기에 맞출 위젯
    """
    parent_widget = widget.parentWidget()  # 부모 위젯 얻기
    if parent_widget is not None:
        parent_width = parent_widget.width()
        parent_height = parent_widget.height()
        widget.setGeometry(0, 0, parent_width, parent_height)  # 부모 크기에 맞게 설정
        

def limit_plaintext_lines(plain_text_edit, max_lines):
    """
    QPlainTextEdit에서 최대 라인 수를 초과하면 오래된 라인을 삭제하고 커서를 맨 아래로 이동합니다.
    :param plain_text_edit: QPlainTextEdit 객체
    :param max_lines: 최대 허용 라인 수
    """
    while plain_text_edit.blockCount() > max_lines:
        cursor = plain_text_edit.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.select(QTextCursor.BlockUnderCursor)
        cursor.removeSelectedText()
        cursor.deleteChar()
        plain_text_edit.setTextCursor(cursor)
    
    # 커서를 맨 아래로 이동
    plain_text_edit.moveCursor(QTextCursor.End)
    