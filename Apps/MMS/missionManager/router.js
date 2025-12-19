// #############################
// ## filename : missionManager/router.js
// ## 설명 : TCP 서버(WebUI 관리) API 라우터
// ## 작성자 : gbox3d (by ChatGPT)
// ## 위 주석은 수정하지 마세요.
// #############################

import express from "express";
import { deepMerge, getByPath } from "./deepMerge.js";
import {
  IMG_JPG, IMG_PNG, IMG_BMP
} from "./tcpProtocol.js";

//c4i config read
import fs from "node:fs/promises";
import path from "node:path";

const router = express.Router();

/** -------------------------------------------------------
 * 공통 미들웨어: CORS/바디파서
 * ----------------------------------------------------- */
router.use((req, res, next) => {
  res.set("Access-Control-Allow-Origin", "*");
  res.set("Access-Control-Allow-Methods", "*");
  res.set("Access-Control-Allow-Headers", "*");
  next();
});

// NOTE: index.js에서 이미 app.use로 붙는 게 아니므로, 여기서 바디 파서 구성
// raw: 파일 업로드(application/octet-stream), json/text: 일반 API
router.use(express.raw({ limit: "1gb", type: "application/octet-stream" }));
router.use(express.json({ limit: "50mb" }));
router.use(express.text({ limit: "10mb" }));

/** 유틸: TCP 인스턴스 가져오기 */
function getTcp(req) {
  const tcp = req.app?.locals?.tcp;
  if (!tcp) throw new Error("TcpServer instance not found (app.locals.tcp)");
  return tcp;
}

/** 유틸: 이미지 타입 -> MIME */
function imgTypeToMime(t) {
  if (t === IMG_JPG) return "image/jpeg";
  if (t === IMG_PNG) return "image/png";
  if (t === IMG_BMP) return "image/bmp";
  return "application/octet-stream";
}

// missionManager/router.js 상단 유틸 근처에 추가
function setByPath(obj, path, value) {
  if (!path || typeof path !== "string") return;
  const keys = path.split(".");
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    const k = keys[i];
    if (typeof cur[k] !== "object" || cur[k] === null || Array.isArray(cur[k])) {
      cur[k] = {};
    }
    cur = cur[k];
  }
  cur[keys[keys.length - 1]] = value;
}
function deleteByPath(obj, path) {
  if (!path || typeof path !== "string") return false;
  const keys = path.split(".");
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    const k = keys[i];
    if (typeof cur[k] !== "object" || cur[k] === null) return false;
    cur = cur[k];
  }
  return delete cur[keys[keys.length - 1]];
}


/** 루트: 라우터 정보 */
router.get("/", (req, res) => {
  res.json({ r: "ok", info: "mission manager (tcp admin api)" });
});

/** -------------------------------------------------------
 * C4I 설정 파일 읽기 API (CORS 방지용)
 * ----------------------------------------------------- */
router.get("/c4i-config", async (req, res) => {
  try {
    // 특정 윈도우 경로 지정 (사용자 환경에 맞게 수정)
    const configPath = "C:/c4i_config.json";
    const data = await fs.readFile(configPath, "utf8");
    res.json(JSON.parse(data));
  } catch (e) {
    console.error("[SERVER] Config Read Error:", e.message);
    res.status(500).json({ r: "err", msg: "설정 파일을 읽을 수 없습니다.", detail: e.message });
  }
});

/** -------------------------------------------------------
 * 서버 상태
 * ----------------------------------------------------- */
// GET /state : TCP 서버 상태+요약
router.get("/state", (req, res) => {
  try {
    const tcp = getTcp(req);
    const s = tcp.state; // {ip, port, timeoutMs, version, clients, banks}
    const metaKeys = Object.keys(tcp.metadataJson || {});
    res.json({
      r: "ok",
      state: s,
      metadata_keys: metaKeys.length,
      banks: s.banks
    });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

/** -------------------------------------------------------
 * metadataJson 제어
 * ----------------------------------------------------- */
// GET /metadata : 전체 스냅샷 조회
router.get("/metadata", (req, res) => {
  try {
    const tcp = getTcp(req);
    const snapshot = JSON.parse(JSON.stringify(tcp.metadataJson || {}));
    res.json({ r: "ok", data: snapshot });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// GET /metadata/:path : 점표기 경로 조회 (예: pos.x.y)
router.get("/metadata/:path", (req, res) => {
  try {
    const tcp = getTcp(req);
    const path = String(req.params.path || "");
    const value = path.includes(".")
      ? getByPath(tcp.metadataJson, path)
      : (tcp.metadataJson?.[path] ?? null);
    res.json({ r: "ok", path, value });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// ===== 키 목록 (optional: 평탄화) =====
router.get("/metadata/keys", (req, res) => {
  try {
    const tcp = getTcp(req);
    const flat = String(req.query.flat || "0") === "1";
    const obj = tcp.metadataJson || {};
    if (!flat) {
      return res.json({ r: "ok", keys: Object.keys(obj) });
    }
    // flat=1 이면 'a.b.c' 형태로 모든 경로 리턴
    const out = [];
    const walk = (o, prefix = "") => {
      for (const k of Object.keys(o)) {
        const keyPath = prefix ? `${prefix}.${k}` : k;
        if (o[k] && typeof o[k] === "object" && !Array.isArray(o[k])) {
          walk(o[k], keyPath);
        } else {
          out.push(keyPath);
        }
      }
    };
    walk(obj, "");
    res.json({ r: "ok", keys: out });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});


// POST /metadata : 전체 교체(덮어쓰기)
router.post("/metadata", (req, res) => {
  try {
    const tcp = getTcp(req);
    const body = req.body;
    if (typeof body !== "object" || Array.isArray(body)) {
      return res.status(400).json({ r: "err", msg: "body must be JSON object" });
    }
    tcp.metadataJson = JSON.parse(JSON.stringify(body));
    res.json({ r: "ok", msg: "replaced", size: Object.keys(tcp.metadataJson).length });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// PATCH /metadata : 부분 병합(딥머지)
router.patch("/metadata", (req, res) => {
  try {
    const tcp = getTcp(req);
    const patch = req.body;
    if (typeof patch !== "object" || Array.isArray(patch)) {
      return res.status(400).json({ r: "err", msg: "body must be JSON object" });
    }
    deepMerge(tcp.metadataJson, patch);
    res.json({ r: "ok", msg: "merged" });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// DELETE /metadata : 전체 초기화
router.delete("/metadata", (req, res) => {
  try {
    const tcp = getTcp(req);
    tcp.metadataJson = {};
    res.json({ r: "ok", msg: "cleared" });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});


// ===== 키 단위 Upsert (PUT /metadata/:path) =====
// body: { value: any }
router.put("/metadata/:path", (req, res) => {
  try {
    const tcp = getTcp(req);
    const path = String(req.params.path || "");
    if (!path) return res.status(400).json({ r: "err", msg: "path required" });

    const body = req.body;
    const hasWrapper = body && Object.prototype.hasOwnProperty.call(body, "value");
    const value = hasWrapper ? body.value : body; // {value} 혹은 raw object 둘 다 허용

    setByPath(tcp.metadataJson, path, value);
    res.json({ r: "ok", path, replaced: true });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// ===== 키 단위 부분 병합 (PATCH /metadata/:path) =====
// body: { ... }  (타겟이 object일 때 deepMerge, 아니면 set)
router.patch("/metadata/:path", (req, res) => {
  try {
    const tcp = getTcp(req);
    const path = String(req.params.path || "");
    if (!path) return res.status(400).json({ r: "err", msg: "path required" });

    const patch = req.body;
    const cur = path.includes(".") ? getByPath(tcp.metadataJson, path) : (tcp.metadataJson?.[path]);

    if (cur && typeof cur === "object" && !Array.isArray(cur) && patch && typeof patch === "object" && !Array.isArray(patch)) {
      deepMerge(cur, patch);
      return res.json({ r: "ok", path, merged: true });
    }
    // 대상이 object가 아니면 통째로 교체
    setByPath(tcp.metadataJson, path, patch);
    res.json({ r: "ok", path, replaced: true });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// ===== 키 단위 삭제 (DELETE /metadata/:path) =====
router.delete("/metadata/:path", (req, res) => {
  try {
    const tcp = getTcp(req);
    const path = String(req.params.path || "");
    if (!path) return res.status(400).json({ r: "err", msg: "path required" });

    const ok = deleteByPath(tcp.metadataJson, path);
    res.json({ r: "ok", path, deleted: ok });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// POST /metadata/save : 메타데이터를 디스크에 저장
router.post("/metadata/save", (req, res) => {
  try {
    const tcp = getTcp(req);
    const out = tcp.saveMetadata();
    res.json({ r: out.ok ? "ok" : "err", saved: out.ok, path: out.path });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

router.post("/metadata/load", (req, res) => {
  try {
    const tcp = getTcp(req);
    const out = tcp.loadMetadata();
    res.json({ r: out.ok ? "ok" : "err", loaded: out.ok, path: out.path });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

/** -------------------------------------------------------
 * imageBank 제어
 * ----------------------------------------------------- */
// GET /banks : 은행 리스트
router.get("/banks", (req, res) => {
  try {
    const tcp = getTcp(req);
    const banks = [];
    for (const [bank_id, e] of tcp.imageBank.entries()) {
      banks.push({
        bank_id,
        img_type: e.type,
        img_size: e.size,
        img_seq: e.seq,
        ts: Math.floor(e.ts ?? Date.now() / 1000)
      });
    }
    res.json({ r: "ok", banks });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// GET /banks/:bankId : 메타 정보 조회(+ ?download=1 이면 바이너리 다운로드)
router.get("/banks/:bankId", (req, res) => {
  try {
    const tcp = getTcp(req);
    const bankId = Number(req.params.bankId ?? -1);
    const entry = tcp.imageBank.get(bankId);
    const wantDownload = String(req.query.download || "0") === "1";

    if (!entry) {
      return res.json({ r: "ok", exists: false, bank_id: bankId });
    }
    if (wantDownload) {
      res.setHeader("Content-Type", imgTypeToMime(entry.type));
      res.setHeader("Content-Length", entry.size);
      return res.send(entry.data);
    }
    res.json({
      r: "ok",
      exists: true,
      bank_id: bankId,
      img_type: entry.type,
      img_size: entry.size,
      img_seq: entry.seq,
      ts: Math.floor(entry.ts ?? Date.now() / 1000)
    });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// PUT /banks/:bankId : 바이너리 업로드(application/octet-stream)
// 헤더: x-img-type [0=JPG,1=PNG,2=BMP], x-img-seq(옵션, 기본 1)
router.put("/banks/:bankId", (req, res) => {
  try {
    const tcp = getTcp(req);
    const bankId = Number(req.params.bankId ?? -1);
    if (!Number.isFinite(bankId) || bankId < 0) {
      return res.status(400).json({ r: "err", msg: "invalid bankId" });
    }

    // 타입/시퀀스
    const imgType = Number(req.header("x-img-type"));
    const imgSeq = Number(req.header("x-img-seq") ?? 1);
    if (![IMG_JPG, IMG_PNG, IMG_BMP].includes(imgType)) {
      return res.status(400).json({ r: "err", msg: "x-img-type must be 0(JPG)|1(PNG)|2(BMP)" });
    }
    const buf = req.body instanceof Buffer ? req.body : Buffer.from(req.body || []);
    tcp.imageBank.set(bankId, {
      data: buf,
      type: imgType,
      seq: imgSeq,
      ts: Date.now() / 1000,
      size: buf.length
    });
    res.json({ r: "ok", bank_id: bankId, size: buf.length });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// DELETE /banks/:bankId : 삭제
router.delete("/banks/:bankId", (req, res) => {
  try {
    const tcp = getTcp(req);
    const bankId = Number(req.params.bankId ?? -1);
    const existed = tcp.imageBank.delete(bankId);
    res.json({ r: "ok", deleted: existed, bank_id: bankId });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

/** -------------------------------------------------------
 * 브로드캐스트/유틸
 * ----------------------------------------------------- */
// POST /broadcast : 연결된 TCP 클라이언트에게 JSON 푸시
// body: { cmd: "whatever", ... }
router.post("/broadcast", async (req, res) => {
  try {
    const tcp = getTcp(req);
    const obj = req.body;

    // 1. C4I 연결 명령 처리
    if (obj.cmd === "C4I_CONNECT") {
      // 함수가 존재하는지 체크 (없으면 500 에러 원인)
      if (typeof tcp.connectToC4I !== 'function') {
        throw new Error("TcpServer에 connectToC4I 함수가 구현되지 않았습니다.");
      }

      const success = await tcp.connectToC4I(obj.target_ip, obj.target_port);
      return res.json({ r: success ? "ok" : "err", msg: success ? "Connected" : "Fail" });
    }

    // 2. C4I 데이터 송신 명령 처리
    if (obj.cmd === "C4I_SEND_DATA") {
      const success = tcp.sendToC4I(obj.payload);
      return res.json({
        r: success ? "ok" : "err",
        msg: success ? "Data sent" : "C4I not connected"
      });
    }

    if (typeof obj !== "object" || Array.isArray(obj)) {
      return res.status(400).json({ r: "err", msg: "body must be JSON object" });
    }
    await tcp.broadcastJson(obj);
    res.json({ r: "ok", pushed: true });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

// POST /ping : 간단한 헬스 체크용 푸시
router.post("/ping", async (req, res) => {
  try {
    const tcp = getTcp(req);
    await tcp.broadcastJson({ cmd: "ping", server_time: Math.floor(Date.now() / 1000) });
    res.json({ r: "ok" });
  } catch (e) {
    res.status(500).json({ r: "err", msg: e.message });
  }
});

export default router;
