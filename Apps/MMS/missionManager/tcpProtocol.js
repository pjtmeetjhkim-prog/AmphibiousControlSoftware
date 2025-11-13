// #############################
// ## filename : tcpProtocol.js
// ## 설명 : TCP Agent 공통 프로토콜 정의/유틸 (Node.js/ESM)
// ## 작성자 : gbox3d (port by ChatGPT)
// ## 위 주석은 수정하지 마세요.
// #############################

import { Buffer } from "node:buffer";

export const checkcode = 20251004;      // 파이썬과 동일 고정 체크코드
export const MAX_PAYLOAD_BYTES = 16 * 1024 * 1024; // 16MB

// 요청/푸시 코드 (파이썬과 동일)
export const REQ_PING      = 99;
export const REQ_JSON      = 0x01;
export const REQ_ACK       = 0x02;
export const REQ_IMG_UP    = 0x10;
export const REQ_IMG_DOWN  = 0x11;

export const PUSH_JSON     = 0x03;
export const PUSH_STATUS   = 0x04;
export const PUSH_ALERT    = 0x05;

// 상태코드
export const SUCCESS                 = 0;
export const ERR_CHECKCODE_MISMATCH  = 1;
export const ERR_INVALID_DATA        = 2;
export const ERR_INVALID_REQUEST     = 3;
export const ERR_INVALID_PARAMETER   = 4;
export const ERR_INVALID_FORMAT      = 5;
export const ERR_UNKNOWN_CODE        = 8;
export const ERR_EXCEPTION           = 9;
export const ERR_TIMEOUT             = 10;

export const WARN_TIMEOUT   = 100;
export const WARN_NO_DATA   = 101;
export const WARN_NO_IMAGE  = 102;

// 이미지 타입
export const IMG_JPG = 0x00;
export const IMG_PNG = 0x01;
export const IMG_BMP = 0x02;

// ---------- 공용 패킷 전송 유틸(LE) ----------
export function buildHeader(code) {
  const buf = Buffer.allocUnsafe(8);
  buf.writeUInt32LE(checkcode, 0);
  buf.writeUInt32LE(code, 4);
  return buf;
}

export function buildJsonPacket(code, obj) {
  const body = Buffer.from(JSON.stringify(obj), "utf8");
  const size = Buffer.allocUnsafe(4);
  size.writeUInt32LE(body.length, 0);
  return Buffer.concat([buildHeader(code), size, body]);
}

// REQ_ACK 응답 바디: <IB
export function buildAckPacketFor(reqCode, status) {
  const header = buildHeader(REQ_ACK);
  const body = Buffer.allocUnsafe(5);
  body.writeUInt32LE(reqCode, 0);
  body.writeUInt8(status, 4);
  return Buffer.concat([header, body]);
}

// PUSH_STATUS/ALERT 바디: status(1) + reserved(15)
export function buildPushStatusPacket(status) {
  const header = buildHeader(PUSH_STATUS);
  const body = Buffer.concat([Buffer.from([status]), Buffer.alloc(15, 0)]);
  return Buffer.concat([header, body]);
}

export function buildPushAlertPacket(status) {
  const header = buildHeader(PUSH_ALERT);
  const body = Buffer.concat([Buffer.from([status]), Buffer.alloc(15, 0)]);
  return Buffer.concat([header, body]);
}
