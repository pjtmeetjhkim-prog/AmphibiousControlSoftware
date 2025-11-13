"""
filename : robot_client.py
author : gbox3d

정찰로봇 프로토콜을 이용한 클라이언트 연결 모듈
"""

import socket
import threading
import time
import struct
import json
from protocol import (
    Packet, SendType, ContentType, DeviceID,
    DriveControl, SensorStatus,
    create_drive_control_packet, parse_sensor_status_data
)

class RobotClient:
    def __init__(self, host="localhost", port=5000):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.recv_thread = None
        self.running = False
        self.sequence_no = 0
        self.lock = threading.Lock()
        
        # 센서 데이터 저장용
        self.sensors = {}
        self.position = [0, 0, 0]
        self.speed = 0
        self.yaw = 0
        self.orientation = [1, 0, 0, 0]
        self.linear_velocity = [0, 0, 0]
        self.angular_velocity = [0, 0, 0]
        self.last_update_time = 0
        
        # 콜백 함수
        self.on_sensor_updated = None
        self.on_drive_ack = None
        
    def connect(self):
        """서버에 연결"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            self.running = True
            
            # 수신 스레드 시작
            self.recv_thread = threading.Thread(target=self.receive_loop)
            self.recv_thread.daemon = True
            self.recv_thread.start()
            
            print(f"서버 {self.host}:{self.port}에 연결되었습니다.")
            return True
        except Exception as e:
            print(f"연결 실패: {e}")
            self.connected = False
            return False
            
    def disconnect(self):
        """서버 연결 종료"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        self.connected = False
        
        if self.recv_thread and self.recv_thread.is_alive():
            self.recv_thread.join(timeout=1.0)
            
        print("서버 연결이 종료되었습니다.")
            
    def receive_loop(self):
        """패킷 수신 루프"""
        buffer = bytearray()
        
        try:
            while self.running and self.socket:
                try:
                    # 데이터 수신
                    data = self.socket.recv(1024)
                    if not data:
                        print("서버 연결이 종료되었습니다.")
                        break
                    
                    # 수신 데이터를 버퍼에 추가
                    buffer.extend(data)
                    
                    # 완전한 패킷 처리
                    while True:
                        # 최소 패킷 크기는 20바이트 (헤더 18바이트 + 접미사 2바이트)
                        if len(buffer) < 20:
                            break
                        
                        # 프리픽스 확인 (Little-Endian에서 0xAABB는 0xBB 0xAA로 표현됨)
                        if buffer[0] != 0xBB or buffer[1] != 0xAA:
                            # 프리픽스를 찾을 때까지 버퍼 이동
                            found = False
                            for i in range(len(buffer) - 1):
                                if buffer[i] == 0xBB and buffer[i+1] == 0xAA:
                                    buffer = buffer[i:]
                                    found = True
                                    break
                            if not found:
                                buffer.clear()
                            break
                        
                        # 데이터 길이 확인
                        data_length = struct.unpack_from('<I', buffer, 14)[0]
                        
                        # 전체 패킷 길이 계산 (헤더 18바이트 + 데이터 길이 + 접미사 2바이트)
                        total_length = 18 + data_length + 2
                        
                        # 완전한 패킷이 수신되었는지 확인
                        if len(buffer) < total_length:
                            break
                            
                        # 패킷 추출
                        packet_data = bytes(buffer[:total_length])
                        
                        # 패킷 처리
                        packet = Packet.from_bytes(packet_data)
                        if packet:
                            self.process_packet(packet)
                            
                        # 처리된 패킷 제거
                        buffer = buffer[total_length:]
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"수신 중 오류: {e}")
                    break
                    
        finally:
            self.connected = False
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
                
    def process_packet(self, packet):
        """수신된 패킷 처리"""
        print(f"패킷 수신: {packet}")
        
        # 센서 상태 패킷 처리
        if packet.content_type == ContentType.SENSOR_STATUS and packet.send_type == SendType.DATA:
            sensors = parse_sensor_status_data(packet.data)
            
            with self.lock:
                # 센서 데이터 갱신
                for sensor in sensors:
                    self.sensors[sensor.sensor_id] = sensor
                    
                    # 위치 센서 (ID: 1)
                    if sensor.sensor_id == 1:
                        self.position[0] = sensor.temperature  # X 좌표
                    elif sensor.sensor_id == 2:
                        self.speed = sensor.temperature  # 전진 속도
                    elif sensor.sensor_id == 3:
                        self.yaw = sensor.temperature  # 방향
                    elif sensor.sensor_id == 4:
                        self.position[1] = sensor.temperature  # Y 좌표
                        
                self.last_update_time = time.time()

                
            # 콜백 함수 호출
            if self.on_sensor_updated:
                self.on_sensor_updated()
        elif packet.content_type == ContentType.DRIVE_CONTROL and packet.send_type == SendType.ACK:
            print("드라이브 제어 ACK 수신")
            if self.on_drive_ack:
                self.on_drive_ack()


    # def send_drive_command(self, speed, direction):
    #     """주행 제어 명령 전송"""
    #     if not self.connected or not self.socket:
    #         print("서버에 연결되어 있지 않습니다.")
    #         return False
            
    #     try:
    #         with self.lock:
    #             self.sequence_no += 1
                
    #             # 드라이브 제어 객체 생성
    #             drive_control = DriveControl(
    #                 speed=speed,         # 속도 (-2.0 ~ 2.0 m/s)
    #                 direction=direction,  # 방향 (-1.0 ~ 1.0 rad)
    #                 operation_mode=1      # 1: 자율 모드
    #             )
                
    #             # 패킷 생성
    #             packet = create_drive_control_packet(
    #                 sender_id=DeviceID.CONTROL_CENTER,
    #                 receiver_id=DeviceID.SCOUT_ROBOT,
    #                 sequence_no=self.sequence_no,
    #                 drive_control=drive_control
    #             )
                
    #             # 패킷 전송
    #             packet_bytes = packet.to_bytes()
    #             self.socket.sendall(packet_bytes)
                
    #             return True
                
    #     except Exception as e:
    #         print(f"명령 전송 실패: {e}")
    #         return False
            
    # def get_sensor_data(self):
    #     """센서 데이터 반환"""
    #     with self.lock:
    #         return {
    #             'sensors': self.sensors.copy(),
    #             'position': self.position.copy(),
    #             'orientation': self.orientation.copy(),
    #             'linear_velocity': self.linear_velocity.copy(),
    #             'angular_velocity': self.angular_velocity.copy(),
    #             'last_update_time': self.last_update_time
    #         }
    # def get_drive_status(self):
    #     """현재 주행 상태 반환"""
    #     with self.lock:
    #         return {
    #             'speed': self.speed,
    #             'yaw': self.yaw,
    #             'position': self.position.copy()
    #         }
