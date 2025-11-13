// filename: apiHelper.js
// description: REST API 호출용 헬퍼 함수 (MMS Web UI 전용 확장판)
// author: gbox3d
// created: 2025-10-27
// updated: 2025-10-27

// ===== 기본 설정 =====
export let AUTH_TOKEN = "7204";
export let BASE_HOST = "http://localhost:8080";
export let BASE = `${BASE_HOST}/api/v1/mms`;

/**
 * 런타임에 인증 토큰/호스트를 변경하고 싶을 때 사용
 */
export function setAuthToken(token) { AUTH_TOKEN = token; }
export function setBaseHost(host) {
    BASE_HOST = host;
    BASE = `${BASE_HOST}/api/v1/mms`;
}

/**
 * 공통 fetch 래퍼 (JSON 응답)
 * @param {string} url - API URL
 * @param {object} options - fetch 옵션 (method, headers, body 등)
 * @returns {Promise<object>} - JSON 응답 결과
 */
export async function apiFetch(url, options = {}) {
    try {
        const res = await fetch(url, options);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        // 일부 엔드포인트는 내용이 없을 수 있으므로 안전 처리
        const ct = res.headers.get("Content-Type") || "";
        if (ct.includes("application/json")) return await res.json();
        const txt = await res.text();
        try { return JSON.parse(txt); } catch { return { ok: true, text: txt }; }
    } catch (err) {
        console.error("[API FETCH ERROR]", err);
        throw err;
    }
}

/**
 * 공통 fetch 래퍼 (바이너리/Blob 응답)
 */
export async function apiFetchBlob(url, options = {}) {
    try {
        const res = await fetch(url, options);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.blob();
    } catch (err) {
        console.error("[API FETCH BLOB ERROR]", err);
        throw err;
    }
}

/**
 * JSON 기본 헤더
 */
function jsonHeaders(extra = {}) {
    return new Headers({
        "Content-Type": "application/json",
        "auth-token": AUTH_TOKEN,
        ...extra
    });
}

// ====== Router/헬스체크 ======

/** 라우터 루트 (Hello) */
export async function helloRoot() {
    const _url = `${BASE}/`;
    return await apiFetch(_url, {
        method: "GET",
        headers: new Headers({ "auth-token": AUTH_TOKEN })
    });
}

/** 서버 상태 조회 */
export async function getState() {
    const _url = `${BASE}/state`;
    return await apiFetch(_url, {
        method: "GET",
        headers: new Headers({
            "Content-Type": "application/json",
            "auth-token": AUTH_TOKEN
        })
    });
}

/** 서버 시간/헬스 핑 */
export async function ping() {
    const _url = `${BASE}/ping`;
    return await apiFetch(_url, {
        method: "POST",
        headers: new Headers({ "auth-token": AUTH_TOKEN })
    });
}

// ====== 브로드캐스트/노티 ======

/**
 * 모든 TCP 클라이언트에 JSON 브로드캐스트
 * @param {object} payload {cmd, message, ...}
 */
export async function broadcast(payload) {
    const _url = `${BASE}/broadcast`;
    return await apiFetch(_url, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify(payload ?? {})
    });
}

// ====== 메타데이터 (스냅샷/부분 업데이트 등) ======

/** 전체 메타데이터 스냅샷 */
export async function getMetadata() {
    const _url = `${BASE}/metadata`;
    return await apiFetch(_url, {
        method: "GET",
        headers: new Headers({ "auth-token": AUTH_TOKEN })
    });
}

/** 메타데이터 키 목록 */
export async function getMetadataKeys() {
    const _url = `${BASE}/metadata/keys`;
    return await apiFetch(_url, {
        method: "GET",
        headers: new Headers({ "auth-token": AUTH_TOKEN })
    });
}

/** 특정 키 조회 */
export async function getMetadataByKey(key) {
    const _url = `${BASE}/metadata/${encodeURIComponent(key)}`;
    return await apiFetch(_url, {
        method: "GET",
        headers: new Headers({ "auth-token": AUTH_TOKEN })
    });
}

/** 특정 키 생성/치환(Upsert) */
export async function setMetadata(key, value) {
    const _url = `${BASE}/metadata/${encodeURIComponent(key)}`;
    return await apiFetch(_url, {
        method: "PUT",
        headers: jsonHeaders(),
        body: JSON.stringify({ value })
    });
}

/** 특정 키 부분 업데이트(PATCH) */
export async function patchMetadata(key, patchObj) {
    const _url = `${BASE}/metadata/${encodeURIComponent(key)}`;
    return await apiFetch(_url, {
        method: "PATCH",
        headers: jsonHeaders(),
        body: JSON.stringify(patchObj ?? {})
    });
}

/** 특정 키 삭제 */
export async function deleteMetadata(key) {
    const _url = `${BASE}/metadata/${encodeURIComponent(key)}`;
    return await apiFetch(_url, {
        method: "DELETE",
        headers: new Headers({ "auth-token": AUTH_TOKEN })
    });
}

/** 루트 단위 머지(PATCH /metadata) */
export async function mergeMetadata(patchObj) {
    const _url = `${BASE}/metadata`;
    return await apiFetch(_url, {
        method: "PATCH",
        headers: jsonHeaders(),
        body: JSON.stringify(patchObj ?? {})
    });
}

export async function saveMetadata() {
    const _url = `${BASE}/metadata/save`;
    return await apiFetch(_url, {
        method: "POST",
        headers: jsonHeaders()
    });
}
export async function loadMetadata(merge = false) {
     const _url = `${BASE}/metadata/load`;
     return await apiFetch(_url, {
         method: "POST",
         headers: jsonHeaders(),
        body: JSON.stringify({ merge })
     });
 }


// ====== 로봇 관련 ======

/** 로봇 목록 */
export async function listRobots() {
    const _url = `${BASE}/robots`;
    return await apiFetch(_url, {
        method: "GET",
        headers: new Headers({ "auth-token": AUTH_TOKEN })
    });
}


// ====== 파일 업/다운로드 ======

/**
 * 파일 업로드 (사용 패턴: reader.result 바디)
 */
export async function uploadFile(_url, _fileObj, upload_name, reader) {
    return await apiFetch(_url, {
        method: "POST",
        body: reader.result,
        headers: new Headers({
            "Content-Type": _fileObj.type,
            "upload-name": encodeURIComponent(upload_name),
            "file-size": _fileObj.size,
            "auth-token": AUTH_TOKEN
        })
    });
}

/**
 * 파일 업로드 (FormData 버전)
 * 서버가 multipart/form-data를 기대할 때 사용
 */
export async function uploadFormData(_url, file, fields = {}) {
    const fd = new FormData();
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
    if (file) fd.append("file", file, file.name ?? "upload.bin");
    return await apiFetch(_url, {
        method: "POST",
        headers: new Headers({ "auth-token": AUTH_TOKEN }), // Content-Type 자동
        body: fd
    });
}

/** 바이너리 다운로드(Blob) → 링크 저장/프리뷰 등에 사용 */
export async function downloadBinary(_url, extraHeaders = {}) {
    return await apiFetchBlob(_url, {
        method: "GET",
        headers: new Headers({ "auth-token": AUTH_TOKEN, ...extraHeaders })
    });
}

// ====== 유틸 ======

/** 쿼리 포함 GET 호출 유틸 */
export async function getWithQuery(path, query = {}) {
    const qs = new URLSearchParams(query).toString();
    const _url = `${BASE}${path}${qs ? `?${qs}` : ""}`;
    return await apiFetch(_url, {
        method: "GET",
        headers: new Headers({ "auth-token": AUTH_TOKEN })
    });
}

/** 임의 POST JSON 호출 유틸 */
export async function postJson(path, bodyObj = {}, extraHeaders = {}) {
    const _url = `${BASE}${path}`;
    return await apiFetch(_url, {
        method: "POST",
        headers: jsonHeaders(extraHeaders),
        body: JSON.stringify(bodyObj ?? {})
    });
}
