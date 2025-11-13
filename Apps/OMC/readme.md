# 수륙양용 로봇 관제 시스템 UI Application

## 개발환경

```bash
pip install -r requirements.txt
``` 

**designer**
```bash
pyside6-designer
```
## ui 파일 변환

uic 커맨드를 사용하여 ui 파일을 py로 변환합니다. 아래 예제 를 참고 하세요.

```bash
pyside6-uic mainwindow.ui -o mainwindow.py
```

## qrc 파일 변환

qrc 파일을 py로 변환합니다. 아래 예제를 참고 하세요.

```bash
pyside6-rcc assets/icons.qrc -o icons_rc.py
pyside6-rcc assets/font.qrc -o font_rc.py
```

## window용 실행파일만들기

```bash
pip install pyinstaller
pyinstaller --onefile --windowed app.py
pyinstaller --onefile --windowed --icon=favicon.ico app.py


```

위 명령어를 사용하여 윈도우용 실행 파일을 만들 수 있습니다. `--onefile` 옵션은 단일 실행 파일을 생성하고, `--windowed` 옵션은 콘솔 창 없이 GUI 애플리케이션을 실행하도록 합니다.


## launch.json 


lauch.json 파일은 다음과 같이 설정합니다.  

```json
{
    
    "configurations": [
        {
            "type": "debugpy",
            "request": "launch",
            "name": "Launch Current Venv",
            "python": "${workspaceFolder}/.venv/bin/python", // 가상환경을 사용하고 있다면 python 경로를 가상환경의 python 경로로 설정해야 합니다.  
            //"program": "${workspaceFolder}/${input:programPath}",
            "program": "${file}",
            "cwd": "${fileDirname}", //cwd는 현재 파일이 있는 디렉토리로 설정해야 합니다.  
            "console": "integratedTerminal",
        },
        {
            "name": "Python 디버거: 현재 파일",
            "type": "debugpy",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal"
        }
    ],
    "inputs": [
        {
            "type": "promptString",
            "id": "programPath",
            "description": "Enter the relative path to the main Python file"
        }
    ]
}
```

## Test Url

```txt
bsqai01.iptime.org
ailab-miso.iptime.org
```
