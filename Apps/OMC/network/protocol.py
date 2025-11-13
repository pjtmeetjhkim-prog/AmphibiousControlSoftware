#############################
## filename : protocol.py
## 설명 : TCP Agent 공통 프로토콜 정의/유틸
## 작성자 : gbox3d
## 위 주석은 수정하지 마세요.
#############################

import json
import struct
from typing import Optional
import asyncio

# 고정 체크코드
checkcode: int = 20251004

# 최대 페이로드 크기(이미지/JSON 등)
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024  # 16MB

# 리틀엔디언(네트워크 전송용)
# 모든 pack/unpack은 '<' 로 통일합니다.
# 예: struct.pack("<II", checkcode, code)

# 요청/푸시 코드
REQ_PING     = 99
REQ_JSON     = 0x01
REQ_ACK      = 0x02
REQ_IMG_UP   = 0x10
REQ_IMG_DOWN = 0x11

PUSH_JSON    = 0x03
PUSH_STATUS  = 0x04
PUSH_ALERT   = 0x05

# 상태코드
SUCCESS                 = 0
ERR_CHECKCODE_MISMATCH  = 1
ERR_INVALID_DATA        = 2
ERR_INVALID_REQUEST     = 3
ERR_INVALID_PARAMETER   = 4
ERR_INVALID_FORMAT      = 5
ERR_UNKNOWN_CODE        = 8
ERR_EXCEPTION           = 9
ERR_TIMEOUT             = 10

WARN_TIMEOUT   = 100
WARN_NO_DATA   = 101
WARN_NO_IMAGE  = 102

# 헤더 타임아웃 경계(서버 측에서 사용)
MAX_HEADER_TIMEOUTS = 3

# 이미지 타입
IMG_JPG = 0x00
IMG_PNG = 0x01
IMG_BMP = 0x02


class ServerProtocol:
    # 서버도 같은 상수 사용(가독성 위해 별칭)
    checkcode = checkcode

    REQ_PING     = REQ_PING
    REQ_JSON     = REQ_JSON
    REQ_ACK      = REQ_ACK
    REQ_IMG_UP   = REQ_IMG_UP
    REQ_IMG_DOWN = REQ_IMG_DOWN

    PUSH_JSON   = PUSH_JSON
    PUSH_STATUS = PUSH_STATUS
    PUSH_ALERT  = PUSH_ALERT

    SUCCESS               = SUCCESS
    ERR_CHECKCODE_MISMATCH= ERR_CHECKCODE_MISMATCH
    ERR_INVALID_DATA      = ERR_INVALID_DATA
    ERR_INVALID_REQUEST   = ERR_INVALID_REQUEST
    ERR_INVALID_PARAMETER = ERR_INVALID_PARAMETER
    ERR_INVALID_FORMAT    = ERR_INVALID_FORMAT
    ERR_UNKNOWN_CODE      = ERR_UNKNOWN_CODE
    ERR_EXCEPTION         = ERR_EXCEPTION
    ERR_TIMEOUT           = ERR_TIMEOUT

    WARN_TIMEOUT  = WARN_TIMEOUT
    WARN_NO_DATA  = WARN_NO_DATA
    WARN_NO_IMAGE = WARN_NO_IMAGE

    MAX_HEADER_TIMEOUTS = MAX_HEADER_TIMEOUTS
    MAX_PAYLOAD_BYTES   = MAX_PAYLOAD_BYTES

    IMG_JPG = IMG_JPG
    IMG_PNG = IMG_PNG
    IMG_BMP = IMG_BMP

    @staticmethod
    async def send_packet(writer, data: bytes, lock: Optional[asyncio.Lock]=None):
        if lock:
            async with lock:
                writer.write(data)
                await writer.drain()
        else:
            writer.write(data)
            await writer.drain()

    @staticmethod
    async def send_json(writer, code: int, obj: dict, lock: Optional[asyncio.Lock]=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        size = struct.pack("<I", len(body))
        header = struct.pack("<II", checkcode, code)
        await ServerProtocol.send_packet(writer, header + size + body, lock)

    @staticmethod
    async def send_ack(writer, req_code: int, status: int, lock: Optional[asyncio.Lock]=None):
        # 헤더(8B): checkcode + REQ_ACK
        # 바디(5B): req_code(uint32 LE) + status(uint8)
        header = struct.pack("<II", checkcode, REQ_ACK)
        body   = struct.pack("<IB", req_code, status)
        await ServerProtocol.send_packet(writer, header + body, lock)

    @staticmethod
    async def send_push_status(writer, status: int, lock: Optional[asyncio.Lock]=None):
        # 헤더(8B): checkcode + PUSH_STATUS
        # 바디(16B): status(1) + reserved(15)
        header = struct.pack("<II", checkcode, PUSH_STATUS)
        body   = bytes([status]) + bytes(15)
        await ServerProtocol.send_packet(writer, header + body, lock)

    @staticmethod
    async def send_push_alert(writer, status: int, lock: Optional[asyncio.Lock]=None):
        # 헤더(8B): checkcode + PUSH_ALERT
        # 바디(16B): status(1) + reserved(15)
        header = struct.pack("<II", checkcode, PUSH_ALERT)
        body   = bytes([status]) + bytes(15)
        await ServerProtocol.send_packet(writer, header + body, lock)


class ClientProtocol:
    # 확장자→이미지 타입 매핑
    TYPE_FROM_EXT = {
        ".jpg": IMG_JPG, ".jpeg": IMG_JPG,
        ".png": IMG_PNG,
        ".bmp": IMG_BMP
    }

    @staticmethod
    async def send_ack(writer, checkcode_val: int, req_code: int, status: int, lock: Optional[asyncio.Lock]=None):
        # 클라이언트가 PUSH_JSON 수신 시 즉시 ACK 보낼 때 사용
        header = struct.pack("<II", checkcode_val, REQ_ACK)
        body   = struct.pack("<IB", req_code, status)        
        await ServerProtocol.send_packet(writer, header + body, lock)

    async def send_ping(writer, lock: Optional[asyncio.Lock]=None):
        header = struct.pack("<II", checkcode, REQ_PING)        
        await ServerProtocol.send_packet(writer, header, lock)

    
