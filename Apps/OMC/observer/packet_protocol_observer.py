import struct
from enum import IntEnum
from typing import Tuple  # [!] 튜플 타입 힌트를 위해 임포트
# ==============================================================================
# Python 3.9+ 버전부터는 (ResponseType, int)와 같은 튜플 타입 힌팅(type hinting) 구문이 
# 비표준으로 간주되며, Pylance 같은 린터(linter)가 오류.
# ==============================================================================

class CommandType(IntEnum):
    """
    송신(C -> S) 명령의 베이스 ID
    """
    CMD_MOTOR_CONTROL     = 0x3020  # 모터 구동명령
    CMD_EO_CAMERA_CONTROL = 0x3030  # EO 카메라 명령
    CMD_IR_CAMERA_CONTROL = 0x3040  # IR 카메라 명령
    CMD_TRACKING_SET      = 0x3090  # 추적 설정
    CMD_HEARTBEAT         = 0x3050  # 감시장비 연결상태 (송신)

class ResponseType(IntEnum):
    """
    수신(S -> C) 응답의 베이스 ID
    """
    RES_MOTOR_CAMERA_INFO = 0x3080  # 모터 및 카메라 구동 정보
    RES_TRACKING_STATUS   = 0x30A0  # 추적 상태
    RES_HEARTBEAT_ACK     = 0x3050  # 감시장비 연결상태 (수신)    
    RES_CAMERA_POWER_STATUS = 0x3070  # 카메라 전원 상태
        
class ContentTypeMapper:
    """
    로봇 ID와 Enum 타입을 조합하여 실제 ID를 생성/파싱합니다.
    [!] MAP 딕셔너리 제거 - Enum 값을 직접 활용
    """
    @staticmethod
    def get_command_id(robot_id: int, command_type: CommandType) -> int:
        """
        송신할 명령의 실제 ContentType ID를 반환합니다.
        (예: get_command_id(1, CommandType.CMD_MOTOR_CONTROL) -> 0x3021)
        """
        # [!] 수정: 맵 조회 대신 Enum의 값(value)을 베이스 ID로 직접 사용
        if not isinstance(command_type, CommandType):
            raise ValueError(f"Unknown command type: {command_type}")        
        return command_type.value + robot_id

    @staticmethod
    #def get_response_type(content_id: int) -> (ResponseType, int):
    # [!] 수정: 반환 타입을 (ResponseType, int) -> Tuple[ResponseType, int]로 변경
    def get_response_type(content_id: int) -> Tuple[ResponseType, int]:
        """
        수신된 ContentType ID로부터 ResponseType과 robot_id를 반환합니다.
        (예: get_response_type(0x3082) -> (ResponseType.RES_MOTOR_CAMERA_INFO, 2))
        """
        robot_id = content_id & 0x000F  # 마지막 1바이트 (0~F)
        base_id = content_id & 0xFFF0  # 로봇 ID를 제외한 Base ID
        
        try:
            # [!] 수정: 맵 조회 대신 Enum 생성자로 베이스 ID를 변환
            response_type = ResponseType(base_id)
            return response_type, robot_id
        except ValueError:
            # ResponseType Enum에 정의되지 않은 ID
            return None, robot_id
        
# ==============================================================================
# 2. Command Enums (명령 상수 정의)
# ==============================================================================
NO_COMMAND = 0
NO_COMMAND_POS = 0x5555  # 위치제어 명령없음

class MotorMode(IntEnum):
    NO_OP       = 0
    SPEED_CONTROL = 1  # 속도 제어
    POSITION_CONTROL = 2  # 위치 제어

class MotorPanControl(IntEnum):
    NO_OP   = 0
    LEFT    = 1
    RIGHT   = 2
    STOP    = 3

class MotorTiltControl(IntEnum):
    NO_OP   = 0
    UP      = 1
    DOWN    = 2
    STOP    = 3

class CameraZoomMode(IntEnum):
    NO_OP       = 0
    CONTINUOUS  = 1  # 연속 제어
    POSITION    = 2  # 위치 제어

class CameraZoomControl(IntEnum):
    NO_OP   = 0
    ZOOM_IN = 1
    ZOOM_OUT = 2
    STOP    = 3

class CameraDigitalZoom(IntEnum):
    NO_OP   = 0
    X1      = 1
    X2      = 2
    X4      = 3
    X8      = 4
    X12     = 5

class CameraFocusMode(IntEnum):
    NO_OP       = 0
    CONTINUOUS  = 1
    POSITION    = 2
    
class CameraFocusControl(IntEnum):
    NO_OP   = 0
    NEAR    = 1
    FAR     = 2
    STOP    = 3
    AUTO    = 4

class IRCameraZoom(IntEnum):
    NO_OP   = 0
    X1      = 1
    X2      = 2
    X4      = 3

class TrackingChannel(IntEnum):
    EO      = 1
    IR      = 2

class TrackingCommand(IntEnum): # [!] '추적 설정'용으로 새로 추가
    START   = 1
    STOP    = 2

# ==============================================================================
# 3. Packet Protocol Class (빌더 / 파서)
# ==============================================================================
class PacketProtocol:
    """
    감시장비 패킷 프로토콜 처리 클래스
    - 모든 데이터는 Little-Endian ('<')
    - build_..._payload() 메소드들은 'data' 바이트만 생성
    - parse_...() 메소드들은 'data' 바이트를 파싱
     # [!] 수정: 바이트 오더('<') 문자 제거
    #HEADER_FORMAT = '<H H'  # ContentTypeID (unsigned short), Length (unsigned short)
    HEADER_FORMAT = 'H H'  # ContentTypeID (unsigned short), Length (unsigned short)
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    SUFFIX = 0xEDFF
    #SUFFIX_FORMAT = '<H'    
    SUFFIX_FORMAT = 'H'    # [!] 수정: 바이트 오더('<') 문자 제거
    SUFFIX_SIZE = struct.calcsize(SUFFIX_FORMAT)
    """
    # [!] 삭제: SUFFIX 관련 변수 제거
    
    """
    감시장비 패킷 프로토콜 처리 클래스 (시퀀스 번호 포함, Suffix 없음)
    - 모든 데이터는 Little-Endian ('<')
    - 헤더: [ID(H, 2b)] + [Len(H, 2b)] + [Seq(L, 4b)] = 8 bytes
    """
    # [!] 수정: 헤더 포맷 변경 (H=ushort, L=uint32)
    HEADER_FORMAT = '<H H L'  # ContentTypeID, DataLength, SequenceNumber
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT) # 8 bytes

    # --- 3.1. 기본 패킷 생성기 (Static Method) ---
    @staticmethod
    def build_packet(content_type_id: int, sequence_num: int, data: bytes = b'') -> bytes:
        """
        [!] 수정: 새로운 8바이트 헤더와 데이터를 조합하여 패킷 생성
        """
        data_len = len(data)
        try:
            # 1. 헤더 패킹 (ID, Length, Sequence)
            header = struct.pack(
                PacketProtocol.HEADER_FORMAT,
                content_type_id,
                data_len,
                sequence_num
            )
            # 2. 헤더와 데이터 결합 (Suffix 없음)
            return header + data
            
        except struct.error as e:
            print(f"[PacketBuilder] Error packing ID {content_type_id:X}, Seq {sequence_num}: {e}")
            return b''
        
    '''
    @staticmethod
    def build_packet(content_type_id: int, data: bytes = b'') -> bytes:
        """
        최종적으로 ContentTypeID와 Suffix를 붙여 완전한 패킷을 생성합니다.
        [ContentTypeID(H)] [Length(H)] [Data(..s)] [Suffix(H)]
        """
        data_len = len(data)
        #packet_format = f'{PacketProtocol.HEADER_FORMAT}{data_len}s{PacketProtocol.SUFFIX_FORMAT}'
        #[!] 수정: 바이트 오더('<')를 포맷 맨 앞에 한 번만 추가
        packet_format = f'<{PacketProtocol.HEADER_FORMAT}{data_len}s{PacketProtocol.SUFFIX_FORMAT}'
        try:
            return struct.pack(
                packet_format,
                content_type_id,
                data_len,
                data,
                PacketProtocol.SUFFIX
            )
        except struct.error as e:
            #print(f"[PacketBuilder] Error packing data for ID {content_type_id:X}: {e}")
            # 에러 발생 시, 사용된 포맷을 함께 출력하여 디버깅 용이하게 함
            print(f"[PacketBuilder] Error packing ID {content_type_id:X}: {e} (Format: '{packet_format}')")
            return b''
    '''
    # --- 3.2. 송신(CMD) 페이로드(Payload) 생성 헬퍼 ---

    @staticmethod
    def build_motor_control_payload(
        mode: MotorMode,
        pan_control: MotorPanControl,
        pan_speed_dps: float,
        pan_position_deg: float,
        tilt_control: MotorTiltControl,
        tilt_speed_dps: float,
        tilt_position_deg: float
    ) -> bytes:
        """
         1. 모터 구동명령 페이로드 [길이 16bytes]
        Args:
            pan_speed_dps: 방위각 속도 (0~30 deg/s)
            pan_position_deg: 방위각 위치 (-180~179 deg)
            tilt_speed_dps: 고각 속도 (0~20 deg/s)
            tilt_position_deg: 고각 위치 (-20~60 deg)
        """
        # (Ushort) [0~30 deg/s * 100]
        pan_speed_scaled = max(0, min(3000, int(pan_speed_dps * 100)))
        # (Ushort) [0~20 deg/s * 100]
        tilt_speed_scaled = max(0, min(2000, int(tilt_speed_dps * 100)))

        # (short) [-180~179 deg * 100]
        if pan_position_deg == NO_COMMAND_POS:
            pan_pos_scaled = NO_COMMAND_POS
        else:
            pan_pos_scaled = max(-18000, min(17900, int(pan_position_deg * 100)))
        
        # (short) [-20~60 deg * 100]
        if tilt_position_deg == NO_COMMAND_POS:
            tilt_pos_scaled = NO_COMMAND_POS
        else:
            tilt_pos_scaled = max(-2000, min(6000, int(tilt_position_deg * 100)))
            
        # [구조체] 16 bytes
        # 7개 항목 (14 bytes) + 1개 reserve (2 bytes) = 16 bytes
        data = struct.pack(
            '<H H H h H H h H',  # 8 * 2 = 16 bytes
            mode.value,                 # 구동제어모드 (Ushort)
            pan_control.value,          # 방위각 속도제어 (Ushort)
            pan_speed_scaled,           # 방위각 속도 (Ushort)
            pan_pos_scaled,             # 방위각 위치제어 (short)
            tilt_control.value,         # 고각 속도제어 (Ushort)
            tilt_speed_scaled,          # 고각 속도 (Ushort)
            tilt_pos_scaled,            # 고각 위치제어 (short)
            0                           # reserve (Ushort)
        )
        return data

    '''
    @staticmethod
    def build_eo_camera_control_payload(
        zoom_mode: CameraZoomMode,
        zoom_control: CameraZoomControl,
        digital_zoom: CameraDigitalZoom,
        focus_mode: CameraFocusMode,
        focus_control: CameraFocusControl
    ) -> bytes:
        """
        2. EO카메라 명령 페이로드 [길이 16bytes]
        """
        data = struct.pack(
            '<H H H H H H H H', # 8 * 2 = 16 bytes
            zoom_mode.value,      # 줌 제어모드 (Ushort)
            zoom_control.value,   # 줌 연속 제어 (Ushort)
            0xFFFF,               # reserve (Ushort)
            digital_zoom.value,   # 디지털 줌제어 (Ushort)
            focus_mode.value,     # 포커스 제어모드 (Ushort)
            focus_control.value,  # 포커스 연속 제어 (Ushort)
            0,                    # reserve (Ushort)
            0                     # reserve (Ushort)
        )
        return data
    '''
    @staticmethod
    def build_eo_camera_control_payload(
        zoom_mode: CameraZoomMode,
        zoom_control: CameraZoomControl,
        reserve3: int, # [!] 수정: '0' 하드코딩 대신 인수로 받음
        digital_zoom: CameraDigitalZoom,
        focus_mode: CameraFocusMode,
        focus_control: CameraFocusControl
    ) -> bytes:
        """
        2. EO카메라 명령 페이로드 [길이 16bytes]
        (reserve3 필드 추가됨)
        """
        data = struct.pack(
            '<H H H H H H H H', # 8 * 2 = 16 bytes
            zoom_mode.value,      # Field 1
            zoom_control.value,   # Field 2
            reserve3,               # reserve3 [!] Field 3 (예: 0xFFFF or 0)
            digital_zoom.value,   # Field 4
            focus_mode.value,     # Field 5
            focus_control.value,  # Field 6
            0,                    # Field 7 (reserve)
            0                     # Field 8 (reserve)
        )
        return data
    
    @staticmethod
    def build_ir_camera_control_payload(zoom_mode: IRCameraZoom) -> bytes:
        """
        3. IR카메라 명령 페이로드 [길이 4bytes]
        """
        data = struct.pack(
            '<H H', # 2 * 2 = 4 bytes
            zoom_mode.value,      # 줌 제어모드 (Ushort)
            0                     # reserve (Ushort)
        )
        return data

    @staticmethod
    def build_tracking_set_payload(
        x: int, y: int, width: int, height: int, 
        channel: TrackingChannel, command: TrackingCommand
    ) -> bytes:
        """
        5. 추적 설정 [길이 12bytes] - (수정됨)
        """
        data = struct.pack(
            '<H H H H H H', # 6 * 2 = 12 bytes
            x,              # 추적 박스 X축 (Ushort)
            y,              # 추적 박스 Y축 (Ushort)
            width,          # 추적박스 Width (Ushort)
            height,         # 추적박스 Height (Ushort)
            channel.value,  # 추적 채널 (Ushort)
            command.value   # [!] 추적 시작 및 정지 (Ushort)
        )
        return data

    @staticmethod
    def build_heartbeat_payload() -> bytes:
        """ 7. HeartBeat (페이로드 없음) """
        return b''

    # --- 3.3. 수신(RES) 패킷 파싱 헬퍼 ---
    
    @staticmethod
    def parse_motor_camera_info(data: bytes) -> dict:
        """
        4. 모터 및 카메라 구동 정보 [길이 8bytes] - 수신
        """
        if len(data) != 8:
            return {"error": f"Invalid length: expected 8, got {len(data)}"}
        
        try:
            pan_scaled, tilt_scaled, eo_zoom_pos, mode = struct.unpack('<h h H H', data)
            
            # 스케일링된 정수 값을 실제 물리 값 (float)으로 변환
            info = {
                "pan_angle": pan_scaled / 100.0,    # 방위각정보 (short, deg*100)
                "tilt_angle": tilt_scaled / 100.0,   # 고각정보 (short, deg*100)
                "eo_zoom_position": eo_zoom_pos,     # EO 줌위치정보 (Ushort)
                "drive_mode": mode                   # 장비구동모드 (Ushort)
            }
            return info
        except struct.error as e:
            return {"error": f"Parsing error: {e}"}

    @staticmethod
    def parse_camera_power_status(data: bytes) -> dict:
        """
        [!] 신규: 카메라 전원 상태 [길이 4bytes] - 수신
        """
        if len(data) != 4:
            return {"error": f"Invalid length: expected 4, got {len(data)}"}
        
        try:
            eo_power, ir_power = struct.unpack('<H H', data)
            info = {
                "eo_power": eo_power,  # 0: Off, 1: On
                "ir_power": ir_power   # 0: Off, 1: On
            }
            return info
        except struct.error as e:
            return {"error": f"Parsing error: {e}"}
        
    @staticmethod
    def parse_tracking_status(data: bytes) -> dict:
        """ 6. 추적 상태 [4bytes] - 수신 (이전과 동일) """
        if len(data) != 4:
            return {"error": f"Invalid length: expected 4, got {len(data)}"}

        try:
            channel, status = struct.unpack('<H H', data)
            info = {
                "channel": channel,  # 추적 채널 (Ushort, 1=EO, 2=IR)
                "status": status     # 추적 상태 (Ushort, 0=미추적, 1=추적중)
            }
            return info
        except struct.error as e:
            return {"error": f"Parsing error: {e}"}

    @staticmethod
    def parse_connection_status(data: bytes) -> dict:
        """ 7. 감시장비 연결상태정보 (HeartBeat 응답) - 수신 (이전과 동일) """
        ...
        return {"connected": True}