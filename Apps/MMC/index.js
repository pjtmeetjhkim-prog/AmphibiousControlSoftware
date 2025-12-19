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
    updateWaypointsForUnit, updateGoalpointsForUnit, enableCtrlClickToAppendGoalpoint, _getSelectedUnitIndex1, _getGoalpoints, _getWaypoints,
    _clearWaypointLayers
} from "./mapView.js";

//import * as c4imoulde from "/c4i/c4iClient.js";
import { C4IClient } from "./c4i/interface_c4i.js";

//import * as apiModule from "/libs/apiHelper.js";
//import * as mapModule from "./mapView.js";

// --- 기본 초기 메타데이터 ---
const INIT_DATA = {
    init: true,
    currentSelectUnit: 0,
    numberOFUnits: 3,
    robot_1: { operation_mode: "manual", mission_mode: "stop", waypoints: [], goalpoint: [] },
    robot_2: { operation_mode: "manual", mission_mode: "stop", waypoints: [], goalpoint: [] },
    robot_3: { operation_mode: "manual", mission_mode: "stop", waypoints: [], goalpoint: [] }
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

        this.setBroadcastWaringButton = () =>
            document.querySelector('.waring-broadcast-btn');
        // this.setWaringSendButton = () =>
        //     document.querySelector('.waring-sms-btn');
        // this.setWaringJoinButton = () =>
        //     document.querySelector('.waring-join-btn');

        this.connectControlInterfaceButton = () =>
            document.querySelector('.c4i-connect-btn');

        this.c4i = new C4IClient();
        this.c4iPolling = false;
        this.c4iInterval = 100000; // 10초 주기

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

        //경고&알람시스템
        this.#bindWaringBroadcast();
        // this.#bindWaringMessageSetter();
        // this.#bindWaringJoinSetter();
        //C4I 체계연동
        this.#bindControlInterface();

        // 초기 로봇 운용 갯수 세팅
        const resNum = await getMetadataByKey("numberOFUnits");
        if (resNum?.value) {
            const inp = this.getRobotCountInput();
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
            await updateWaypointsForUnit(unitIdx1);    // 초기 웨이포인트 로드

            const resOther = await getMetadataByKey(`robot_${unitIdx1}.robot_status_data`);
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
                    } catch (_) { }

                    // ✅ 선택 유닛의 status_data가 있다면 그 로봇만 센터 이동
                    try {
                        const resS = await getMetadataByKey(`robot_${unitIdx1}.robot_status_data`);
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
                if (!gps.length && (gps.lat == null || gps.lng == null)) {
                    alert("로봇 목표점을 설정 후 수행하십시오.");
                    return;
                }
                const res = await mergeMetadata({ [`robot_${unitIndex1}`]: { goalpoint: gps } });
                await saveMetadata();
                console.log("[MERGE METADATA RESPONSE]", res);
                alert("로봇 임무 명령 재개");
            } catch (err) {
                console.error("[MERGE METADATA ERROR]", err);
            }
        });
    }

    #bindRobotGoalStopSetter() {
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
                const container = this.getModeContainer();

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

    //------------경고알람---------
    #bindWaringBroadcast() {
        const btn = this.setBroadcastWaringButton(); //
        if (!btn) return;

        btn.addEventListener("click", async () => {
            console.log("경고알람방송 활성화.");
            try {
                alert("경고/알람 방송창 활성화");
                window.open('https://192.168.10.97', 'newWindow')
            } catch (err) {
                console.error("[경고/알람 방송 활성화 실패]", err);
            }
        });
    }

    // #bindWaringMessageSetter() {
    //     const btn = this.setWaringSendButton(); //
    //     if (!btn) return;

    //     btn.addEventListener("click", async () => {
    //         console.log("경고알람 메시지 활성화.");
    //         try {
    //             alert("경고/알람 메시지 전송");
    //             this.#sendWaringMessage();

    //         } catch (err) {
    //             console.error("[경고/알람 메시지 전송 실패]", err);
    //         }
    //     });
    // }

    // #bindWaringJoinSetter() {
    //     const btn = this.setWaringJoinButton(); //
    //     if (!btn) return;

    //     btn.addEventListener("click", async () => {
    //         console.log("경고알람 메시지 인가자 등록 활성화.");
    //         try {
    //             alert("경고/알람 시스템 인가자 등록");
    //         } catch (err) {
    //             console.error("[경고/알람 시스템 인가자 등록 실패]", err);
    //         }
    //     });
    // }

    // async #sendWaringMessage() {
    //     try {            
    //         // 1. receivers.csv 파일 내용 읽기
    //         // 브라우저 환경이므로, 서버에서 파일을 제공하거나 
    //         // 해당 파일이 공용 경로에 있다고 가정하고 fetch를 사용합니다.
    //         const csvResponse = await fetch("./receivers.csv");
    //         if (!csvResponse.ok) {
    //             throw new Error(`Failed to fetch receivers.csv: ${csvResponse.statusText}`);
    //         }
    //         const csvText = await csvResponse.text();

    //         console.log("인가자 정보 읽기.",csvText);
    //         // 2. CSV 파싱 및 JSON 포맷 준비
    //         const result = [];
    //         const rows = csvText.trim().split('\n');
    //         rows.forEach((row, idx) => {
    //             // CSV는 쉼표로 구분되어 있다고 가정
    //             const columns = row.split(',').map(col => col.trim());
    //             if (columns.length >= 2) {
    //                 const dic = {
    //                     "Seq": `${idx + 1}`,
    //                     "Number": columns[1] // 전화번호
    //                 };
    //                 // Python 코드와 달리, JavaScript에서는 배열에 객체 자체를 저장 후 
    //                 // JSON.stringify로 전체를 직렬화하는 것이 더 일반적입니다.
    //                 result.push(dic);
    //             }
    //         });
    //         console.log("인가자 정보 읽기.",result);

    //         // 3. 현재 시간 포맷
    //         const now = new Date();
    //         const nowString = now.toLocaleString('ko-KR', {
    //             year: 'numeric', month: '2-digit', day: '2-digit',
    //             hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    //         });

    //         // 4. API 요청 Payload 구성
    //         const payload = {
    //             "MessageSubType": "1",
    //             "CallbackNumber": "15883391",
    //             "Message": {
    //                 "Content": `[경고알림].${nowString} - \n
    //                              - 수륙양용 지휘통제소에서 알립니다.\n
    //                              - 시스템경고/알림 메시지 송부 \n
    //                              - 임무 수행 경고 발생 \n`,
    //                 // Python 예제와 동일하게 JSON 문자열로 변환하여 전송
    //                 "Receivers": JSON.stringify(result)
    //             }
    //         };

    //         const headers = {
    //             // 'Authorization' 헤더는 보안상의 이유로 서버에서 처리하거나 
    //             // CORS 문제를 해결해야 할 수 있습니다. 
    //             // 일단 Python 코드와 동일하게 설정합니다.
    //             'Authorization': 'Basic Q1BTOTIwMDA1MTMxOFNSRlVGSDpTVks5MjAwMDUxMzE4REZNUUFK',
    //             'Content-Type': 'application/json'
    //         };

    //         // 5. 알림 확인 및 API 요청 (msvcrt.getch() 대체)
    //         if (confirm("알림을 보내시겠습니까?")) {
    //             console.log("알림 발송 시도:", result);

    //             const apiResponse = await fetch("https://api.communis.kt.com/cpaas/v1.0/CPaaS_sendSMS", {
    //                 method: "POST",
    //                 headers: headers,
    //                 body: JSON.stringify(payload)
    //             });

    //             const data = await apiResponse.json();

    //             console.log("API 응답:", data);
    //             if (apiResponse.ok && data.r === "ok") {
    //                 alert("경고/알람 메시지 전송 성공!");
    //             } else {
    //                 alert(`경고/알람 메시지 전송 실패: ${data.r || apiResponse.statusText}`);
    //             }
    //         } else {
    //             console.log("알림발송 미승인");
    //             alert("알림발송 미승인");
    //         }
    //     } catch (err) {
    //         console.error("waring message send err : ", err)
    //     }
    // }

    // ------------------------------
    //      Polling / Updates
    // ------------------------------

    #bindControlInterface() {
        try {
            const btn = this.connectControlInterfaceButton();
            if (!btn) return;

            btn.addEventListener("click", async () => {
                // 1. 중복 실행 확인
                if (this.c4i.isLooping) {
                    alert("이미 C4I 연동 루프가 실행 중입니다. (연결 상태를 확인하세요)");
                    console.log("[C4I] 현재 상태: 실행 중, IP:", this.c4i.options.hostname);
                    return;
                }

                console.log("C4I 체계 연동 시도.");
                try {
                    const isConfigLoaded = await this.c4i.loadConfig();
                    if (!isConfigLoaded) {
                        console.warn("설정 파일을 읽지 못해 기본 설정으로 진행합니다.");
                    }
                    const success = await this.c4i.connect();
                    if (success) {
                       alert(`C4I 연동 시작 (${this.c4i.options.hostname})`);
                        this.startC4IPolling(10000); // 연결 성공 시 송신 루프 시작
                    } else {
                        alert("C4I 체계 연동 실패.");
                    }
                } catch (error) {
                    alert("C4I 서버 연결에 실패했습니다. 서버 상태를 확인하세요.");
                    console.err("C4I 체계 연동 실패", err);
                }
            });
        } catch (error) {
            console.error("C4I 연동 중 예상치 못한 오류 발생:", error);
            alert("연동 오류: " + error.message);
        }
    }

    // 2. C4I 전용 폴링 시작 루틴
    startC4IPolling(intervalMs) {
        if (this.c4iPolling) return;
        if (intervalMs) this.c4iInterval = Math.max(200, intervalMs);
        this.c4iPolling = true;
        this.#c4iPollLoop();
    }

    // 3. 데이터 수집 및 송신 루프 (핵심 기능)
    async #c4iPollLoop() {
        console.log("[C4I] 반복 송신 루프 시작...");

        while (this.c4iPolling) {
            try {
                // 현재 선택된 유닛 인덱스 가져오기 (1-based)
                const selRes = await getMetadataByKey("currentSelectUnit");
                const unitIdx1 = ((selRes?.value ?? 0) | 0) + 1;

                // 병렬 데이터 수집 (status 및 detector)
                const [statusRes, detectorRes] = await Promise.all([
                    getMetadataByKey(`robot_${unitIdx1}.robot_status_data`),
                    getMetadataByKey(`robot_${unitIdx1}.dectector_data`)
                ]);

                // 데이터가 존재할 경우에만 전송 실행
                if (statusRes?.value) {
                    // this.c4i.sendFormattedData(unitIdx1, statusRes.value, detectorRes?.value);
                    // //this.c4i.sendRobotData(unitIdx1, statusRes.value, detectorRes?.value);
                    
                    //const status = resStatus.value;
                    const detector = detectorRes?.value || {};

                    // 데이터 포맷 생성
                    const now = new Date();
                    const ts = now.toISOString().replace('T', ' ').substring(0, 19);
                    const payload = `${ts}/${this.c4i.options.armycode}/${detector.class || '0'}/${detector.name || 'none'}/"latitude":${statusRes.value.latitude}, "longitude":${statusRes.value.longitude}\r\n`;

                    // 송신 및 수신 데이터 확인
                    await this.c4i.sendAndListen(payload);
                }

            } catch (err) {
                console.error("[C4I 루프 오류]", err);
            }
            // 주기 대기
            await new Promise(resolve => setTimeout(resolve, this.c4iInterval));
        }
    }

    // 4. 폴링 중지 기능
    stopC4IPolling() {
        this.c4iPolling = false;
        if (this.c4i.socket) this.c4i.socket.end();
        console.log("[C4I] Data Transmission Loop Stopped.");
    }

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
            const resOther = await getMetadataByKey(`robot_${i}.robot_status_data`);
            const statusOther = resOther?.value;
            if (statusOther && typeof statusOther === "object") {
                // ✅ 1-based 인덱스로 호출
                const center = centerSelected && (i === selected1);
                updateMapWithStatusData(i, statusOther, center);
            }
        }
    }

    async #updateRobotWaypointsDataToMap(centerSelected = false) {
        //const unitCountRes = await getMetadataByKey("numberOFUnits");
        //const unitCount = unitCountRes?.value ?? 0;

        const sel = await getMetadataByKey("currentSelectUnit");
        const selected0 = sel?.value ?? 0;
        const selected1 = selected0 + 1; // 1-based

        const wps = await _getWaypoints(selected1);
        //if (typeof wps?.lat !== "number" || typeof wps?.lng !== "number") return;
        if ((wps.length == 0) && (typeof wps !== "object" || typeof wps?.lng !== "object")) {
            _clearWaypointLayers();
            return;
        }
        await updateWaypointsForUnit(selected1);
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
