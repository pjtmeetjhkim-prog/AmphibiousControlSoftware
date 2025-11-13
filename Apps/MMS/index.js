import express from "express";
import dotenv from "dotenv";
import fs from "fs-extra";

import fileControl from "./api/routers/fileControl.js";
import chunkUploader from "./api/routers/chunkUploader.js";
import router_missionManager from "./missionManager/router.js";

//TCP 서버
import { TcpServer } from "./missionManager/tcpServer.js";

async function main() {
  dotenv.config({ path: ".env" });
  console.log(`run mode : ${process.env.NODE_ENV}`);

  // 업로드 경로 보장
  {
    const created = fs.ensureDirSync(process.env.UPLOAD_PATH);
    if (created) console.log(`${created} created`);
  }

  // 1) TCP 서버 먼저 시작(환경변수 -> 주입)
  const tcp = new TcpServer({
    ip: process.env.TCP_IP ?? "127.0.0.1",
    port: Number(process.env.TCP_PORT ?? 8282),
    timeoutMs: Number(process.env.TCP_TIMEOUT_MS ?? 10000),
  });
  await tcp.start();

  {
    const res = await tcp.loadMetadata(); // 메타데이터 로드

    if (res.ok == true) {      
      console.log(`metadata mode : ${res.mode}`);
      console.log(`path : ${res.path}`);
    }
  }
  

  // 2) Express 앱
  const app = express();

  // 필요하면 라우터에서 tcp 인스턴스 접근 가능
  app.locals.tcp = tcp;

  // auth 미들웨어 … (기존 코드)
  app.use("/api", (req, res, next) => {
    const authToken = req.header("auth-token");
    if (authToken === process.env.AUTH_TOKEN) next();
    else res.status(401).json({ r: "err", msg: "auth fail" });
  });

  console.log(`auth token ${process.env.AUTH_TOKEN}`);

  app.use("/api/v1/fc", fileControl);
  app.use("/api/v1/uploader", chunkUploader);
  app.use("/api/v1/mms", router_missionManager);

  if (process.env.PATH_ROUTER) {
    try {
      const _pathRouters = await fs.readJson(process.env.PATH_ROUTER);
      for (const it of _pathRouters) {
        app.use("/" + it.name, express.static(it.path));
        console.log(`${it.name} : ${it.path}`);
      }
      console.log("static router setup complete");
    } catch (err) {
      console.log(err);
    }
  }

  app.use("/uploads", express.static(process.env.UPLOAD_PATH));
  console.log(`upload path : ${process.env.UPLOAD_PATH}`);

  app.use("/www", express.static("./api/www"));
  app.use("/libs", express.static("./api/www/libs"));
  
  app.use(express.static(process.env.STATIC_ASSET));

  app.use((req, res) => res.status(404).send("oops! resource not found"));

  const httpPort = Number(process.env.PORT ?? 3000);
  app.listen(httpPort, () => {
    console.log(`server run at : ${httpPort}`);
    console.log(`webUI url : http://localhost:${httpPort}`);
  });

  // 그레이스풀 종료
  process.on("SIGINT", async () => {
    console.log("\n> shutting down...");
    try { await tcp.broadcastJson({ cmd: "server_shutdown" }); } catch {}
    await tcp.stop();
    process.exit(0);
  });
}

main();
