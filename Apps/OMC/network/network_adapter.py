# filename: network_adapter.py
# 역할: asyncio 기반 Client를 별도 스레드 루프에서 돌리고,
#       Qt 시그널로 연결/해제/에러/메시지 등을 UI에 전달하는 어댑터

import asyncio
import threading
from typing import Optional, Callable, Any

from PySide6.QtCore import QObject, Signal

# 외부에서 제공되는 Client를 주입받습니다.
# from client.client import Client  # UI 코드 쪽에서 import 경로에 맞게 넣으세요.

class NetworkAdapter(QObject):
    # ===== 외부로 내보내는 시그널 =====
    connected = Signal(dict)         # 서버가 보낸 초기/welcome 정보
    disconnected = Signal(str)       # 끊김 사유(문자열)
    error = Signal(str)              # 예외/에러 메시지
    message = Signal(dict)           # 필요 시 일반 메시지(payload)

    def __init__(self, client_factory: Callable[[], Any], parent=None):
        """
        client_factory: 호출 시 새 Client 인스턴스를 반환하는 함수.
                        예: lambda: Client(host="localhost", port=8282)
        """
        super().__init__(parent)
        self._client_factory = client_factory

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._client: Optional[Any] = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    # ========== 내부: asyncio 루프 스레드 관리 ==========
    def _ensure_loop(self):
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()

        def _runner():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=_runner, daemon=True)
        self._loop_thread.start()

    def _run_async(self, coro, on_done=None):
        """백그라운드 이벤트 루프에서 코루틴 실행"""
        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        if on_done:
            def _cb(f):
                try:
                    on_done(f)
                except Exception as e:
                    # on_done에서 예외가 떠도 UI 크래시는 방지
                    self.error.emit(f"[on_done] {e}")
            fut.add_done_callback(_cb)
        return fut

    # ========== 외부 API ==========
    def start(self):
        """서버 연결 시작"""
        # Client 인스턴스 준비
        self._client = self._client_factory()

        # Client 콜백을 Qt 시그널로 브릿지
        self._client.on_connection_start = self._on_connection_start
        self._client.on_connection_lost = self._on_connection_lost
        self._client.on_push_update = self._on_push_update
        # 필요 시 self._client.on_message = self._on_message  형태로 확장 가능

        def done(fut):
            try:
                _ = fut.result()  # client.start()가 리턴하는 값(보통 None)
                self._connected = True
            except Exception as e:
                self._connected = False
                self.error.emit(f"[connect] {e}")
                # 연결 실패 시 끊김 신호도 보낼지 선택
                self.disconnected.emit(str(e))

        self._run_async(self._client.start(), on_done=done)

    def stop(self):
        """서버 연결 해제"""
        if not self._connected and not self._client:
            return

        def done(fut):
            try:
                fut.result()
            except Exception as e:
                self.error.emit(f"[disconnect] {e}")
            finally:
                self._connected = False
                self._client = None

        self._run_async(self._client.stop(), on_done=done)

    # ========== Client → Adapter 콜백 ==========
    def _on_connection_start(self, json_info: dict):
        # 백그라운드 스레드에서 호출되어도, 시그널 emit은 Qt가 안전하게 메인스레드로 큐잉함
        self.connected.emit(json_info)

    def _on_connection_lost(self, reason: str):
        self._connected = False
        self._client = None
        self.disconnected.emit(reason)

    def _on_push_update(self, json_info: dict):
        self.message.emit(json_info)

    # 필요 시 일반 메시지 브릿지
    # def _on_message(self, payload: dict):
    #     print(f"[NetworkAdapter] Message received: {payload}")
    #     self.message.emit(payload)

    # 앱 종료 시 안전 정리(선택)
    def shutdown(self):
        try:
            if self._client and self._connected:
                self.stop()
        finally:
            if self._loop:
                loop, self._loop = self._loop, None
                if loop.is_running():
                    loop.call_soon_threadsafe(loop.stop)
            self._loop_thread = None
    
    # ping 전송 ==========
    def ping_server(self):

        if not self._connected or not self._client:
            # messagebox.showwarning("Not connected", "먼저 Connect 버튼으로 서버에 연결하세요.")
            print("[UI] Cannot ping: not connected.")
            return

        def done(fut):
            try:
                ok = fut.result()  # bool
                if ok:
                    print("[UI] Ping successful.")
                else:
                    print("[UI] Ping failed.")
            except Exception as e:
                print(f"[UI] Ping error: {e}")
                
            finally:
                # 연결 상태 유지 중이면 다시 활성화
                if self._connected:
                    pass  # 필요 시 추가 동작

        self._run_async(self._client.send_ping(), on_done=done)

    # JSON by key 요청 ==========
    def fetch_json_by_key(self, key: str, *, timeout_sec: float = 5.0):
        """서버에 key 기반 JSON 요청 → message(cmd='json_item', key=..., data=...) emit"""
        if not self._connected or not self._client:
            self.error.emit("Not connected")
            # 실패도 동일 cmd로 내려서 UI가 한 곳에서 처리 가능하게
            self.message.emit({"cmd": "json_item", "key": key, "ok": False, "data": None, "error": "not connected"})
            return

        async def _task():
            import asyncio
            coro = self._client.request_json_by_key(key)
            res = await asyncio.wait_for(coro, timeout=timeout_sec) if timeout_sec and timeout_sec > 0 else await coro
            return res  # dict | None (서버 구현에 따름)

        def done(fut):
            try:
                res = fut.result()
                self.message.emit({"cmd": "json_item", "key": key, "ok": True, "data": res})
            except Exception as e:
                self.error.emit(f"[json_by_key:{key}] {e}")
                self.message.emit({"cmd": "json_item", "key": key, "ok": False, "data": None, "error": str(e)})

        self._run_async(_task(), on_done=done)

    def set_json_by_key(self, key: str, value: dict, *, timeout_sec: float = 5.0, echo: bool = False):
        """
        서버에 key/value 업데이트 요청.
        결과를 표준화하여 message(cmd='json_item_set_result')로 emit.
        - echo=True 이면, 성공 후 즉시 fetch_json_by_key(key)로 최신값 재조회
        """
        if not self._connected or not self._client:
            self.error.emit("Not connected")
            self.message.emit({"cmd": "json_item_set_result", "key": key, "ok": False, "error": "not connected"})
            return

        async def _task():
            import asyncio
            # 클라이언트의 send_json을 이용해 {"cmd":"set_item",...} 전송 (ACK 기반)
            payload = {"cmd": "set_item", "key": key, "value": value}
            ok = await asyncio.wait_for(self._client.send_json(payload), timeout=timeout_sec)
            return bool(ok)

        def done(fut):
            try:
                ok = fut.result()
                self.message.emit({"cmd": "json_item_set_result", "key": key, "ok": ok})
                # 성공 시 즉시 재조회(선택): 서버가 push 하지 않는 환경에서도 UI 동기화 보장
                if ok and echo:
                    self.fetch_json_by_key(key)
            except Exception as e:
                self.error.emit(f"[json_set_by_key:{key}] {e}")
                self.message.emit({"cmd": "json_item_set_result", "key": key, "ok": False, "error": str(e)})

        self._run_async(_task(), on_done=done)

# ===== MMS 전용 어댑터 (메타데이터/뱅크/알림 등) =====
class NetworkAdapter_MMS(NetworkAdapter):
    def __init__(self, client_factory: Callable[[], Any], parent=None):
        super().__init__(client_factory, parent)

    # 메타데이터 전체 요청
    def fetch_all_metadata(self, *, timeout_sec: float = 5.0):
        if not self._connected or not self._client:
            self.error.emit("Not connected")
            self.message.emit({"cmd": "all_metadata", "ok": False, "error": "not connected"})
            return

        async def _task():
            import asyncio
            payload = {"cmd": "get_all"}
            ok = await asyncio.wait_for(self._client.send_json(payload), timeout=timeout_sec)
            return bool(ok)

        def done(fut):
            try:
                ok = fut.result()
                # 서버는 PUSH_JSON으로 all_metadata를 보내므로,
                # 여기선 ACK만 확인. 실데이터는 _on_push_update → message 시그널로 옴.
                self.message.emit({"cmd": "all_metadata/ack", "ok": ok})
            except Exception as e:
                self.error.emit(f"[MMS:get_all] {e}")
                self.message.emit({"cmd": "all_metadata/ack", "ok": False, "error": str(e)})

        self._run_async(_task(), on_done=done)

    # 특정 키 요청(get_item)
    def fetch_item(self, key: str, *, timeout_sec: float = 5.0):
        if not self._connected or not self._client:
            self.error.emit("Not connected")
            self.message.emit({"cmd": "item_metadata", "key": key, "ok": False, "error": "not connected"})
            return

        async def _task():
            import asyncio
            payload = {"cmd": "get_item", "key": key}
            ok = await asyncio.wait_for(self._client.send_json(payload), timeout=timeout_sec)
            return bool(ok)

        def done(fut):
            try:
                ok = fut.result()
                self.message.emit({"cmd": "item_metadata/ack", "key": key, "ok": ok})
            except Exception as e:
                self.error.emit(f"[MMS:get_item:{key}] {e}")
                self.message.emit({"cmd": "item_metadata/ack", "key": key, "ok": False, "error": str(e)})

        self._run_async(_task(), on_done=done)

    # 특정 키 설정(set_item)
    def set_item(self, key: str, value: dict, *, timeout_sec: float = 5.0, echo: bool = False):
        if not self._connected or not self._client:
            self.error.emit("Not connected")
            self.message.emit({"cmd": "item_metadata_set", "key": key, "ok": False, "error": "not connected"})
            return

        async def _task():
            import asyncio
            payload = {"cmd": "set_item", "key": key, "value": value}
            ok = await asyncio.wait_for(self._client.send_json(payload), timeout=timeout_sec)
            return bool(ok)

        def done(fut):
            try:
                ok = fut.result()
                self.message.emit({"cmd": "item_metadata_set/ack", "key": key, "ok": ok})
                if ok and echo:
                    self.fetch_item(key)
            except Exception as e:
                self.error.emit(f"[MMS:set_item:{key}] {e}")
                self.message.emit({"cmd": "item_metadata_set/ack", "key": key, "ok": False, "error": str(e)})

        self._run_async(_task(), on_done=done)

      
class NetworkAdapter_Robot(NetworkAdapter):
    def __init__(self, client_factory: Callable[[], Any], parent=None):
        super().__init__(client_factory, parent)

      # ===== control_robot: 구동기 제어 (RPM/조향각/각속도) =====
    def control_robot_set_actuators(self, *, rpm: int, angle_deg: int, omega_rad: float,
                                    timeout_sec: float = 5.0, token=None):
        if not self._connected or not self._client:
            self.error.emit("Not connected")
            return
        async def _task():
            import asyncio
            payload = {
                "cmd": "control_robot",
                "action": "set_actuators",
                "data": {
                    "WheelSpeed": int(rpm),
                    "WheelAngle": int(angle_deg),
                    "WheelOmega": float(omega_rad),
                },
                "token": token,
            }
            ok = await asyncio.wait_for(self._client.send_json(payload), timeout=timeout_sec)
            return bool(ok)
        def done(fut):
            try:
                ok = fut.result()
                self.message.emit({"cmd": "control_robot/ack", "action": "set_actuators", "ok": ok})
            except Exception as e:
                self.error.emit(f"[control_robot:set_actuators] {e}")
                self.message.emit({"cmd": "control_robot/ack", "action": "set_actuators", "ok": False, "error": str(e)})
        self._run_async(_task(), on_done=done)

    # ===== control_robot: 운용 패치 (모드/배터리 등 상태값 갱신) =====
    def control_robot_apply_patch(self, *, mission_mode=None, operation_mode=None,
                                  batt_percent=None, batt_tempC=None, extra: dict | None = None,
                                  timeout_sec: float = 5.0, token=None):
        if not self._connected or not self._client:
            self.error.emit("Not connected")
            return
        async def _task():
            # import asyncio
            patch = {}
            if mission_mode is not None:   patch["mission"]   = mission_mode   # move|patrol|tracking|return|stop
            if operation_mode is not None: patch["mode"] = operation_mode # auto|operator|manual
            if batt_percent is not None:   patch["battPercent"]    = float(batt_percent)
            if batt_tempC is not None:     patch["battTempC"]      = float(batt_tempC)
            if extra: patch.update(extra)

            payload = {
                "cmd": "control_robot",
                "action": "apply_patch",
                "data": patch,
                "token": token,
            }
            ok = await asyncio.wait_for(self._client.send_json(payload), timeout=timeout_sec)
            return bool(ok)
        def done(fut):
            try:
                ok = fut.result()
                self.message.emit({"cmd": "control_robot/ack", "action": "apply_patch", "ok": ok})
            except Exception as e:
                self.error.emit(f"[control_robot:apply_patch] {e}")
                self.message.emit({"cmd": "control_robot/ack", "action": "apply_patch", "ok": False, "error": str(e)})
        self._run_async(_task(), on_done=done)

    # ===== control_robot: 위치/자세 텔레포트 =====
    def control_robot_teleport(self, *, x: float | None = None, y: float | None = None,
                               heading_deg: float | None = None, timeout_sec: float = 5.0, token=None):
        if not self._connected or not self._client:
            self.error.emit("Not connected")
            return
        async def _task():
            import asyncio
            data = {}
            if x is not None:           data["x"] = float(x)
            if y is not None:           data["y"] = float(y)
            if heading_deg is not None: data["headingDeg"] = float(heading_deg)

            payload = {
                "cmd": "control_robot",
                "action": "apply_patch",     # 시뮬레이터는 apply_patch로 위치/헤딩 반영
                "data": data,
                "token": token,
            }
            ok = await asyncio.wait_for(self._client.send_json(payload), timeout=timeout_sec)
            return bool(ok)
        def done(fut):
            try:
                ok = fut.result()
                self.message.emit({"cmd": "control_robot/ack", "action": "teleport", "ok": ok})
            except Exception as e:
                self.error.emit(f"[control_robot:teleport] {e}")
                self.message.emit({"cmd": "control_robot/ack", "action": "teleport", "ok": False, "error": str(e)})
        self._run_async(_task(), on_done=done)

