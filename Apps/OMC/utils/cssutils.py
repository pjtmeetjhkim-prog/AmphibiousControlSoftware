import re
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QTextCursor

def change_background_color(obj: QWidget, color: str):
    """
    객체의 기존 스타일 시트에서 배경색을 변경합니다.
    :param obj: 스타일을 변경할 PySide 위젯 객체
    :param color: 변경할 배경색 (예: '#FF0000')
    """
    # 기존 스타일 시트 가져오기
    existing_style = obj.styleSheet()
    
    # 기존 스타일 시트에서 'background-color' 속성을 제거
    cleaned_style = re.sub(r"background-color:\s*[^;]*;?", "", existing_style)
    
    # 새로운 배경색 추가
    new_style = f"background-color: {color};"
    
    # 기존 스타일에 새로운 배경색 스타일 추가
    cleaned_style = cleaned_style.strip()
    if cleaned_style and not cleaned_style.endswith(";"):
        cleaned_style += ";"
    obj.setStyleSheet(cleaned_style + (" " if cleaned_style else "") + new_style)

def change_text_color(obj: QWidget, color: str):
    """
    객체의 기존 스타일 시트에서 텍스트 색상을 변경합니다.
    :param obj: 스타일을 변경할 PySide 위젯 객체
    :param color: 변경할 텍스트 색상 (예: '#FF0000')
    """
    # 기존 스타일 시트 가져오기
    existing_style = obj.styleSheet()
    
    # 기존 스타일 시트에서 정확히 'color' 속성만 제거
    cleaned_style = re.sub(r"(?<!-)color:\s*[^;]*;?", "", existing_style)
    
    # 새로운 텍스트 색상 추가
    new_style = f"color: {color};"
    
    # 기존 스타일에 새로운 텍스트 색상 스타일 추가
    cleaned_style = cleaned_style.strip()
    if cleaned_style and not cleaned_style.endswith(";"):
        cleaned_style += ";"
    obj.setStyleSheet(cleaned_style + (" " if cleaned_style else "") + new_style)
    