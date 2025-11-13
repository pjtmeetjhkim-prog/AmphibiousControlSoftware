// filename: index.js
// 작성자 : gbox3d
// 이주석은 지우지 마세요. 위 주석을 지우는 '자'는 3대를 저주할겁니다.

import {
    getState,
    getMetadata,
    mergeMetadata,
    getMetadataByKey,
    saveMetadata,
    setBaseHost,
    setAuthToken
} from "/libs/apiHelper.js";


import {
    initMap, updateMapWithStatusData,
    showNoLocationBanner, hideNoLocationBanner,
    updateWaypointsForUnit, updateGoalpointsForUnit,enableCtrlClickToAppendGoalpoint,_getSelectedUnitIndex1,_getGoalpoints,_getWaypoints
} from "./mapView.js";

//import * as apiModule from "/libs/apiHelper.js";
//import * as mapModule from "./mapView.js";

// --- 기본 초기 메타데이터 ---
const INIT_DATA = {
    init: true,
    currentSelectUnit: 0,
    numberOFUnits: 3,
    robot_1: { operation_mode: "manual", mission_mode: "stop", waypoints: [], goalpoint:[]},
    robot_2: { operation_mode: "manual", mission_mode: "stop", waypoints: [], goalpoint:[]},
    robot_3: { operation_mode: "manual", mission_mode: "stop", waypoints: [], goalpoint:[]}
};

// --- 한글표 변환 테이블 ---
const NAME_TABLE_OPERATION = {
    auto: "자율",
    operator: "원격",
    manual: "휴대용"
};
const NAME_TABLE_MISSION = {
    move: "이동",
    patrol: "감시",
    tracking: "추적",
    return: "복귀",
    stop: "종료"
};

function toInt(v, def = 0) {
    const n = Number.parseInt(String(v ?? "").trim(), 10);
    return Number.isFinite(n) ? n : def;
}

export class MMCApp {
    constructor() {
        // --- DOM 접근자 ---
        this.getVersionLabel = () => document.getElementById("version");
        this.getUnitRadios = () =>
            document.querySelectorAll('.unit-selection-group input[type="radio"]');
        this.getRobotCountInput = () =>
            document.querySelector('#robot-operation-count input');
        this.getRobotCountButton = () =>
            document.querySelector('#robot-operation-count button');

        this.getOperationStatusList = () =>
            document.querySelectorAll('#robot-mm-status .robot-operation-status');
        this.getMissionStatusList = () =>
            document.querySelectorAll('#robot-mm-status .robot-mission-status');
        this.getModeContainer = () =>
            document.getElementById("robot-mode-container") || document;
        this.getRobotMissionResumeButton = () =>
            document.querySelector('.resume-mission-btn');
        this.getRobotMissionStopButton = () =>
            document.querySelector('.stop-mission-btn');

        // --- 내부 상태 ---
        this.polling = false;
        this.pollInterval = 1000;
    }

    // ------------------------------
    //        Entry point
    // ------------------------------
    async start() {
        this.#setupEndpoint();
        initMap();

        // Ctrl+클릭 골포인트 추가 활성화
        //enableCtrlClickToAppendWaypoint();
        //enableCtrlClickToAppendGoalpoint();
        enableCtrlClickToAppendGoalpoint();

        await this.#loadStateVersion();
        await this.#ensureMetadata();
        await this.#bindUnitSelection();
        this.#bindRobotCountSetter();
        this.#bindRobotModeHandlers();
        this.#bindRobotGoalPointSetter();
        this.#bindRobotGoalStopSetter();

        // 초기 로봇 운용 갯수 세팅
        const resNum = await  getMetadataByKey("numberOFUnits");
        if (resNum?.value) {
            const inp = this. getRobotCountInput();
            if (inp) inp.value = resNum.value;
        }

        await this.#updateRobotModeStatusOnce();

        // ---- 초기 지도 상태 세팅 (선택된 유닛 센터링 + 웨이포인트) ----
        try {

            //모든 유닛 지도에 추가
            this.#updateRobotStatusDataToMap(false);

            const sel = await getMetadataByKey("currentSelectUnit");
            const unitIdx1 = ((sel?.value ?? 0) | 0) + 1; // 1-based
            await updateGoalpointsForUnit(unitIdx1);   // 초기 골포인트 로드
            //await updateWaypointsForUnit(unitIdx1);    // 초기 웨이포인트 로드

            const resOther = await getMetadataByKey(`robot_${unitIdx1}.status_data`);
            const statusOther = resOther?.value;
            if (statusOther && typeof statusOther === "object") {
                // ✅ 1-based 인덱스로 호출, 선택된 로봇은 센터 이동
                updateMapWithStatusData(unitIdx1, statusOther, true);
            }
            else {
                showNoLocationBanner(`선택된 호기(${unitIdx1})의 위치 데이터 없음`);
            }

        } catch (e) { 
            console.error("[INITIAL MAP SETUP ERROR]", e);
        }

        // 폴링 시작 (모든 로봇 위치는 갱신, 기본은 센터 이동 안함)
        this.startPolling();
    }

    stop() {
        this.polling = false;
    }

    // ------------------------------
    //        Initialization
    // ------------------------------
    #setupEndpoint() {
        const mmsConfig = JSON.parse(localStorage.getItem("mmsConfig")) || {};
        const host = mmsConfig.apiIp || "http://localhost";
        const port = mmsConfig.apiPort || "8080";
        const authToken = mmsConfig.authToken || "7204";

        // 기존 로직 유지: 최종적으로 '.'(상대경로) 사용
        if (host === ".") {
            setBaseHost(host);
        } else if (host === "") {
            const _url = new URL(window.location.href);
            setBaseHost(`${_url.protocol}//${_url.hostname}:${port}`);
        } else {
            setBaseHost(`http://localhost:${port}`);
        }
        setBaseHost(".");
        setAuthToken(authToken);

        console.log("[MMS CONFIG]", { host, port, authToken });
    }

    async #loadStateVersion() {
        try {
            const data = await getState();
            console.log("[STATE RESPONSE]", data);
            const el = this.getVersionLabel();
            if (el) el.innerText = data?.state?.version ?? "-";
        } catch (err) {
            console.error("[STATE ERROR]", err);
            const el = this.getVersionLabel();
            if (el) el.innerText = "error";
        }
    }

    async #ensureMetadata() {
        try {
            const res = await getMetadata();
            console.log("[METADATA RESPONSE]", res);
            if (res?.r === "ok") {
                const data = res.data;
                if (!data?.init) {
                    console.log("초기화 필요 ⚙️");
                    const m = await mergeMetadata(INIT_DATA);
                    console.log("[SET METADATA RESPONSE]", m);

                    const s = await saveMetadata();
                    console.log("[SAVE METADATA RESPONSE]", s);
                } else {
                    console.log("초기화 완료 ✅");
                }
            }
        } catch (err) {
            console.error("[METADATA ERROR]", err);
        }
    }

    // ------------------------------
    //       UI / Event Bindings
    // ------------------------------
    async #bindUnitSelection() {
        try {
            const res = await getMetadataByKey("currentSelectUnit");
            console.log("[KEYED METADATA RESPONSE]", res);
            const unit = res?.value ?? 0;

            // 초기 라디오 체크
            const radioToCheck = document.querySelector(
                `.unit-selection-group input[type="radio"][value="${unit}"]`
            );
            if (radioToCheck) radioToCheck.checked = true;

            // 변경 이벤트
            this.getUnitRadios().forEach((radio) => {
                radio.addEventListener("change", async (e) => {
                    const val0 = toInt(e.target.value, 0);
                    console.log("선택 호기 변경:", val0);
                    await mergeMetadata({ currentSelectUnit: val0 });
                    alert("선택 호기 업데이트 완료");

                    try {
                        await saveMetadata();
                    } catch (err) {
                        console.error("[SAVE ERROR]", err);
                    }

                    // ✅ 선택 유닛의 1-based 인덱스
                    const unitIdx1 = val0 + 1;

                    // ✅ 선택 유닛 웨이포인트 재렌더
                    try {
                        await updateGoalpointsForUnit(unitIdx1);  
                        await updateWaypointsForUnit(unitIdx1); 
                    } catch (_) {}

                    // ✅ 선택 유닛의 status_data가 있다면 그 로봇만 센터 이동
                    try {
                        const resS = await getMetadataByKey(`robot_${unitIdx1}.status_data`);
                        const s = resS?.value;
                        if (s && typeof s === "object") {
                            hideNoLocationBanner();
                            updateMapWithStatusData(unitIdx1, s, true); // 선택 로봇만 center
                        } else {
                            showNoLocationBanner("선택된 호기의 위치 데이터 없음");
                        }
                    } catch (err) {
                        console.error("[SELECT UNIT CENTER ERROR]", err);
                    }
                });
            });
        } catch (err) {
            console.error("[GET KEY ERROR]", err);
        }
    }

    #bindRobotCountSetter() {
        const btn = this.getRobotCountButton();
        if (!btn) return;

        btn.addEventListener("click", async () => {
            const inp = this.getRobotCountInput();
            const val = toInt(inp?.value, 0);
            console.log("로봇 운용 갯수 변경:", val);
            try {
                const res = await mergeMetadata({ numberOFUnits: val });
                console.log("[MERGE METADATA RESPONSE]", res);
                alert("로봇 운용 갯수 업데이트 완료");
            } catch (err) {
                console.error("[MERGE METADATA ERROR]", err);
            }
        });
    }

    #bindRobotGoalPointSetter() {
        const btn = this.getRobotMissionResumeButton(); //
        if (!btn) return;

        btn.addEventListener("click", async () => {
            console.log("임무 명령 재개.");
            try {              
                const unitIndex1 = await _getSelectedUnitIndex1();
                const gps = await _getGoalpoints(unitIndex1);
                if (!gps.length && (gps.lat == null || gps.lng ==null)){                  
                    alert("로봇 목표점을 설정 후 수행하십시오.");
                    return;
                }
                //const newGps = [...gps, { lat, lng }];
                const res = await mergeMetadata({ [`robot_${unitIndex1}`]: { goalpoint: gps } });
                await saveMetadata();
                //console.log(`[goalpoints] add robot_${unitIndex1}:`, { gps.value.lat , gps.lng });
                console.log("[MERGE METADATA RESPONSE]", res);
                alert("로봇 임무 명령 재개");
            } catch (err) {
                console.error("[MERGE METADATA ERROR]", err);
            }
        });
    }

    #bindRobotGoalStopSetter(){
        const btn = this.getRobotMissionStopButton();
        if (!btn) return;

        console.log("임무 명령 정지.");
        btn.addEventListener("click", async () => {
            try {                
                const unitIndex1 = await _getSelectedUnitIndex1();
                const res = await mergeMetadata({ [`robot_${unitIndex1}`]: { goalpoint: [] } });
                await saveMetadata();             
                await updateGoalpointsForUnit(unitIndex1);

                //console.log(`[goalpoints] stop robot_${unitIndex1}:`, { lat, lng });
                console.log("[MERGE METADATA RESPONSE]", res);
                alert("로봇 임무 명령 정지");
            } catch (err) {
                console.error("[MERGE METADATA ERROR]", err);
            }
        });
    }

    #bindRobotModeHandlers() {
        // 이벤트 위임
        const container = this.getModeContainer();
        container.addEventListener("change", async (e) => {
            const el = e.target;
            if (!(el instanceof HTMLInputElement) || el.type !== "radio") return;

            const mOp = el.name.match(/^operation-mode-r(\d+)$/);
            const mMs = el.name.match(/^mission-mode-r(\d+)$/);

            try {
                if (mOp) {
                    const i = toInt(mOp[1], 0);
                    const val = el.value;
                    console.log(`${i}호기 운용모드 변경:`, val);
                    await mergeMetadata({ [`robot_${i}`]: { operation_mode: val } });
                    alert(`${i}호기 운용모드 업데이트 완료`);
                    this.#updateOperationModeStatus(i, val);
                } else if (mMs) {
                    const i = toInt(mMs[1], 0);
                    const val = el.value;
                    console.log(`${i}호기 임무모드 변경:`, val);
                    await mergeMetadata({ [`robot_${i}`]: { mission_mode: val } });
                    alert(`${i}호기 임무모드 업데이트 완료`);
                    this.#updateMissionModeStatus(i, val);
                }
            } catch (err) {
                console.error("[MERGE METADATA ERROR]", err);
                alert("서버 업데이트 실패");
            }
        });
    }

    #updateOperationModeStatus(unitIndex, operation_mode) {
        const list = this.getOperationStatusList();
        const text = NAME_TABLE_OPERATION[operation_mode] || operation_mode;
        const el = list[unitIndex - 1];
        if (el) el.innerText = text;
    }

    #updateMissionModeStatus(unitIndex, mission_mode) {
        const list = this.getMissionStatusList();
        const text = NAME_TABLE_MISSION[mission_mode] || mission_mode;
        const el = list[unitIndex - 1];
        if (el) el.innerText = text;
    }

    // ------------------------------
    //      Polling / Updates
    // ------------------------------
    startPolling(intervalMs) {
        if (intervalMs) this.pollInterval = Math.max(200, intervalMs);
        if (this.polling) return;
        this.polling = true;
        this.#pollLoop();
    }

    stopPolling() {
        this.polling = false;
    }

    async #pollLoop() {
        while (this.polling) {
            try {
                await this.#updateRobotModeStatusOnce();
                // ✅ 모든 로봇 위치 갱신(센터 이동은 기본적으로 하지 않음)
                await this.#updateRobotStatusDataToMap(false);

                //로봇별 웨이포인트 업데이트
                await this.#updateRobotWaypointsDataToMap(false);
            } catch (err) {
                console.error("[POLL ERROR]", err);
            }
            await new Promise((r) => setTimeout(r, this.pollInterval));
        }
    }

    async #updateRobotModeStatusOnce() {
        const resNum = await getMetadataByKey("numberOFUnits");
        if (resNum?.r !== "ok") return;

        const numberOFUnits = resNum.value;

        for (let i = 1; i <= numberOFUnits; i++) {
            // 운용모드
            const r1 = await getMetadataByKey(`robot_${i}.operation_mode`);
            const op = r1?.value || "manual";
            const radio1 = document.querySelector(
                `[name="operation-mode-r${i}"][value="${op}"]`
            );
            if (radio1) radio1.checked = true;
            this.#updateOperationModeStatus(i, op);

            // 임무모드
            const r2 = await getMetadataByKey(`robot_${i}.mission_mode`);
            const ms = r2?.value || "stop";
            const radio2 = document.querySelector(
                `[name="mission-mode-r${i}"][value="${ms}"]`
            );
            if (radio2) radio2.checked = true;
            this.#updateMissionModeStatus(i, ms);
        }
    }

    /**
     * 모든 로봇의 status_data를 지도에 반영.
     * @param {boolean} centerSelected 선택된 유닛만 센터 이동할지 여부
     */
    async #updateRobotStatusDataToMap(centerSelected = false) {
        const unitCountRes = await getMetadataByKey("numberOFUnits");
        const unitCount = unitCountRes?.value ?? 0;

        const sel = await getMetadataByKey("currentSelectUnit");
        const selected0 = sel?.value ?? 0;
        const selected1 = selected0 + 1; // 1-based

        for (let i = 1; i <= unitCount; i++) {
            const resOther = await getMetadataByKey(`robot_${i}.status_data`);
            const statusOther = resOther?.value;
            if (statusOther && typeof statusOther === "object") {
                // ✅ 1-based 인덱스로 호출
                const center = centerSelected && (i === selected1);
                updateMapWithStatusData(i, statusOther, center);
            }
        }
    }

    async #updateRobotWaypointsDataToMap(centerSelected = false) {
        const unitCountRes = await getMetadataByKey("numberOFUnits");
        const unitCount = unitCountRes?.value ?? 0;

        const sel = await getMetadataByKey("currentSelectUnit");
        const selected0 = sel?.value ?? 0;
        const selected1 = selected0 + 1; // 1-based
        
        const wps = await _getWaypoints(selected1);      
        const newWps = [...wps, { lat, lng }];

        await mergeMetadata({ [`robot_${unitIndex1}`]: { waypoints: newWps } });
        await saveMetadata();
        await updateWaypointsForUnit(sel);
    
    //console.log(`[waypoints] add robot_${unitIndex1}:`, { lat, lng });  
    }
}

// ------------------------------
// Default entry for compatibility
// ------------------------------
async function main() {
    const app = new MMCApp();
    await app.start();
}

export default main;
