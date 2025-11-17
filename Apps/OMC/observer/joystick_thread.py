import pygame
from PySide6.QtCore import QThread, Signal, Slot

class JoystickThread(QThread):
    """
    Trustmaster F-16C Viper 조이스틱 입력을 처리하는 스레드
    (pygame 기반)
    """
    # [!] GUI(main_window)로 전송할 새 시그널 정의
    log_message = Signal(str)
    joystick_status = Signal(bool, str) # (connected, name)

    # 1. Gimbal(모터) 제어 (HAT[0])
    #    (pan, tilt) -> 예: (-1, 0), (1, 0), (0, 1), (0, -1), (0, 0)
    gimbal_move = Signal(int, int)

    # 2. EO/IR 카메라 제어
    #    (zoom_dir) -> 1:In, -1:Out, 0:Stop
    gimbal_zoom_continuous = Signal(int)
    gimbal_zoom_digital = Signal()  # BTN[3] (배율 순환)
    gimbal_focus_auto = Signal()    # BTN[4] (자동 초점)

    # 3. 로봇(차량) 제어
    #    (steering, throttle) -> -1.0 ~ 1.0
    robot_move = Signal(float, float)
    robot_estop = Signal()          # BTN[1] (비상 정지)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self.joystick = None
        self.dead_zone = 0.1 # 축 데드존
        
        # 조이스틱의 현재 상태 값 (중복 시그널 방지용)
        self.last_hat = (0, 0)
        self.last_steering = 0.0
        self.last_throttle = 0.0

    def _apply_deadzone(self, value):
        if abs(value) < self.dead_zone:
            return 0.0
        return value

    def run(self):
        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            self.log_message.emit("조이스틱을 찾을 수 없습니다.")
            self.joystick_status.emit(False, "N/A")
            pygame.quit()
            return

        try:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            name = self.joystick.get_name()
            self.log_message.emit(f"'{name}' 조이스틱 연결됨.")
            self.joystick_status.emit(True, name)
        except pygame.error as e:
            self.log_message.emit(f"조이스틱 초기화 실패: {e}")
            self.joystick_status.emit(False, "Error")
            pygame.quit()
            return
            
        self._running = True

        while self._running:
            try:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self._running = False
                        break
                    
                    # --- 1. 김발(모터) 제어 (HAT) ---
                    # [pan, tilt]
                    if event.type == pygame.JOYHATMOTION:
                        if event.hat == 0:
                            if event.value != self.last_hat:
                                self.gimbal_move.emit(event.value[0], event.value[1])
                                self.last_hat = event.value
                    
                    # --- 2. EO/IR 및 로봇 제어 (버튼) ---
                    if event.type == pygame.JOYBUTTONDOWN:
                        # [!] 참고: BTN[0]=Trigger, BTN[1]=NWS, BTN[2]=Pinky, BTN[3]=Boat, BTN[4]=TDC
                        
                        # --- 줌 인 (BTN[0], Trigger) ---
                        # *참고: 요청하신 'BTN[2] Up'은 'Release' 이벤트이며, 
                        # 'ZOOM IN'과 'ZOOM OUT' 동시 제어가 불가능합니다.
                        # 따라서 전문가용 표준 맵핑인 'Trigger(BTN[0])'를 'ZOOM IN'으로 할당합니다.
                        if event.button == 0: 
                            self.gimbal_zoom_continuous.emit(1) # Zoom In

                        # --- 비상 정지 (BTN[1], NWS) ---
                        elif event.button == 1:
                            self.robot_estop.emit()

                        # --- 줌 아웃 (BTN[2], Pinky) ---
                        elif event.button == 3:
                            self.gimbal_zoom_continuous.emit(-1) # Zoom Out

                        # --- 배율 조정 (BTN[3], Boat) ---
                        elif event.button == 2:
                            self.gimbal_zoom_digital.emit()

                        # --- 자동 초점 (BTN[4], TDC) ---
                        elif event.button == 4:
                            self.gimbal_focus_auto.emit()

                    # --- 줌 정지 (버튼 Release) ---
                    if event.type == pygame.JOYBUTTONUP:
                        # (Trigger 또는 Pinky 버튼을 떼면 줌 정지)
                        if event.button == 0 or event.button == 3:
                            self.gimbal_zoom_continuous.emit(0) # Zoom Stop

                    # --- 3. 로봇(차량) 제어 (축) ---
                    if event.type == pygame.JOYAXISMOTION:
                        current_steering = self.last_steering
                        current_throttle = self.last_throttle

                        if event.axis == 0: # AXIS[0] (좌우 조향)
                            current_steering = self._apply_deadzone(event.value)
                        elif event.axis == 1: # AXIS[1] (전진)
                            # 부호 전환 (pygame: Up = -1.0, Down = 1.0)
                            # (전진 = -1.0 -> 1.0 / 후진 = 1.0 -> -1.0)
                            current_throttle = self._apply_deadzone(-event.value) 
                        
                        if (current_steering != self.last_steering or 
                            current_throttle != self.last_throttle):
                            
                            self.robot_move.emit(current_steering, current_throttle)
                            self.last_steering = current_steering
                            self.last_throttle = current_throttle

            except pygame.error as e:
                self.log_message.emit(f"pygame 이벤트 루프 오류: {e}")
                self._running = False # 오류 발생 시 루프 중단

            pygame.time.wait(20) # CPU 점유율 관리 (50Hz)

        self.joystick.quit()
        pygame.joystick.quit()
        pygame.quit()
        self.log_message.emit("조이스틱 스레드 종료됨.")
        self.joystick_status.emit(False, "Terminated")

    @Slot()
    def stop(self):
        self._running = False
        self.wait(1000)