# filename: clientApp/app.py
# 위 주석은 수정하지 마시오
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# app.py 상단 import에 추가
from io import BytesIO

import json

import asyncio
import threading
from pathlib import Path

from protocol import ServerProtocol
from client.client import Client

from dotenv import load_dotenv
import os

load_dotenv()

class App(tk.Tk):
    def __init__(self):
        super().__init__()


        self.title("Canvas Image (Pillow)")
        self.geometry("800x600")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.build_ui()


        # --- 이미지 상태 ---
        self._img_pil = None   # 원본 PIL 이미지
        self._img_tk  = None   # 렌더용 Tk 이미지(참조 유지)
        self._last_path: Path | None = None

        # --- 네트워크 상태 ---
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self.client: Client | None = None
        self._connected = False

    def build_ui(self):
        # --- UI ---
        top = tk.Frame(self); top.pack(fill="x")
        self.connect_button = tk.Button(top, text="Connect", command=self.Connect_network)
        self.connect_button.pack(side="left", padx=6, pady=6)

        # __init__ -> UI 섹션에 Ping 버튼 추가
        self.ping_button = tk.Button(top, text="Ping", command=self.ping_server)
        self.ping_button.pack(side="left", padx=6, pady=6)
        self.ping_button.config(state="disabled")

        self.send_image_button = tk.Button(top, text="Send Image...", command=self.send_image)
        self.send_image_button.pack(side="left", padx=6, pady=6)
        self.send_image_button.config(state="disabled")

        self.recv_image_button = tk.Button(top, text="Recv Image", command=self.recv_image)
        self.recv_image_button.pack(side="left", padx=6, pady=6)
        self.recv_image_button.config(state="disabled")

        self.status_var = tk.StringVar(value="Disconnected")
        tk.Label(top, textvariable=self.status_var).pack(side="right", padx=6)

        addressFrame = tk.Frame(self); addressFrame.pack(fill="x")
        tk.Label(addressFrame, text="Server Address:").pack(side="left", padx=6, pady=6)
        port = int(os.getenv('PORT', 8282))
        ip = os.getenv('IP', '127.0.0.1')
        self.address_var = tk.StringVar(value=f"{ip}:{port}")
        tk.Entry(addressFrame, textvariable=self.address_var).pack(side="left", fill="x", expand=True, padx=6, pady=6)

        self.canvas = tk.Canvas(self, bg="#fff"); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw())

        json_frame = tk.Frame(self); json_frame.pack(fill="x")
        self.json_text = tk.StringVar(value='{"test": "hello torch"}')
        tk.Entry(json_frame, textvariable=self.json_text).pack(side="left", fill="x", expand=True, padx=6, pady=6)
        self.send_json_button = tk.Button(json_frame, text="Send JSON", command=self.send_json_append)
        self.send_json_button.pack(side="right", padx=6, pady=6)

        #Get JSON 섹션
        get_json_frame = tk.Frame(self); get_json_frame.pack(fill="x")
        self.get_json_button = tk.Button(get_json_frame, text="Get JSON", command=self.get_json)
        self.get_json_button.pack(side="right", padx=6, pady=6)
        self.json_key_text = tk.StringVar(value='test')
        tk.Entry(get_json_frame, textvariable=self.json_key_text).pack(side="left", fill="x", expand=True, padx=6, pady=6)

        # json 을 받은 내용을 보여줄 텍스트창
        result_frame = tk.Frame(self)
        result_frame.pack(fill="both", expand=True, padx=6, pady=6)

        tk.Label(result_frame, text="JSON 결과 출력:").pack(anchor="w")

        self.json_output = tk.Text(result_frame, height=10, wrap="word")
        self.json_output.pack(fill="both", expand=True, padx=6, pady=6)
        self.json_output.insert("1.0", "여기에 결과가 표시됩니다...")
        
        # json 을 받은 내용을 보여줄 텍스트창

        bottom = tk.Frame(self); bottom.pack(fill="x")
        self.status_info_var = tk.StringVar(value="Ready....")
        tk.Label(bottom, textvariable=self.status_info_var).pack(side="left", padx=6, pady=6)

    # ========== Async loop helpers ==========
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
        """백그라운드 루프에서 코루틴 실행. on_done(future) 콜백은 메인스레드에서 self.after로 호출."""
        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        if on_done:
            def _cb(f):
                # Tk는 메인스레드만 접근 가능
                self.after(0, on_done, f)
            fut.add_done_callback(_cb)
        return fut
    
    def _on_connection_start(self,json_info: dict):
        if json_info is None:
            self.after(0, self._handle_disconnect, "Invalid server response")
            return
        if json_info["cmd"] == "welcome":
            info = f"version : {json_info['version']} , id : {json_info['id']}, connection time : {json_info['server_time']}"
            self.after(0, lambda: self.status_info_var.set(info))
            
    def _on_connection_lost(self, reason: str):
        self.after(0, self._handle_disconnect, reason)

    def _disconnect(self):
        self._connected = False
        self.status_var.set("Disconnected")
        self.status_info_var.set("Ready....")
        self.connect_button.config(state="normal")
        self.connect_button.config(text="Connect")
        self.client = None

        self.send_image_button.config(state="disabled")
        self.recv_image_button.config(state="disabled")
        self.ping_button.config(state="disabled")
        

    # 서버측에서 연결이 끊어진 경우 처리
    def _handle_disconnect(self, reason: str):
        if not self._connected:
            # 이미 끊어진 상태면 중복 처리 방지
            self.status_var.set("Disconnected")
        else:
            self._disconnect()

        messagebox.showwarning("Disconnected", f"서버 연결이 끊어졌습니다.\n\n{reason}")
    
    # 클라이언트 측에서 능동적으로 연결 해제
    def Disconnect_network(self):
        if not self._connected:
            return
        self.connect_button.config(state="disabled")
        self.status_var.set("Disconnecting...")

        def done(fut):
            try:
                fut.result()
            except Exception as e:
                messagebox.showerror("Disconnect failed", str(e))
            finally:
                self._disconnect()

        self._run_async(self.client.stop(), on_done=done)

    # ========== UI actions ==========
    def Connect_network(self):

        if self._connected:
            # messagebox.showinfo("Info", "Already connected.")
            self.Disconnect_network()
            return

        addr = self.address_var.get().strip()
        if ':' not in addr:
            messagebox.showerror("Invalid address", "주소는 IP:PORT 형식이어야 합니다.")
            return   
        
        self.connect_button.config(state="disabled")
        self.status_var.set("Connecting...")

        ip, port_str = addr.split(':', 1)     
        self.client = Client(host=ip, port=int(port_str))

        # 콜백 등록
        self.client.on_connection_lost = self._on_connection_lost   # ← 등록
        self.client.on_connection_start = self._on_connection_start   # ← 등록

        def done(fut):
            try:
                obj = fut.result()
                print(f"Connected: {obj}")
                self._connected = True
                self.status_var.set("Connected")
                self.connect_button.config(state="normal")
                self.connect_button.config(text="Disconnect")
                self.send_image_button.config(state="normal")
                self.recv_image_button.config(state="normal")
                self.ping_button.config(state="normal")

            except Exception as e:
                messagebox.showerror("Connect failed", str(e))
                self._connected = False
                self.status_var.set("Disconnected")

                self.connect_button.config(state="normal")
        
        self._run_async(self.client.start(), on_done=done)
    

    def ping_server(self):
        if not self._connected or not self.client:
            messagebox.showwarning("Not connected", "먼저 Connect 버튼으로 서버에 연결하세요.")
            return

        self.ping_button.config(state="disabled")
        self.status_var.set("Pinging...")

        def done(fut):
            try:
                ok = fut.result()  # bool
                if ok:
                    self.status_var.set("Ping OK")
                else:
                    self.status_var.set("Ping FAIL")
                    messagebox.showwarning("Ping", "Server returned non-success status.")
            except Exception as e:
                self.status_var.set("Disconnected")
                messagebox.showerror("Ping failed", str(e))
            finally:
                # 연결 상태 유지 중이면 다시 활성화
                if self._connected:
                    self.ping_button.config(state="normal")

        self._run_async(self.client.send_ping(), on_done=done)

    def send_image(self):
        if not self._connected or not self.client:
            messagebox.showwarning("Not connected", "먼저 Connect 버튼으로 서버에 연결하세요.")
            return
        path_str = filedialog.askopenfilename(
            title="이미지 선택",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tif *.tiff"), ("All files", "*.*")]
        )
        if not path_str:
            return
        try:
            p = Path(path_str)
            self._img_pil = Image.open(p).convert("RGBA")
            self._last_path = p
            # self.redraw()
        except Exception as e:
            messagebox.showerror("로드 실패", str(e))
            return
        
        def done(fut):
            try:
                ok = fut.result()  # bool
                if ok:
                    self.status_var.set(f"Sent OK: {p.name}")
                else:
                    messagebox.showwarning("Send Image", "Server returned non-success status.")
            except Exception as e:
                messagebox.showerror("Send Image", str(e))
        
        # seq는 간단히 0 사용(필요시 증가/타임스탬프 사용 가능)
        self._run_async(self.client.send_image(self._last_path, seq=0), on_done=done)
  
    def recv_image(self):
        if not self._connected or not self.client:
            messagebox.showwarning("Not connected", "먼저 Connect 버튼으로 서버에 연결하세요.")
            return

        def done(fut):
            try:
                payload = fut.result()  # None or {"type","seq","data"}
                if not payload:
                    messagebox.showinfo("Recv Image", "서버 버퍼에 이미지가 없습니다.")
                    return
                if "ERROR" in payload:
                    if payload["ERROR"] == ServerProtocol.WARN_NO_IMAGE:
                        messagebox.showinfo("Recv Image", "서버 버퍼에 이미지가 없습니다.")
                    return

                img_bytes = payload["data"]
                self._img_pil = Image.open(BytesIO(img_bytes)).convert("RGBA")
                self._last_path = None
                self.redraw()
                self.status_var.set(f"Received image (seq={payload['seq']}, type={payload['type']})")
            except Exception as e:
                messagebox.showerror("Recv Image", str(e))

        self._run_async(self.client.request_image(), on_done=done)

    def send_json_append(self):
        if not self._connected or not self.client:
            messagebox.showwarning("Not connected", "먼저 Connect 버튼으로 서버에 연결하세요.")
            return
        try:            
            data = json.loads(self.json_text.get())
        except Exception as e:
            messagebox.showerror("Invalid JSON", str(e))
            return

        def done(fut):
            try:
                ok = fut.result()  # bool
                if ok:
                    self.status_var.set("Sent JSON OK")
                else:
                    messagebox.showwarning("Send JSON", "Server returned non-success status.")
            except Exception as e:
                messagebox.showerror("Send JSON", str(e))

        self._run_async(self.client.send_json_append(data), on_done=done)

    def get_json(self):
        if not self._connected or not self.client:
            messagebox.showwarning("Not connected", "먼저 Connect 버튼으로 서버에 연결하세요.")
            return

        def done(fut):
            try:
                payload = fut.result()
                if not payload:
                    messagebox.showinfo("Get JSON", "서버 버퍼에 JSON 데이터가 없습니다.")
                    return
                if "ERROR" in payload:
                    if payload["ERROR"] == ServerProtocol.WARN_NO_JSON:
                        messagebox.showinfo("Get JSON", "서버 버퍼에 JSON 데이터가 없습니다.")
                        return
                    
                if "value" in payload:
                    self.json_output.delete("1.0", tk.END)
                    self.json_output.insert(tk.END, payload["value"])
                    self.json_output.see(tk.END)
                else:
                    messagebox.showinfo("Get JSON", "서버로부터 유효한 JSON 응답을 받지 못했습니다.")

            except Exception as e:
                messagebox.showerror("Get JSON", str(e))

        keyStr = self.json_key_text.get().strip()
        self._run_async(self.client.request_json_by_key(keyStr), on_done=done)

    # ========== Canvas ==========
    def redraw(self):
        if self._img_pil is None:
            return
        cw, ch = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        iw, ih = self._img_pil.size
        scale = min(cw / iw, ch / ih)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        img = self._img_pil.resize((nw, nh), Image.LANCZOS)
        self._img_tk = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self._img_tk, anchor="center")

    # ========== Shutdown ==========
    def on_close(self):
        async def _shutdown():
            if self.client:
                await self.client.stop()
        # 비동기 종료 스케줄
        if self._loop:
            asyncio.run_coroutine_threadsafe(_shutdown(), self._loop).result(timeout=3)
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread:
                self._loop_thread.join(timeout=3)
        self.destroy()

if __name__ == "__main__":
    App().mainloop()
