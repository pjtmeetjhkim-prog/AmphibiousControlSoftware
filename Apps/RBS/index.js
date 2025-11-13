// #############################
// ## filename : index.js
// ## 설명 : 부팅 시 metadata.json 로딩, 로봇 시뮬레이터 구동
// ## 작성자 : gbox3d 
// ## 위 주석은 수정하지 마세요.
// #############################

import express from "express";
import dotenv from "dotenv";


// 경로 주의: tcpServer.js가 현재 프로젝트 루트에 있다면 아래처럼 import 하세요.
// (기존에 "./network/tcpServer.js" 였다면, 실제 파일 위치에 맞게 경로만 수정)
import { TcpServer } from "./api/network/tcpServer.js";

import { Robot } from "./api/simulator/robot.js";

async function main() {
  dotenv.config({ path: ".env" });
  console.log(`run mode : ${process.env.NODE_ENV}`);

  // 1) TCP 서버 시작
  const tcp = new TcpServer({
    ip: process.env.TCP_IP ?? "127.0.0.1",
    port: Number(process.env.TCP_PORT ?? 8283),
    timeoutMs: Number(process.env.TCP_TIMEOUT_MS ?? 10000),
  });
  await tcp.start();

  // 2) metadata.json 로딩 (존재하면 가져오고, 없으면 빈 상태 유지)
  //    tcpServer에는 이미 loadMetadata()/saveMetadata()와 내부 메모리 this.metadataJson이 있습니다.
  //    (아래 구현은 그 API를 활용합니다)
  const metaLoad = tcp.loadMetadata({ merge: false });
  if (metaLoad.ok) {
    console.log(`[META] loaded: ${metaLoad.path} (mode=${metaLoad.mode})`);
  } else {
    console.log(`[META] no file yet: ${metaLoad.path} (start with empty metadata)`);
  }

  // geo 기준점 준비 (metadata.geo에 저장)
  if (!tcp.metadataJson.geo) {
    tcp.metadataJson.geo = {
      originLon: 127.0,
      originLat: 37.5,
      metersPerDeg: 111320
    };
  }

  // 로봇 생성 시 기준점 전달
  const seed = { ...(tcp.metadataJson.robot ?? {}), ...(tcp.metadataJson.geo ?? {}) };
  const robot = Robot.fromMetadata({ robot: seed, geo: tcp.metadataJson.geo });

  // ✅ control_robot 콜백 등록
  tcp.registerJsonHandler("control_robot", async (obj, { tcp }) => {

    // 예상 payload:
    // { cmd:"control_robot", action:"set_mode"|"set_velocity"|"teleport"|"stop"|"apply_patch", data:{...}, token?:any }

    const action = String(obj.action || "").toLowerCase();
    const data = (typeof obj.data === "object" && obj.data) ? obj.data : {};
    const token = obj.token;

    try {

      switch (action) {
        case "set_actuators": {
          const { WheelSpeed, WheelAngle, WheelOmega } = data;
          robot.setActuators({ WheelSpeed, WheelAngle, WheelOmega });
          break;
        }
        case "apply_patch": {
          // 차량 파라미터/상태 변경(옵션)
          robot.applyPatch(data);
          // console.log(`[ROBOT] applied patch:`, data);
          break;
        }
        default:
          // 다른 액션은 기존처럼 확장 가능 (예: emergency_stop 등)
          break;
      }

      // 상태를 metadata에 반영 & 저장(선택)
      tcp.metadataJson.robot = robot.toJSON();
      // tcp.saveMetadata(); // 필요 시 활성화

      // UI/다중 클라 동기화용 PUSH 패킷 반환
      return {
        ackStatus: undefined, // 기본 SUCCESS
        push: {
          cmd: "robot_update",
          token,                   // 클라 상호작용 매칭용(선택)
          data: tcp.metadataJson.robot
        }
      };
    } catch (e) {
      // 에러 시: 예외 ACK
      return { ackStatus: 0xEE /* ERR_EXCEPTION 같은 값으로 맞춰도 됨 */ };
    }
  });

  // 4) 시뮬레이션 루프 (기본 30Hz). 로봇 상태를 metadata에 반영하고, 주기적으로 브로드캐스트
  const SIM_HZ = Number(process.env.SIM_HZ ?? 30);
  const BROADCAST_HZ = Number(process.env.BROADCAST_HZ ?? 5);

  let lastTs = Date.now();
  let broadcastAccumulator = 0;

  const timer = setInterval(async () => {
    const now = Date.now();
    const dt = Math.max(0, (now - lastTs) / 1000);
    lastTs = now;

    // 시뮬 step
    robot.update(dt);

    // metadata 반영
    tcp.metadataJson.robot = robot.toJSON();

    // 저주파 브로드캐스트(상태 델타 알림 등)
    broadcastAccumulator += dt;
    if (broadcastAccumulator >= (1 / BROADCAST_HZ)) {
      broadcastAccumulator = 0;
      try {
        await tcp.broadcastJson({
          cmd: "robot_update",
          data: tcp.metadataJson.robot,
        });
      } catch { }
    }
  }, 1000 / SIM_HZ);

  // 5) 안전 종료: 메타데이터 저장 후 종료
  const graceful = async () => {
    console.log("\n> shutting down...");
    clearInterval(timer);
    try {
      const saved = tcp.saveMetadata();
      console.log(`[META] saved -> ${saved.path}`);
      await tcp.broadcastJson({ cmd: "server_shutdown" });
    } catch { }
    await tcp.stop();
    process.exit(0);
  };

  process.on("SIGINT", graceful);
  process.on("SIGTERM", graceful);


  // Express 앱 생성 (필요 시 활용)
  const app = express();
  // auth 미들웨어 … (기존 코드)
  app.use("/api", (req, res, next) => {
    const authToken = req.header("auth-token");
    if (authToken === process.env.AUTH_TOKEN) next();
    else res.status(401).json({ r: "err", msg: "auth fail" });
  });

  console.log(`auth token ${process.env.AUTH_TOKEN}`);

  app.use(express.static("./www"));
  app.use((req, res) => res.status(404).send("oops! resource not found"));
  
  const httpPort = Number(process.env.WEB_PORT ?? 8284);
  app.listen(httpPort, () => {
    // console.log(`server run at : ${httpPort}`);
    console.log(`[WEB] webUI url : http://localhost:${httpPort}`);
  });


}

main().catch((err) => {
  console.error("Fatal Error:", err);
  process.exit(1);
});
