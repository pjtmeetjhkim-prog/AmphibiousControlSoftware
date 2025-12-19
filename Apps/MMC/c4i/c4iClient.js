import net from "node:net";
import fs from "node:fs";
import path from "node:path";

const c4i_options = {
    hostname: "127.0.0.1",
    port: 54435,
    timeoutMs: 10000,
    armycode: "52S0001"
}

export class C4I_CLIETN {
    constructor(c4i_options = {}) {
        this.ip = c4i_options.ip ?? "127.0.0.1";
        this.port = Number(c4i_options.port ?? 8282);
        this.timeoutMs = Number(c4i_options.timeoutMs ?? 10_000);
        this.server = null;
        this.sockets = new Set();

        this.c4i_client = undefined; // 초기화 전
        // 전역 상태
        this.metadataJson = {};

        // 부팅 시각
        this.bootTsSec = Math.floor(Date.now() / 1000);
    }
}

async function getParamConfig(param) {
    fs.readFile('./c4i_config.json', 'utf8', (err, data) => {
        if (err) {
            console.error("파일 읽기 오류:", err);
            return;
        }
        try {
            const jsonData = JSON.parse(data); // JSON 문자열을 객체로 변환

            console.log("읽어온 JSON 데이터:", jsonData);
            console.log("타입:", typeof jsonData); // 'object' 또는 'array'

            if (param != null) {
                param.hostname = jsonData.c4i_ip ?? "127.0.0.1";
                param.port = Number(jsonData.c4i_port ?? 54435);
                param.timeoutMs = Number(jsonData.c4i_tcp_timeout_ms ?? 600000);
            }
            else {
                console.error("JSON 파싱 오류:", parseError);
            }

        } catch (parseError) {
            console.error("JSON 파싱 오류:", parseError);
        }
    });
}

async function Connect(param, client) {
    // 3. TCP 클라이언트 소켓 생성 및 서버 접속
    // const net = require('net');
    client = net.createConnection(param, () => {
        // 연결 성공 시 실행되는 콜백 함수
        console.log('C4I 서버에 연결되었습니다!');
        console.log(`{Link: 서버 주소: ${param.hostname}, 포트: ${param.port} }`);

        // 서버로 데이터 보내기 (메시지 전송)
        client.write('connected c4i client..\r\n');
        client.write('DataFormat [부대코드/위험식별코드/식별명/로봇위치정보]\r\n');
    });
}

function getToday() {
    const options = {
        timeZone: 'Asia/Seoul',
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: 'numeric',
        minute: 'numeric',
        second: 'numeric',
        hour12: false // Use 24-hour format
    };
    const formatter = new Intl.DateTimeFormat('en-CA', options);
    const utcPlus8Time = formatter.format(Date.now());
    // var date = new Date();
    // var year = date.getFullYear();
    // var month = ("0" + (1 + date.getMonth())).slice(-2);
    // var day = ("0" + date.getDate()).slice(-2);

    return utcPlus8Time;
    return year + "-" + month + "-" + day;
}

async function main() {
    getParamConfig(c4i_options);
    //Connect(c4i_options, this.c4i_client);

    const c4i_client = net.createConnection(c4i_options, () => {
        c4i_client.setEncoding('utf8');
        // 연결 성공 시 실행되는 콜백 함수
        console.log('C4I 서버에 연결되었습니다!');
        console.log(`{Link: 서버 주소: ${c4i_options.hostname}, 포트: ${c4i_options.port} }`);

        // 서버로 데이터 보내기 (메시지 전송)
        c4i_client.write('connected c4i client..\r\n');
        c4i_client.write('DataFormat [armycode/emeidcode/emename/robotlocation]\r\n');
    });

    // 4. 서버로부터 데이터 수신 이벤트 처리 ('data' 이벤트)
    c4i_client.on('data', (data) => {
        console.log(`{Link: C4I 서버로부터 받은 메시지: ${data.toString()} }`);
    });

    // 5. 연결 종료 이벤트 처리 ('end' 이벤트)
    c4i_client.on('end', () => {
        console.log('C4I 서버와의 연결이 종료되었습니다.');
    });

    // 6. 오류 발생 이벤트 처리 ('error' 이벤트)
    c4i_client.on('error', (err) => {
        console.error(`{Link: 연결 오류 발생: ${err.message} }`);
    });

    // 7. 클라이언트에서 연결 종료 요청 (예: 콘솔에서 'exit' 입력 시)
    // process.stdin을 사용하여 사용자 입력을 받고 서버에 전송하거나 연결을 종료할 수 있습니다.
    process.stdin.on('data', (input) => {
        const message = input.toString().trim();
        if (message === 'exit') {
            console.log('클라이언트 연결 종료...');
            c4i_client.end(); // 서버 연결을 닫음
        } else {

            const str = getToday() + "/" + c4i_options.armycode + "/" + message + " \r\n";
            c4i_client.write(str); // 입력받은 메시지 서버로 전송
        }
    });
}

main();

// ------------------------------
// Default entry for compatibility
// ------------------------------
async function main() {
    const app = new MMCApp();
    await app.start();
}

export default main;