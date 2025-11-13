"""
file name : configMng.py
author : gbox3d
이 주석은 건드리지 마시오
"""

import json
import os

class ConfigManager:
    """
    차량 IP, 포트, 카메라 URL 및 사운드 설정을 관리하는 클래스
    파일에서 설정을 저장하고 불러올 수 있습니다.
    최대 3대의 차량을 관리할 수 있습니다.
    """
    
    def __init__(self, config_file="config.json"):
        """
        ConfigManager 초기화
        
        Args:
            config_file (str): 설정 파일 경로 (기본값: "config.json")
        """
        self.config_file = config_file
        
        # 기본 설정값
        self.config = {            
            "currentSelectUnit" : 1,
            "cam": {
                "enable": False,
                "irCameraUrl": "http://localhost:8081/stream",
                "cameraUrl": "http://localhost:8080/stream"
            },            
            "imageDetectionServer" : {
                "enable": False,
                "ip": "localhost",
                "port": 8085
                
            },
            "isSoundOn": False,
            "fullscreen": True,
            "mmsServer": {
                "enable": False,
                "ip": "localhost",
                "port": 8282
            },
            "robotControlServer": {
                "enable": False,
                "ip": "localhost",
                "port": 8283
            }
        }
        
        # 설정 파일이 존재하면 불러오기
        self.load_config()

    def get_current_select_unit(self) :
        if self.config['currentSelectUnit'] is not None :
            return  self.config['currentSelectUnit']
        else :
            return 0
    
    def set_current_select_unit(self,index) :
        self.config['currentSelectUnit'] = index
    
        
    def get_detection_server_ip(self):
        """
        이미지 감지 서버 IP 반환
        
        Returns:
            str: 이미지 감지 서버 IP 주소
        """
        return self.config["imageDetectionServer"]["ip"]
    
    def get_detection_server_port(self):
        """
        이미지 감지 서버 포트 반환
        
        Returns:
            int: 이미지 감지 서버 포트 번호
        """
        return self.config["imageDetectionServer"]["port"]
    
    def set_detection_server_ip(self, ip):
        """
        이미지 감지 서버 IP 설정
        
        Args:
            ip (str): 설정할 이미지 감지 서버 IP 주소
        """
        self.config["imageDetectionServer"]["ip"] = ip
        
    def set_detection_server_port(self, port):
        """
        이미지 감지 서버 포트 설정
        
        Args:
            port (int): 설정할 이미지 감지 서버 포트 번호
        """
        self.config["imageDetectionServer"]["port"] = int(port)

    def get_detection_server_enable(self):
        """
        이미지 감지 서버 활성화 상태 반환
        Returns:
            bool: 이미지 감지 서버 활성화 여부
        """
        return self.config["imageDetectionServer"]["enable"]
    
    def set_detection_server_enable(self, enable):
        """
        이미지 감지 서버 활성화 설정
        Args:
            enable (bool): 활성화 여부
        """
        self.config["imageDetectionServer"]["enable"] = bool(enable)
    

    def is_fullscreen(self):
        """
        전체화면 설정 상태 반환
        
        Returns:
            bool: 전체화면 설정 상태
        """
        return self.config.get("fullscreen", True)
    def set_fullscreen(self, is_fullscreen):
        """
        전체화면 설정 상태 변경
        
        Args:
            is_fullscreen (bool): 전체화면 설정 상태
        """
        self.config["fullscreen"] = bool(is_fullscreen)

    def get_mms_server_info(self):
        """
        MMS 서버 정보 반환

        Returns:
            dict: MMS 서버 정보 딕셔너리
        """
        return self.config.get("mmsServer", {})
    
    def get_robot_control_server_info(self):
        """
        로봇 제어 서버 정보 반환

        Returns:
            dict: 로봇 제어 서버 정보 딕셔너리
        """
        return self.config.get("robotControlServer", {})

    def save_config(self):
        """
        설정을 파일에 저장
        
        Returns:
            bool: 저장 성공 여부
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"설정 저장 중 오류 발생: {e}")
            return False
    
    def load_config(self):
        """
        파일에서 설정 불러오기
        
        Returns:
            bool: 불러오기 성공 여부
        """
        if not os.path.exists(self.config_file):
            # 파일이 없으면 기본 설정 사용
            self.save_config()
            return False
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)

                self.config = loaded_config
                    
                # if "imageDetectionServer" in loaded_config:
                #     self.config["imageDetectionServer"].update(loaded_config["imageDetectionServer"])
                # else:
                #     # 기본 이미지 감지 서버 설정 추가
                #     self.config["imageDetectionServer"] = {
                #         "ip": "localhost",
                #         "port": 8085
                #     }
                # if "fullscreen" in loaded_config:
                #     self.config["fullscreen"] = loaded_config["fullscreen"]
                
                # if "currentSelectUnit" in loaded_config:
                #     self.config["currentSelectUnit"] = loaded_config["currentSelectUnit"]
                # else :
                #     self.config["currentSelectUnit"] = 0
                

                # if "mmsServer" in loaded_config:
                #     self.config["mmsServer"] = loaded_config["mmsServer"]
                # else:
                #     self.config["mmsServer"] = {
                #         "ip": "localhost",
                #         "port": 8282
                #     }

                # if "robotControlServer" in loaded_config:
                #     self.config["robotControlServer"] = loaded_config["robotControlServer"]
                # else:
                #     self.config["robotControlServer"] = {
                #         "ip": "localhost",
                #         "port": 8283
                #     }
                    
                    
            return True
        except Exception as e:
            print(f"설정 불러오기 중 오류 발생: {e}")
            return False    

# 사용 예시
if __name__ == "__main__":
    # ConfigManager 인스턴스 생성
    config_mgr = ConfigManager()
    
    # # 모든 차량 정보 출력
    # for i in range(3):
    #     car_info = config_mgr.get_car_info(i)
    #     print(f"== 차량 {i+1} 정보 ==")
    #     print(f"IP: {car_info['ip']}")
    #     print(f"Port: {car_info['port']}")
    #     print(f"Camera URL: {car_info['camUrl']}")
    #     print()
    
    # print(f"Sound On: {config_mgr.is_sound_on()}")
    
    # # 첫 번째 차량 설정 변경
    # config_mgr.set_car_ip("192.168.1.100", 0)
    # config_mgr.set_car_port(9090, 0)
    # config_mgr.set_car_cam_url("http://192.168.1.100:8081/stream", 0)
    
    # # 두 번째 차량 설정 변경
    # car2_info = {
    #     "ip": "192.168.1.101",
    #     "port": 9091,
    #     "camUrl": "http://192.168.1.101:8081/stream"
    # }
    # config_mgr.set_car_info(car2_info, 1)
    
    # # 사운드 설정 변경
    # config_mgr.set_sound(False)
    
    # # 변경된 설정 저장
    # config_mgr.save_config()
    
    # print("\n설정이 변경되었습니다.")
    # # 변경된 설정 확인
    # for i in range(3):
    #     car_info = config_mgr.get_car_info(i)
    #     print(f"== 차량 {i+1} 정보 ==")
    #     print(f"IP: {car_info['ip']}")
    #     print(f"Port: {car_info['port']}")
    #     print(f"Camera URL: {car_info['camUrl']}")
    #     print(f"Enable: {car_info.get('enable', False)}")
    #     print()
    
    # print(f"Sound On: {config_mgr.is_sound_on()}")