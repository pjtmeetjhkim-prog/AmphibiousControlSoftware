#############################
## filename : client.py
## 설명 : TCP Agent 클라이언트
## 작성자 : gbox3d
## 위 주석은 수정하지 마세요.
#############################

import asyncio
import json
import struct
from typing import Dict, Optional, Union, Callable
from pathlib import Path
import time
from collections import defaultdict

from network.protocol import ServerProtocol, ClientProtocol

class Client:
    def __init__(self, host: str, port: int,
                 checkcode:int = ServerProtocol.checkcode, timeout: float = 15.0):
        self.host = host
        self.port = port
        self.checkcode = checkcode
        self.timeout = timeout

        print(f"[CLIENT] initialized for {self.host}:{self.port} with checkcode={self.checkcode}")

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

        self._recv_task: Optional[asyncio.Task] = None
        self._write_lock = asyncio.Lock()
        self._closed = False

        # 요청별 대기자
        self.waiters: Dict[int, asyncio.Queue] = defaultdict(asyncio.Queue)
        # item_metadata 토큰별 대기자
        self._item_waiters: Dict[str, asyncio.Queue] = {}

        # 콜백
        self.on_connection_start: Optional[Callable[[dict], None]] = None
        self.on_connection_lost: Optional[Callable[[str], None]] = None

        self.on_push_update: Optional[Callable[[dict], None]] = None

    def _notify_connect(self, json_info: dict):
        cb = self.on_connection_start
        if cb:
            try:
                cb(json_info)
            except Exception as e:
                print(f"[CLIENT][WARN] on_connection_start callback error: {e}")

    def _notify_robot_update(self, json_info: dict):
        cb = self.on_robot_update
        if cb:
            try:
                cb(json_info)
            except Exception as e:
                print(f"[CLIENT][WARN] on_robot_update callback error: {e}")

    def _notify_disconnect(self, reason: str):
        cb = self.on_connection_lost
        if cb:
            try:
                cb(reason)
            except Exception as e:
                print(f"[CLIENT][WARN] on_connection_lost callback error: {e}")

    async def start(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            print(f"[CLIENT] connected -> {self.host}:{self.port}")
            self._recv_task = asyncio.create_task(self._recv_loop())
        except Exception as e:
            print(f"[CLIENT] failed to connect: {str(e)}")
            raise ConnectionError(f"failed to connect to {self.host}:{self.port}") from e

    async def stop(self):
        if self._closed:
            return
        self._closed = True
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        print("[CLIENT] closed")

    async def _read_exactly(self, n: int) -> bytes:
        assert self.reader is not None
        return await asyncio.wait_for(self.reader.readexactly(n), timeout=self.timeout)

    # ---------- 기본 요청 ----------
    async def send_ping(self) -> bool:

        await ClientProtocol.send_ping(
            writer=self.writer,
            lock=self._write_lock
        )
        
        status = await asyncio.wait_for(self.waiters[ServerProtocol.REQ_PING].get(), timeout=self.timeout)
        return status == ServerProtocol.SUCCESS

    # ---------- 이미지 업/다운 ----------
    @staticmethod
    def _infer_img_type(path: Path) -> int:
        t = ClientProtocol.TYPE_FROM_EXT.get(path.suffix.lower())
        if t is None:
            raise ValueError(f"unsupported image extension: {path.suffix}")
        return t

    
    async def send_image(self, path: Union[str, Path], seq: int = 0, img_type: Optional[int] = None, bank_id: int = 0) -> bool:
        p = Path(path)
        data = p.read_bytes()
        if img_type is None:
            img_type = self._infer_img_type(p)
        if len(data) > (16 * 1024 * 1024):
            raise ValueError("image too large (>16MB)")

        header = struct.pack("<II", self.checkcode, ServerProtocol.REQ_IMG_UP)
        # 16B header: <B 3x I I I  (img_type, bank_id, img_size, img_seq)
        data_hdr = struct.pack("<B3xIII", img_type, bank_id, len(data), seq)

        await ServerProtocol.send_packet(self.writer, header + data_hdr + data, self._write_lock)
        status = await asyncio.wait_for(self.waiters[ServerProtocol.REQ_IMG_UP].get(), timeout=self.timeout)
        return status == ServerProtocol.SUCCESS


    async def request_image(self, bank_id: int = 0):
        header = struct.pack("<II", self.checkcode, ServerProtocol.REQ_IMG_DOWN)
        # 다운로드는 4바이트 bank_id 바디를 동봉
        body = struct.pack("<I", bank_id)
        await ServerProtocol.send_packet(self.writer, header + body, self._write_lock)

        res = await asyncio.wait_for(self.waiters[ServerProtocol.REQ_IMG_DOWN].get(), timeout=self.timeout)

        if isinstance(res, int):
            return None if res != ServerProtocol.SUCCESS else None

        return res  # {"bank_id": int, "type": int, "seq": int, "data": bytes}

    # ---------- JSON ----------
    async def send_json(self, obj: dict) -> bool:
        
        body = json.dumps(obj).encode("utf-8")
        if len(body) > (4 * 1024 * 1024):
            raise ValueError("JSON data too large (>4MB)")

        header = struct.pack("<II", self.checkcode, ServerProtocol.REQ_JSON)
        size = struct.pack("<I", len(body))
        await ServerProtocol.send_packet(self.writer, header + size + body, self._write_lock)

        status = await asyncio.wait_for(self.waiters[ServerProtocol.REQ_JSON].get(), timeout=self.timeout)
        return status == ServerProtocol.SUCCESS
    
    async def send_json_append(self, obj: dict) -> bool:
        
        payload = {"cmd": "append", "data": obj}

        return await self.send_json(payload)

    async def request_json_by_key(self, key: str) -> Optional[dict]:
        if self.writer is None:
            raise ConnectionError("not connected")

        token = f"item:{time.time_ns()}"  # 요청에 대한 확인을 위한 토큰 생성 , 겹치지않는 값이어야함
        q: asyncio.Queue = asyncio.Queue()
        self._item_waiters[token] = q

        payload = {"cmd": "get_item", "key": key, "token": token}
        body = json.dumps(payload).encode("utf-8")
        header = struct.pack("<II", self.checkcode, ServerProtocol.REQ_JSON)
        size = struct.pack("<I", len(body))
        await ServerProtocol.send_packet(self.writer, header + size + body, self._write_lock)

        try:
            res = await asyncio.wait_for(q.get(), timeout=self.timeout)
            return res
        finally:
            self._item_waiters.pop(token, None)

    # ---------- 수신 루프 ----------
    async def _recv_loop(self):
        try:
            while True:
                try:
                    header = await self._read_exactly(8)
                except asyncio.TimeoutError:
                    print("[CLIENT][WARN] recv timeout")
                    continue

                r_check, r_req = struct.unpack("<II", header)
                if r_check != self.checkcode:
                    print(f"[CLIENT][WARN] checkcode mismatch: got={r_check}, expected={self.checkcode}")
                    return

                # PUSH_JSON
                if r_req == ServerProtocol.PUSH_JSON:
                    size = struct.unpack("<I", await self._read_exactly(4))[0]
                    body = await self._read_exactly(size) if size > 0 else b""
                    try:
                        obj_data = json.loads(body.decode("utf-8"))
                    except Exception:
                        obj_data = {"raw": body[:128].hex()}

                    # print(f"[PUSH JSON] {obj_data}")

                    if obj_data.get("cmd") == "welcome":
                        self._notify_connect(obj_data)

                    if obj_data.get("cmd") == "item_metadata":
                        token = obj_data.get("token")
                        if token and token in self._item_waiters:
                            self._item_waiters[token].put_nowait(obj_data)
                    else:
                        if self.on_push_update:
                            try:
                                self.on_push_update(obj_data)
                            except Exception as e:
                                print(f"[CLIENT][WARN] on_push_update callback error: {e}")

                    #     # print(f"[CLIENT][INFO] item_metadata received for token={token}")
                    # if obj_data.get("cmd") == "robot_update":
                    #     self._notify_robot_update(obj_data)
                        

                    try:
                        await ClientProtocol.send_ack(
                            writer=self.writer,
                            checkcode_val=self.checkcode,
                            req_code=ServerProtocol.PUSH_JSON,
                            status=ServerProtocol.SUCCESS,
                            lock=self._write_lock
                        )
                    except Exception as e:
                        print(f"[CLIENT][ERROR] push-ack send failed: {e}")
                    continue

                # REQ_ACK (서버 ACK / IMG-DOWN 데이터 응답)
                elif r_req == ServerProtocol.REQ_ACK:
                    code_bytes = await self._read_exactly(5)
                    (code, status) = struct.unpack("<IB", code_bytes)

                    if code == ServerProtocol.REQ_IMG_DOWN:
                        if status != ServerProtocol.SUCCESS:
                            self.waiters[ServerProtocol.REQ_IMG_DOWN].put_nowait({"ERROR": status})
                            continue

                        # 13B header: <B I I I (img_type, bank_id, img_size, img_seq)
                        data_hdr = await self._read_exactly(13)
                        img_type, bank_id, img_size, img_seq = struct.unpack("<BIII", data_hdr)

                        img_data = await self._read_exactly(img_size) if img_size > 0 else b""
                        self.waiters[ServerProtocol.REQ_IMG_DOWN].put_nowait(
                            {"bank_id": bank_id, "type": img_type, "seq": img_seq, "data": img_data}
                        )
                        continue
                    else:
                        if status == ServerProtocol.WARN_TIMEOUT:
                            print(f"[CLIENT][WARN] server-side timeout warning for req={code}")                        

                        q = self.waiters.get(code)
                        if q:
                            q.put_nowait(status)
                        else:
                            if code == ServerProtocol.REQ_PING:
                                print(f"[CLIENT][INFO] PING ACK (no waiter)")
                            else:
                                print(f"[CLIENT][INFO] ACK for req={code}, status={status} (no waiter)")
                        continue

                # PUSH_ALERT
                elif r_req == ServerProtocol.PUSH_ALERT:
                    body = await self._read_exactly(16)  # status(1) + reserved(15)
                    status = body[0]
                    print(f"[CLIENT][ALERT] server alert: code={status}")

                    if status == ServerProtocol.WARN_TIMEOUT:
                        # send ping ACK
                        try:
                            await ClientProtocol.send_ping(
                                writer=self.writer,
                                lock=self._write_lock
                            )
                        except Exception as e:
                            print(f"[CLIENT][ERROR] alert-ack send failed: {e}")

                    continue

                # PUSH_STATUS
                elif r_req == ServerProtocol.PUSH_STATUS:
                    body = await self._read_exactly(16)  # status(1) + reserved(15)
                    status = body[0]
                    print(f"[CLIENT][STATUS] server status update: code={status}")
                    continue

                else:
                    print(f"[CLIENT][WARN] unknown req code: {r_req}")

        except asyncio.IncompleteReadError:
            print("[CLIENT][INFO] server closed connection")
            self._notify_disconnect("서버와의 연결이 끊어졌습니다.")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[CLIENT][ERROR] recv_loop: {e}")
