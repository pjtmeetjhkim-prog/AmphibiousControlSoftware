import socket
import time
import struct # 파싱로그용

from PySide6.QtCore import QThread, Signal
from observer.packet_protocol_observer import (
    PacketProtocol, ContentTypeMapper, CommandType, ResponseType
)

class NetworkThread(QThread):
    """
    TCP 소켓 통신을 담당하는 백그라운드 스레드
    이제 'robot_id'를 인스턴스 변수로 가짐
    """
    # [!] 수신 시 'robot_id'를 함께 전달
    connection_status = Signal(int, bool)     # (robot_id, connected)
    received_motor_info = Signal(int, dict)   # (robot_id, info)
    received_tracking_status = Signal(int, dict) # (robot_id, status)
    received_heartbeat = Signal(int)        # (robot_id)
    received_power_status = Signal(int, dict) # (robot_id, info)
    log_message = Signal(str)            

    def __init__(self, robot_id: int, parent=None):
        super().__init__(parent)
        self.host = None
        self.port = None
        self.robot_id = robot_id # [!] 1호기 또는 2호기
        self._is_running = False
        self.sock = None
        self.client_socket = None
        self._buffer = b''
        
        # [!] 송신 시퀀스 번호 카운터
        self.tx_sequence_num = 0

    def connect_to_server(self, host: str, port: int):
        self.host = host
        self.port = port        
        self._is_running = True
        self.client_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)  
        host_info = (self.host, self.port)   
        self.log_message.emit(f"[감시장비 연결 정보 IP[{self.host}]/PORT[{self.port}]")
        self.client_socket.connect(host_info)
        self.log_message.emit(f"[로봇 {self.robot_id}] 스레드 시작...")
        if not self.isRunning():
            self.start()

    def stop(self):
        """스레드를 안전하게 종료합니다."""
        self.log_message.emit(f"[로봇 {self.robot_id}] 스레드 종료 시도...")
        
        # 1. 루프 플래그를 False로 설정
        self._is_running = False
        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
                self.log_message.emit(f"[로봇 {self.robot_id}] 통신 스레드 종료")
            except OSError:
                pass # 이미 닫혔을 수 있음
            
                # 3. [!] msleep()을 중단시키기 위해 exit() 호출
        self.exit() 
        
        # 4. 스레드가 완전히 종료될 때까지 최대 2초 대기
        if not self.wait(2000):
             self.log_message.emit(f"[로봇 {self.robot_id}] 스레드 강제 종료 (timeout).")
             self.terminate() # 최후의 수단
        else:
             self.log_message.emit(f"[로봇 {self.robot_id}] 스레드 정상 종료 확인.")
             
        # [!] 스레드가 멈춘 후에도 GUI가 '미연결'이 아닐 경우를 대비해
        #     stop()이 직접 GUI 상태를 업데이트하도록 신호를 한 번 더 보냄
        self.connection_status.emit(self.robot_id, False)
        
        #self.log_message.emit(f"[로봇 {self.robot_id}] 통신 스레드 종료 시도...")
        #self.wait(2000) # 스레드가 완전히 종료될 때까지 최대 2초 대기

    def send_command(self, cmd_type: CommandType, payload: bytes):
        """
        GUI로부터 받은 '명령 타입'과 '페이로드'를 조합하여
        '로봇ID'에 맞는 '실제 패킷'을 전송합니다.
        """
        """
        [!] 수정: 시퀀스 번호를 증가시키고 build_packet 호출
        """
        #if not self.sock or not self._is_running:
        if not self.client_socket or not self._is_running:
            self.log_message.emit(f"[로봇 {self.robot_id}] 연결되지 않아 전송 실패.")
            return          
        
        try:
            '''
            # 1. 실제 ContentType ID 생성 (ContentTypeMapper가 수정됨)
            content_id = ContentTypeMapper.get_command_id(self.robot_id, cmd_type)
            
            # 2. 완전한 패킷 생성
            packet = PacketProtocol.build_packet(content_id, payload)
            '''
            # 1. 시퀀스 번호 증가 (0부터 시작하면 1, 1이면 1)
            # (32bit uint 최대값 근처에서 오버플로우 방지)
            self.tx_sequence_num = (self.tx_sequence_num + 1) & 0xFFFFFFFF 
            
            # 2. 실제 ContentType ID 생성
            content_id = ContentTypeMapper.get_command_id(self.robot_id, cmd_type)
            
            # 3. 완전한 패킷 생성 (ID, Sequence, Payload 전달)
            packet = PacketProtocol.build_packet(
                content_id, 
                self.tx_sequence_num, 
                payload
            )
            # 4. 전송
            #self.sock.sendall(packet)    
            self.client_socket.sendall(packet)
        except socket.error as e:
            # ...
            self.log_message.emit(f"[로봇 {self.robot_id}] 소켓 데이터 전송 실패: {e}")
            self._handle_disconnect()
        except Exception as e:
            # ...
            self.log_message.emit(f"[로봇 {self.robot_id}] 소켓 패킷 생성 오류: {e}")
            
    def _handle_disconnect(self):
        """ 연결 종료 처리 """
        if self.client_socket:
            try:
                self.client_socket.close()
            except (OSError, socket.error):
                pass
            self.client_socket = None
        
        # GUI(MainWindow)에 연결 해제 상태를 알림
        self.connection_status.emit(self.robot_id, False)
        # _is_running (사용자 연결 의도)이 True일 때만 재시도 로그 출력
        if self._is_running:
            self.log_message.emit(f"[로봇 {self.robot_id}] 서버 연결이 끊어졌습니다.")

    def _parse_buffer(self):
        """
        [!] 수정: 새로운 8바이트 헤더 기반, Suffix 검증 없는 다중 패킷 파서
        """
        while True: # 버퍼에 있는 모든 패킷을 처리할 때까지 반복            
            # 1. 최소 헤더 길이(8바이트) 확인
            if len(self._buffer) < PacketProtocol.HEADER_SIZE:
                break # 데이터가 부족, 다음 recv() 대기

            # 2. 헤더 파싱 (ID, Length, Sequence)
            try:
                header_data = self._buffer[:PacketProtocol.HEADER_SIZE]
                content_type_id, data_len, seq_num = struct.unpack(
                    PacketProtocol.HEADER_FORMAT, header_data
                )
            except struct.error as e:
                self.log_message.emit(f"[로봇 {self.robot_id}] 헤더 파싱 오류: {e}. 버퍼 초기화.")
                self._buffer = b'' # 동기화 깨짐
                break
                
            total_packet_size = PacketProtocol.HEADER_SIZE + data_len

            # 3. 패킷 완성 여부 확인 (헤더 + 데이터)
            if len(self._buffer) < total_packet_size:
                # 아직 데이터가 덜 왔음
                break 
            # 4. [!] Suffix 검증 제거
            
            # 5. 데이터 추출
            packet_data = self._buffer[PacketProtocol.HEADER_SIZE : total_packet_size]

            # 6. 로그 출력 (수신 패킷 구성)
            """
            self.log_message.emit(
                f"[RX {self.robot_id}] ID: 0x{content_type_id:X}, "
                f"Seq: {seq_num}, Len: {data_len}, "
                f"Data: {packet_data.hex(' ', 8)}..." # 8바이트만 표시
            )
            """
                
            # 7. 패킷 처리 (파싱 및 시그널 전송)
            self._process_received_packet(content_type_id, packet_data)
            
            # 8. 처리된 패킷만큼 버퍼에서 제거
            self._buffer = self._buffer[total_packet_size:]
            
            # (버퍼에 남은 데이터가 있으면 while 루프 계속)
            
    def _process_received_packet(self, content_type_id: int, data: bytes):     
        """
        [!] 수정: RES_CAMERA_POWER_STATUS (0x307x) 처리 추가
        """
        response_type, robot_id_from_packet = ContentTypeMapper.get_response_type(content_type_id)
        
        if robot_id_from_packet != self.robot_id:
            self.log_message.emit(f"잘못된 로봇 ID 수신! (Expected {self.robot_id}, Got {robot_id_from_packet})")

        if response_type is None:
            self.log_message.emit(f"[로봇 {self.robot_id}] 미처리 응답 ID 수신: 0x{content_type_id:X}")
            return

        try:
            if response_type == ResponseType.RES_MOTOR_CAMERA_INFO: # 0x308x (10Hz)
                info = PacketProtocol.parse_motor_camera_info(data)
                if "error" not in info:
                    self.received_motor_info.emit(self.robot_id, info)
            
            elif response_type == ResponseType.RES_TRACKING_STATUS: # 0x30Ax (1Hz)
                status = PacketProtocol.parse_tracking_status(data)
                if "error" not in status:
                    self.received_tracking_status.emit(self.robot_id, status)
                    
            elif response_type == ResponseType.RES_HEARTBEAT_ACK: # 0x305x (1Hz)
                self.received_heartbeat.emit(self.robot_id) 
            
            elif response_type == ResponseType.RES_CAMERA_POWER_STATUS: # 0x307x (1Hz)
                info = PacketProtocol.parse_camera_power_status(data)
                if "error" not in info:
                    self.received_power_status.emit(self.robot_id, info)
                
        except Exception as e:
            self.log_message.emit(f"[로봇 {self.robot_id}] 파싱 중 예외 발생 (ID: 0x{content_type_id:X}): {e}")

    def run(self):
        """ QThread의 메인 루프 (start() 호출 시 실행) """
        while self._is_running:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(3.0) 
                self.log_message.emit(f"[로봇 {self.robot_id}] {self.host}:{self.port} 연결 시도 중...")
                self.client_socket.connect((self.host, self.port))
                self.client_socket.settimeout(None)
                self.connection_status.emit(self.robot_id, True)
                self.log_message.emit(f"[로봇 {self.robot_id}] 서버 연결 성공.")

                # 데이터 수신 루프
                while self._is_running:
                    try:
                        #recv_data = self.sock.recv(4096) 
                        recv_data = self.client_socket.recv(4096) 
                        if not recv_data:
                            #self._handle_disconnect() # 서버가 연결 종료 대기
                            break # 내부 루프 탈출
                        
                        self._buffer += recv_data
                        self._parse_buffer()
                        
                    except socket.error as e:
                        # (stop()에서 shutdown() 호출 시 여기로 진입)
                        if self._is_running:
                            # 의도치 않은 종료
                            self.log_message.emit(f"[로봇 {self.robot_id}] 수신 오류: {e}")
                        else:
                            # 의도된 종료
                            self.log_message.emit(f"[로봇 {self.robot_id}] 연결 수동 종료 중...")
                        
                        self._handle_disconnect()
                        break # 내부 루프 탈출
                    except Exception as e:
                        self.log_message.emit(f"[로봇 {self.robot_id}] 파싱 중 예외 발생: {e}")
                        self._buffer = b''
            
            except socket.timeout:
                if self._is_running:
                    self.log_message.emit(f"[로봇 {self.robot_id}] 연결 타임아웃.")
                self.connection_status.emit(self.robot_id, False)
            except socket.error as e:
                if self._is_running:
                    self.log_message.emit(f"[로봇 {self.robot_id}] 소켓 오류: {e}")
                self.connection_status.emit(self.robot_id, False)
            
            # 재연결 로직
            if self._is_running:
                self.log_message.emit(f"[로봇 {self.robot_id}] 5초 후 재연결을 시도합니다...")
                # [!] 수정: time.sleep 대신 self.msleep 사용
                self.msleep(5000) 
        
        # 스레드 완전 종료 (while self._is_running == False)
        self._handle_disconnect() # 마지막으로 소켓 정리 및 상태 전파
        self.log_message.emit(f"[로봇 {self.robot_id}] 네트워크 스레드가 안전하게 종료되었습니다.")
        ## ... (기존과 동일, 단 log_message에 [로봇 ID] 추가) ...
        ##self.log_message.emit(f"[로봇 {self.robot_id}] {self.host}:{self.port} 연결 시도 중...")
        ## ...
        ##self.connection_status.emit(self.robot_id, True)
        ##self.log_message.emit(f"[로봇 {self.robot_id}] 서버 연결 성공.")