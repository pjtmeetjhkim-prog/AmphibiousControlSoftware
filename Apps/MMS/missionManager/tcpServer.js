// #############################
// ## filename : missionManager/tcpServer.js
// ## 설명 : TCP Agent 중계 Server (Node.js/ESM, Little-Endian) - 모듈화 버전
// ## 작성자 : gbox3d (port & modularized by ChatGPT)
// ## 위 주석은 수정하지 마세요.
// #############################

import net from "node:net";
import fs from "node:fs";
import path from "node:path";

import {
  checkcode,
  MAX_PAYLOAD_BYTES,
  REQ_PING, REQ_JSON, REQ_ACK, REQ_IMG_UP, REQ_IMG_DOWN,
  PUSH_JSON, PUSH_STATUS, PUSH_ALERT,
  SUCCESS,
  ERR_CHECKCODE_MISMATCH, ERR_INVALID_DATA, ERR_INVALID_PARAMETER, ERR_INVALID_FORMAT,
  ERR_UNKNOWN_CODE, ERR_EXCEPTION, ERR_TIMEOUT,
  WARN_TIMEOUT, WARN_NO_IMAGE,
  IMG_JPG, IMG_PNG, IMG_BMP,
  buildHeader, buildJsonPacket, buildAckPacketFor,
  buildPushStatusPacket, buildPushAlertPacket,
} from "./tcpProtocol.js";
import { deepMerge, getByPath } from "./deepMerge.js";

// ---- 내부 유틸 ----
class WriteQueue {
  constructor(socket) {
    this.socket = socket;
    this.chain = Promise.resolve();
  }
  send(buffer) {
    this.chain = this.chain.then(() => new Promise((resolve, reject) => {
      this.socket.write(buffer, err => (err ? reject(err) : resolve()));
    }));
    return this.chain;
  }
}

class SocketReader {
  constructor(socket, timeoutMs) {
    this.socket = socket;
    this.timeoutMs = timeoutMs;
    this.buf = Buffer.alloc(0);
    this.waiters = [];
    this.closed = false;

    socket.on("data", chunk => {
      this.buf = Buffer.concat([this.buf, chunk]);
      this._flush();
    });
    socket.on("close", () => { this.closed = true; this._flush(new Error("socket closed")); });
    socket.on("error", e => { this._flush(e); });


  }

  _flush(err) {
    while (this.waiters.length) {
      const w = this.waiters[0];
      if (err) { this.waiters.shift(); w.reject(err); continue; }
      if (this.buf.length >= w.n) {
        const out = this.buf.subarray(0, w.n);
        this.buf = this.buf.subarray(w.n);
        this.waiters.shift();
        w.resolve(out);
      } else break;
    }
  }

  readExactly(n, timeoutMs = this.timeoutMs) {
    if (this.buf.length >= n) {
      const out = this.buf.subarray(0, n);
      this.buf = this.buf.subarray(n);
      return Promise.resolve(out);
    }
    if (this.closed) return Promise.reject(new Error("socket closed"));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        const idx = this.waiters.findIndex(w => w.resolve === resolve);
        if (idx >= 0) this.waiters.splice(idx, 1);
        reject(new Error("timeout"));
      }, timeoutMs);
      this.waiters.push({
        n,
        resolve: (b) => { clearTimeout(timer); resolve(b); },
        reject: (e) => { clearTimeout(timer); reject(e); },
      });
    });
  }
}

export class TcpServer {
  /**
   * @param {{ip?:string, port?:number, timeoutMs?:number}} opts
   */
  constructor(opts = {}) {
    this.ip = opts.ip ?? "127.0.0.1";
    this.port = Number(opts.port ?? 8282);
    this.timeoutMs = Number(opts.timeoutMs ?? 10_000);
    this.version = "1.0.0-LE (Node)";
    this.server = null;
    this.sockets = new Set();

    this.c4iSocket = null; // C4I 연결 관리용

    // 전역 상태
    this.metadataJson = {};
    this.imageBank = new Map(); // bank_id -> { data, type, seq, ts, size }

    // 부팅 시각
    this.bootTsSec = Math.floor(Date.now() / 1000);
  }

  // === 시간 유틸 ===
  #pad2(n) { return String(n).padStart(2, "0"); }

  #formatDate(d) {
    const yyyy = d.getFullYear();
    const MM = this.#pad2(d.getMonth() + 1);
    const dd = this.#pad2(d.getDate());
    const hh = this.#pad2(d.getHours());
    const mm = this.#pad2(d.getMinutes());
    const ss = this.#pad2(d.getSeconds());
    // Qt의 "yyyy-MM-dd hh:mm:ss" 형식에 맞춤
    return `${yyyy}-${MM}-${dd} ${hh}:${mm}:${ss}`;
  }

  #currentTimeString() {
    return this.#formatDate(new Date());
  }

  #elapsedTimeString() {
    const nowSec = Math.floor(Date.now() / 1000);
    const elapsed = Math.max(0, nowSec - (this.bootTsSec ?? nowSec));
    const h = this.#pad2(Math.floor(elapsed / 3600));
    const m = this.#pad2(Math.floor((elapsed % 3600) / 60));
    const s = this.#pad2(elapsed % 60);
    return `${h}:${m}:${s}`;
  }


  // ====== 메타데이터 영속화 ======
  #getMetaDir() {
    return process.env.METADATA_DIR
      ? path.resolve(process.env.METADATA_DIR)
      : path.resolve(process.cwd(), "metadata");
  }
  #getMetaFile() {
    return path.join(this.#getMetaDir(), "metadata_central.json");
  }
  #ensureDir(dirPath) {
    if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath, { recursive: true });
  }
  /**
   * metadata.json 로드
   * @param {{merge?: boolean}} opts
   * @returns {{ok:boolean, mode:"replace"|"merge", path:string}}
   */
  loadMetadata(opts = {}) {
    const merge = Boolean(opts.merge ?? false);
    const dir = this.#getMetaDir();
    const file = this.#getMetaFile();
    if (!fs.existsSync(file)) {
      return { ok: false, mode: merge ? "merge" : "replace", path: file };
    }
    const json = JSON.parse(fs.readFileSync(file, "utf8"));
    if (merge) {
      deepMerge(this.metadataJson, json);
      return { ok: true, mode: "merge", path: file };
    } else {
      this.metadataJson = json;
      return { ok: true, mode: "replace", path: file };
    }
  }
  /**
   * metadata.json 저장 (pretty)
   * @returns {{ok:boolean, path:string}}
   */
  saveMetadata() {
    const dir = this.#getMetaDir();
    const file = this.#getMetaFile();
    this.#ensureDir(dir);
    fs.writeFileSync(file, JSON.stringify(this.metadataJson ?? {}, null, 2), "utf8");
    return { ok: true, path: file };
  }

  get state() {
    return {
      ip: this.ip,
      port: this.port,
      timeoutMs: this.timeoutMs,
      version: this.version,
      clients: this.sockets.size,
      banks: this.imageBank.size,
    };
  }

  async start() {
    if (this.server) return;
    this.server = net.createServer((sock) => this.#handleConnection(sock));
    this.server.on("listening", () => {
      console.log(`[TCP] listening on ${this.ip}:${this.port} (timeout=${this.timeoutMs}ms, check=${checkcode})`);
    });
    this.server.on("error", (e) => {
      console.error("[TCP][FATAL]", e);
    });
    await new Promise((res) => this.server.listen(this.port, this.ip, res));
  }

  async stop() {
    if (!this.server) return;
    for (const s of this.sockets) {
      try { s.destroy(); } catch { }
    }
    await new Promise((res) => this.server.close(() => res()));
    this.server = null;
  }

  async broadcastJson(obj) {
    const buf = buildJsonPacket(PUSH_JSON, obj);
    await Promise.all(
      [...this.sockets].map(sock => new Promise(resolve => sock.write(buf, () => resolve())))
    );
  }

  // ------- 내부 처리 -------
  async #handleConnection(socket) {
    const addr = `${socket.remoteAddress}:${socket.remotePort}`;
    console.log(`[TCP] connected: ${addr}`);
    this.sockets.add(socket);
    socket.setNoDelay(true);
    socket.setKeepAlive(true);

    const writer = new WriteQueue(socket);
    const reader = new SocketReader(socket, this.timeoutMs);
    let headerTimeouts = 0;
    let nextId = (() => { let i = 1; return () => i++; })();

    const closeWithLog = () => {
      try { socket.destroy(); } catch { }
      this.sockets.delete(socket);
      console.log(`[TCP] closed: ${addr}`);
    };

    socket.on("close", () => this.sockets.delete(socket));

    try {
      // welcome push
      await new Promise(r => setTimeout(r, 300));
      await writer.send(buildJsonPacket(PUSH_JSON, {
        cmd: "welcome",
        version: this.version,
        server_time: Math.floor(Date.now() / 1000),
        id: nextId(),
      })); // 원본 흐름 유지 :contentReference[oaicite:2]{index=2}

      while (true) {
        // header 8B
        let header;
        try {
          header = await reader.readExactly(8);
          headerTimeouts = 0;
        } catch (e) {
          if (String(e.message).includes("timeout")) {
            headerTimeouts++;
            console.warn(`[TCP][WARN] header timeout (${headerTimeouts}/3) from ${addr}`);
            await writer.send(buildPushAlertPacket(WARN_TIMEOUT));
            if (headerTimeouts >= 3) break;
            continue;
          }
          throw e;
        }

        const gotCheck = header.readUInt32LE(0);
        const requestCode = header.readUInt32LE(4);
        if (gotCheck !== checkcode) {
          await writer.send(buildAckPacketFor(requestCode, ERR_CHECKCODE_MISMATCH));
          break;
        }

        // ---- REQ_PING ----
        if (requestCode === REQ_PING) {
          await writer.send(buildAckPacketFor(requestCode, SUCCESS));
          continue;
        }

        // ---- REQ_IMG_UP ----
        if (requestCode === REQ_IMG_UP) {
          let dataHdr;
          try { dataHdr = await reader.readExactly(16); }
          catch (e) {
            if (String(e.message).includes("timeout")) {
              await writer.send(buildAckPacketFor(requestCode, ERR_TIMEOUT)); break;
            }
            await writer.send(buildAckPacketFor(requestCode, ERR_INVALID_FORMAT)); continue;
          }
          const imgType = dataHdr.readUInt8(0);
          const bankId = dataHdr.readUInt32LE(4);
          const imgSize = dataHdr.readUInt32LE(8);
          const imgSeq = dataHdr.readUInt32LE(12);

          if (![IMG_JPG, IMG_PNG, IMG_BMP].includes(imgType)) {
            await writer.send(buildAckPacketFor(requestCode, ERR_INVALID_PARAMETER)); continue;
          }
          if (imgSize > MAX_PAYLOAD_BYTES) {
            await writer.send(buildAckPacketFor(requestCode, ERR_INVALID_DATA)); break;
          }

          let imgData = Buffer.alloc(0);
          try { imgData = imgSize > 0 ? await reader.readExactly(imgSize) : Buffer.alloc(0); }
          catch (e) {
            if (String(e.message).includes("timeout")) { await writer.send(buildAckPacketFor(requestCode, ERR_TIMEOUT)); break; }
            throw e;
          }

          this.imageBank.set(bankId, {
            data: imgData, type: imgType, seq: imgSeq, ts: Date.now() / 1000, size: imgData.length,
          });
          await writer.send(buildAckPacketFor(requestCode, SUCCESS));
          continue;
        }

        // ---- REQ_IMG_DOWN ----
        if (requestCode === REQ_IMG_DOWN) {
          let b4;
          try { b4 = await reader.readExactly(4); }
          catch (e) {
            if (String(e.message).includes("timeout")) { await writer.send(buildAckPacketFor(requestCode, ERR_TIMEOUT)); break; }
            throw e;
          }
          const bankId = b4.readUInt32LE(0);
          const entry = this.imageBank.get(bankId);
          if (!entry) { await writer.send(buildAckPacketFor(requestCode, WARN_NO_IMAGE)); continue; }

          const { data, type, seq, size } = { data: entry.data, type: entry.type, seq: entry.seq, size: entry.size };
          const header2 = buildHeader(REQ_ACK);
          const dataHdr = Buffer.allocUnsafe(18);
          dataHdr.writeUInt32LE(REQ_IMG_DOWN, 0);
          dataHdr.writeUInt8(SUCCESS, 4);
          dataHdr.writeUInt8(type, 5);
          dataHdr.writeUInt32LE(bankId, 6);
          dataHdr.writeUInt32LE(size, 10);
          dataHdr.writeUInt32LE(seq, 14);

          await writer.send(Buffer.concat([header2, dataHdr, data]));
          continue;
        }

        // ---- REQ_JSON ----
        if (requestCode === REQ_JSON) {
          let sizeBuf;
          try { sizeBuf = await reader.readExactly(4); }
          catch (e) {
            if (String(e.message).includes("timeout")) { await writer.send(buildAckPacketFor(requestCode, ERR_TIMEOUT)); break; }
            throw e;
          }
          const size = sizeBuf.readUInt32LE(0);
          if (size > MAX_PAYLOAD_BYTES) { await writer.send(buildAckPacketFor(requestCode, ERR_INVALID_DATA)); break; }

          let body = Buffer.alloc(0);
          try { body = size > 0 ? await reader.readExactly(size) : Buffer.alloc(0); }
          catch (e) {
            if (String(e.message).includes("timeout")) { await writer.send(buildAckPacketFor(requestCode, ERR_TIMEOUT)); break; }
            throw e;
          }

          try {
            const obj = JSON.parse(body.toString("utf8"));
            if (typeof obj !== "object" || Array.isArray(obj)) throw new Error("JSON root must be object");

            const cmd = String(obj.cmd || "").toLowerCase();
            if (cmd === "append") {
              const data = (typeof obj.data === "object" && obj.data) ? obj.data : {};
              deepMerge(this.metadataJson, data);
            } else if (cmd === "get_all") {
              const snapshot = JSON.parse(JSON.stringify(this.metadataJson));

              // ✅ 추가 필드: 현재시간/경과시간
              const now_time = this.#currentTimeString();
              const elapsed_time = this.#elapsedTimeString();

              await writer.send(buildJsonPacket(PUSH_JSON, {
                cmd: "all_metadata",
                data: snapshot,
                now_time,
                elapsed_time
              }));
              continue;
            } else if (cmd === "get_item") {
              const key = String(obj.key || "");
              const token = obj.token;
              const value = key.includes(".") ? getByPath(this.metadataJson, key) : (this.metadataJson?.[key] ?? null);


              // ✅ 추가 필드: 현재시간/경과시간
              const now_time = this.#currentTimeString();
              const elapsed_time = this.#elapsedTimeString();

              await writer.send(buildJsonPacket(PUSH_JSON, {
                cmd: "item_metadata",
                key,
                token,
                value,
                now_time,       // "yyyy-MM-dd hh:mm:ss"
                elapsed_time    // "HH:MM:SS" (서버 시작 이후)
              }));
              // await writer.send(buildJsonPacket(PUSH_JSON, { cmd: "item_metadata", key, value, token }));

              continue;
            } else if (cmd === "set_item") {
              const key = String(obj.key || "");
              const value = obj.value;
              const token = obj.token;

              if (!key) {
                await writer.send(buildAckPacketFor(requestCode, ERR_INVALID_PARAMETER));
                continue;
              }

              // --- 점표기 지원 set ---
              if (key.includes(".")) {
                const parts = key.split(".");
                let curr = this.metadataJson;
                for (let i = 0; i < parts.length - 1; i++) {
                  const p = parts[i];
                  if (typeof curr[p] !== "object" || curr[p] === null) curr[p] = {};
                  curr = curr[p];
                }
                curr[parts[parts.length - 1]] = value;
              } else {
                this.metadataJson[key] = value;
              }

              // 1) 요청에 대한 ACK (클라이언트의 send_json()이 기다림)
              await writer.send(buildAckPacketFor(requestCode, SUCCESS));

              // 2) (선택) 에코/브로드캐스트용 PUSH_JSON
              //    UI 동기화/다중 클라이언트 갱신에 유용
              await writer.send(buildJsonPacket(PUSH_JSON, {
                cmd: "item_metadata_set",
                key, value, token
              }));

              continue;

            } else if (cmd === "list_banks") {
              const banks = [];
              for (const [bId, e] of this.imageBank.entries()) {
                banks.push({ bank_id: bId, img_type: e.type, img_size: e.size, img_seq: e.seq, ts: Math.floor(e.ts ?? Date.now() / 1000) });
              }
              await writer.send(buildJsonPacket(PUSH_JSON, { cmd: "bank_list", banks }));
              continue;
            } else if (cmd === "get_bank_info") {
              const bId = Number(obj.bank_id ?? -1);
              const e = this.imageBank.get(bId);
              const msg = e
                ? { cmd: "bank_info", bank_id: bId, exists: true, img_type: e.type, img_size: e.size, img_seq: e.seq, ts: Math.floor(e.ts ?? Date.now() / 1000) }
                : { cmd: "bank_info", bank_id: bId, exists: false };
              await writer.send(buildJsonPacket(PUSH_JSON, msg));
              continue;
            } else if (cmd === "clear_bank") {
              const bId = Number(obj.bank_id ?? -1);
              this.imageBank.delete(bId);
              await writer.send(buildAckPacketFor(requestCode, SUCCESS));
              continue;
            } else {
              await writer.send(buildAckPacketFor(requestCode, ERR_INVALID_PARAMETER));
              continue;
            }
          } catch (e) {
            console.warn(`[TCP][WARN] invalid JSON: ${e.message}`);
            await writer.send(buildAckPacketFor(requestCode, ERR_INVALID_FORMAT));
            continue;
          }

          await writer.send(buildAckPacketFor(requestCode, SUCCESS));
          continue;
        }

        // ---- REQ_ACK (클라가 푸시에 대한 ACK 보낼 때) ----
        if (requestCode === REQ_ACK) {
          try {
            const ack = await reader.readExactly(5);
            const reqCode = ack.readUInt32LE(0);
            const status = ack.readUInt8(4);
            console.log(`[TCP] push ACK: status=${status} for req=${reqCode}`);
          } catch (e) {
            if (String(e.message).includes("timeout")) console.warn("[TCP][WARN] push ACK read timeout");
          }
          continue;
        }

        // 알 수 없는 코드
        await writer.send(buildPushStatusPacket(ERR_UNKNOWN_CODE));
      }
    } catch (e) {
      console.error("[TCP][ERROR]", e.message);
      try { await writer.send(buildPushStatusPacket(ERR_EXCEPTION)); } catch { }
    } finally {
      closeWithLog();
    }
  }

  /**
   * C4I 서버로의 외부 접속 요청 (MMC에서 호출됨)
   */
  async connectToC4I(ip, port) {
    try {
      if (this.c4iSocket && !this.c4iSocket.destroyed) {
        console.log("[C4I] 이미 연결된 소켓이 있어 재연결을 위해 종료합니다.");
        this.c4iSocket.destroy();
      }

      return new Promise((resolve, reject) => {
        console.log(`[C4I] 서버 접속 시도: ${ip}:${port}`);

        const socket = net.createConnection({ host: ip, port: port }, () => {
          console.log(`[C4I] TCP 서버 연결 성공!`);
          socket.write("MMS Client Connected\r\n");
          resolve(true);
        });

        this.c4iSocket = socket;
        this.#handleConnection_c4i(socket); // 전용 핸들러 호출

        socket.on('error', (err) => {
          console.error("[C4I] 소켓 오류:", err.message);
          this.c4iSocket = null;
          resolve(false);
        });
        socket.on('timeout', () => {
          console.error("[TCP][C4I] 연결 타임아웃");
          socket.destroy();
          resolve(false);
        });
      });

    } catch (e) {
      console.error("[TCP][C4I] connectToC4I 함수 내부 예외:", e.message);
      return false;
    }
  }

  /**
   * C4I 전용 핸들러 (바이너리 프로토콜 체크 제외)
   */
  #handleConnection_c4i(socket) {
    socket.on('data', (data) => {
      // C4I 서버로부터 받은 모든 데이터를 텍스트로 변환하여 출력
      const message = data.toString().trim();
      console.log(`%c[C4I-RECV] ${message}`, "color: #00ff00; font-weight: bold;");

      // 필요한 경우 웹 UI(MMC)로 전달하기 위해 메타데이터에 기록 가능
      // this.metadataJson.c4i_last_msg = message;
      if (this.metadataJson) {
        this.metadataJson.last_c4i_msg = received;
      }
    });

    socket.on('error', (err) => {
      console.error("[C4I-LINK] Socket Error:", err.message);
      this.c4iSocket = null;
    });

    socket.on('end', () => {
      console.warn("[C4I-LINK] Connection closed by C4I server.");
      this.c4iSocket = null;
    });
  }

  /**
   * 전송용 메서드 (C4I 전용)
   */
  sendToC4I(payload) {
    if (this.c4iSocket && !this.c4iSocket.destroyed) {
      this.c4iSocket.write(payload);
      return true;
    }
    return false;
  }
}
