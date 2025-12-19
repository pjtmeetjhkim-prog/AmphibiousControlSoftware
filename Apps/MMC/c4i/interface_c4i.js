// c4iClient.js
// TCP 통신은 Node.js 런타임에서만 작동 유의.
//import fs from "fs-extra";
// import net from "node:net";
// import fs from "node:fs/promises"; // Promise 기반 fs 모듈 사용
// import path from "node:path";

export class C4IClient {
    constructor() {
        this.client = null;
        this.isConnected = false;
        this.options = {
            hostname: "127.0.0.1",
            //hostname: "192.168.50.100",
            port: 54435,
            armycode: "52S0001",
            timeoutMs: 10000
        };
        this.authToken = 7204;
        // this.authToken = localStorage.getItem('auth_token') || 7204;
        this.configPath = "C:/c4i_config.json"
    }

    // 설정 파일 로드 (config fetch/read)
    async loadConfig() {
        try {

            // MMS 서버의 API 호출 (상대경로 또는 절대경로)
            // const response = await fetch('/api/v1/mms/c4i-config');
            const response = await fetch('/api/v1/mms/c4i-config', {
                method: 'GET',
                headers: {
                    // 401 에러 해결을 위한 인증 헤더 추가
                    'auth-token': this.authToken
                }
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status} - 인증 실패 또는 파일 없음`)
                if (response.status === 401) {
                    throw new Error("인증 실패(401): 토큰을 확인하세요.");
                    throw new Error("Config API response not ok");
                }
            }

            const config = await response.json();

            // const rawData = await fs.readFile(this.configPath, 'utf8');
            // const config = JSON.parse(rawData);
            // const response = await fetch('./c4i_config.json');
            // const config = await response.json();

            this.options.hostname = config.c4i_ip || this.options.hostname;
            this.options.port = Number(config.c4i_port) || this.options.port;
            this.options.timeoutMs = Number(config.c4i_tcp_timeout_ms) || this.options.timeoutMs;
            console.log("[C4I] Config Loaded via API:", this.options);
            return true;
        } catch (err) {
            console.error("[C4I] Config Load Error (using default):", err);
            return false;
        }
    }

    // 서버 연결
    async connect1() {
        // 실제 Node.js 환경이라면 import net from 'net' 사용
        // 브라우저 환경이라면 서버측 Proxy가 필요합니다.
        console.log(`[C4I] Connecting to ${this.options.hostname}:${this.options.port}...`);

        // Mock-up: 실제 net.createConnection 로직 (Node.js 기준)
        /*
        this.client = net.createConnection({ port: this.options.port, host: this.options.hostname }, () => {
            this.isConnected = true;
            this.client.write('connected c4i client..\r\n');
        });
        */
        this.isConnected = true; // 테스트를 위해 true 설정
        return this.isConnected;
    }

    // // 데이터 포맷팅 및 송신
    // sendRobotData(unitIdx, statusData, detectorData) {
    //     if (!this.isConnected) return;

    //     const now = new Date();
    //     const timestamp = now.toLocaleString('ko-KR', {
    //         year: 'numeric', month: '2-digit', day: '2-digit',
    //         hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    //     }).replace(/\. /g, '-').replace('.', '');

    //     // 요구사항 포맷: YYYY-MM-DD, HH:mm:ss/부대코드/class/name/"latitude":lat, "longitude":lng
    //     const lat = statusData?.latitude ?? 0;
    //     const lng = statusData?.longitude ?? 0;
    //     const emeid = detectorData?.class ?? "0";
    //     const emename = detectorData?.name ?? "unknown";

    //     // 요구된 포맷: 날짜,시간/부대코드/class/name/"latitude":값, "longitude":값
    //     const payload = `${timestamp}/${this.options.armycode}/${emeid}/${emename}/"latitude":${lat}, "longitude":${lng}\r\n`;

    //     console.log("[C4I SEND]", payload.trim());
    //     this.socket.write(payload);
    //     // this.client.write(payload);
    // }

    // 데이터 송신 (MMS 서버의 브로드캐스트나 특정 API 활용)
    async sendFormattedData(unitIdx, statusData, detectorData) {
        if (!this.isConnected) return;

        const now = new Date();
        const timestamp = now.toLocaleString('ko-KR', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
        }).replace(/\. /g, '-').replace('.', '');

        // 요구사항 포맷: YYYY-MM-DD, HH:mm:ss/부대코드/class/name/"latitude":lat, "longitude":lng
        const lat = statusData?.latitude ?? 0;
        const lng = statusData?.longitude ?? 0;
        const emeid = detectorData?.class ?? "0";
        const emename = detectorData?.name ?? "unknown";

        const payload = {
            type: "C4I_DATA",
            data: `${timestamp}/${this.options.armycode}/${emeid}/${emename}/"lat:"${lat},"log:"${lng}\r\n`
        };

        try {
            // MMS 서버로 데이터 전송 (그러면 서버가 TCP로 C4I에 쏴줌)
            const response = await fetch('/api/v1/mms/broadcast', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'auth-token': this.authToken
                },
                body: JSON.stringify(payload)
            });
            if (response.status === 401) console.error("데이터 송신 인증 실패");
        } catch (error) {
            console.error("데이터 송신 중 에러:", e);
        }
    }

    /** 서버에 TCP 연결 요청 */
    async connect() {
        try {
            // TCP 서버(MMS)에 C4I 서버로 접속하라는 명령 전달
            const response = await fetch('/api/v1/mms/broadcast', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'auth-token': this.authToken
                },
                body: JSON.stringify({
                    cmd: "C4I_CONNECT",
                    target_ip: this.options.hostname,
                    target_port: this.options.port
                })
            });

            if (response.ok) {
                this.isConnected = true;
                console.log("[C4I] 서버 연결 명령 송신 완료");
                return true;
            }
            return false;
        } catch (error) {
            console.error("[C4I] 연결 요청 중 오류:", error);
            return false;
        }
    }

    async sendAndListen(payload) {
        if (!this.isConnected) return;

        try {
            const response = await fetch('/api/v1/mms/broadcast', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'auth-token': this.authToken 
                },
                body: JSON.stringify({
                    cmd: "C4I_SEND_DATA",
                    payload: payload
                })
            });

            // 서버 측 콘솔에서 [C4I-RECEIVE] 로그가 찍히므로 
            // 클라이언트는 송신 성공 여부만 확인합니다.
            const result = await response.json();
            if (result.r === "ok") {
                console.log("[C4I-TX] Data Sent Successfully");
            } else {
                console.warn("[C4I-TX] Send Failed - Check Connection");
                this.isConnected = false; // 연결 끊김으로 간주
            }
        } catch (error) {
            console.error("[C4I-CLIENT] Network Error:", error);
        }
    }

    // /** 데이터 송신 및 수신 로그 시뮬레이션 */
    // async sendAndListen(payload) {
    //     if (!this.isConnected) return;

    //     try {
    //         const response = await fetch('/api/v1/mms/broadcast', {
    //             method: 'POST',
    //             headers: { 
    //                 'Content-Type': 'application/json',
    //                 'auth-token': this.authToken 
    //             },
    //             body: JSON.stringify({
    //                 cmd: "C4I_SEND_DATA",
    //                 payload: payload
    //             })
    //         });

    //         // 테스트용: 서버로부터 되돌아오는 데이터(수신 데이터) 확인
    //         const result = await response.json();
    //         if (result.receivedData) {
    //             console.log(`%c[C4I 수신 데이터]: ${result.receivedData}`, "color: #00ff00; font-weight: bold;");
    //         }
            
    //         console.log("[C4I 송신 성공]:", payload.trim());
    //     } catch (error) {
    //         console.warn("[C4I 송신/수신 오류]:", error);
    //     }
    // }

    // TCP 소켓 연결 실행
    // connect() {
    //     // 실제로는 MMS 서버가 TCP Client 역할을 수행하도록 
    //     // 명령을 보내는 API를 호출해야 합니다.
    //     console.log("[C4I] 서버를 통한 TCP 연결 요청 대기...");
    //     this.isConnected = true;
    //     return true;

    //     // return new Promise((resolve) => {

    //     //     if (this.socket) this.socket.destroy();

    //     //     this.socket = net.createConnection({
    //     //         host: this.options.hostname,
    //     //         port: this.options.port,
    //     //         timeout: this.options.timeoutMs
    //     //     }, () => {
    //     //         this.isConnected = true;
    //     //         console.log("[C4I] 서버 연결 성공");
    //     //         this.socket.write('connected c4i client..\r\n'); // 초기 접속 메시지
    //     //         resolve(true);
    //     //     });

    //     //     this.socket.on('error', (err) => {
    //     //         console.error("[C4I] 소켓 오류:", err.message);
    //     //         this.isConnected = false;
    //     //         resolve(false);
    //     //     });

    //     //     this.socket.on('end', () => {
    //     //         this.isConnected = false;
    //     //         console.log("[C4I] 서버와 연결이 종료되었습니다.");
    //     //         resolve(false);
    //     //     });
    //     // });
    // }
}