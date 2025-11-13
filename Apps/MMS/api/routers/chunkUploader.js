import express from 'express';
import fs from 'fs-extra';
import path from 'path';
import dotenv from 'dotenv';

dotenv.config(); // .env 로드
const router = express.Router();

// 각종 경로 설정 (없으면 만들어 준다고 가정)
const tempDir = path.resolve(process.env.UPLOAD_TEMP || './temp');
const finalDir = path.resolve(process.env.UPLOAD_PATH || './uploads');

fs.ensureDirSync(tempDir);
fs.ensureDirSync(finalDir);

router.use(express.raw({ limit: '100mb' })) // 100MB 제한


router.route('/').get((req, res) => {
    res.json({ r: 'ok', info: 'chunk uploader' })
})

// ─────────────────────────────────────────────────────────────────────────────
// RAW 바디로 조각 데이터를 받기 위해 express.raw 미들웨어 설정
// Content-Type 은 보통 "application/octet-stream" 이나 파일 MIME 타입
// ─────────────────────────────────────────────────────────────────────────────
router.post('/chunk', async (req, res) => {
  try {
    // 1) 헤더 분석
    const uploadName = decodeURIComponent(req.headers['upload-name'] || 'no_name');
    const fileSize = parseInt(req.headers['file-size'] || '0', 10);
    const chunkStart = parseInt(req.headers['chunk-start'] || '0', 10);
    const chunkSize = parseInt(req.headers['chunk-size'] || '0', 10);

    // 기본 검증
    if (!uploadName || !fileSize || chunkSize <= 0) {
      return res.status(400).json({ 
        r: 'error', 
        msg: 'Invalid headers: upload-name, file-size, chunk-start, chunk-size' 
      });
    }

    // 2) 조각 파일 저장 경로 결정
    //    예: tempDir/원본파일이름/원본파일이름_chunkStart.part
    //    폴더 구분 안 하셔도 되지만, 되도록이면 파일별 폴더를 두는 편이 안전
    const fileFolder = path.join(tempDir, uploadName);
    fs.ensureDirSync(fileFolder); 
    const chunkPath = path.join(fileFolder, `${uploadName}_${chunkStart}.part`);

    // 3) req.body 가 조각 바이너리이므로 그대로 쓰기
    fs.writeFileSync(chunkPath, req.body);
    console.log(`> chunk saved: ${chunkPath} (${req.body.length} bytes)`);

    // 4) 마지막 조각인지 확인
    //    "마지막 조각"의 기준: (chunkStart + chunkSize) == fileSize
    //    ※ 더 견고하게 하려면, 각 조각 개수나 파일크기 등을 비교해서 결정
    const isLastChunk = (chunkStart + chunkSize >= fileSize);

    // ─────────────────────────────────────────────────────────────────────────
    // [선택] 마지막 조각이면, tempDir 에 저장된 .part 들을 모아 최종 파일을 생성
    // ─────────────────────────────────────────────────────────────────────────
    if (isLastChunk) {
      // 4-1) tempDir/업로드파일이름 폴더 안의 .part 파일들을 chunk-start 기준으로 정렬
      const partFiles = fs.readdirSync(fileFolder)
        .filter((f) => f.endsWith('.part'))
        .sort((a, b) => {
          // 파일명에 들어있는 chunkStart 숫자로 정렬
          const getStart = (name) => parseInt(name.split('_').pop().split('.part')[0], 10);
          return getStart(a) - getStart(b);
        });

      // 4-2) 최종 파일 경로 지정
      const finalPath = path.join(finalDir, uploadName);
      console.log(`> Start merging to ${finalPath}`);

      // 4-3) 각 조각을 순차적으로 append
      // fs.createWriteStream을 열고, partFiles 각각을 Stream으로 붙이는 방법도 가능
      // 여기서는 간단히 sync로 예시
      fs.writeFileSync(finalPath, ''); // 빈 파일 생성
      partFiles.forEach((partFile) => {
        const partFilePath = path.join(fileFolder, partFile);
        const data = fs.readFileSync(partFilePath);
        fs.appendFileSync(finalPath, data);
      });

      console.log(`> Merged file completed: ${finalPath}`);

      // 4-4) 머지 완료 후, 임시 폴더 삭제(선택)
      fs.removeSync(fileFolder);

      return res.json({ 
        r: 'ok', 
        msg: 'Last chunk received. Merge completed.', 
        finalPath 
      });
    }

    // 마지막 조각이 아니면 조각 저장만 완료
    return res.json({ 
      r: 'ok', 
      msg: 'Chunk received', 
      chunkPath, 
      nextPos: chunkStart + chunkSize 
    });

  } catch (err) {
    console.error(err);
    return res.status(500).json({ r: 'error', msg: err.toString() });
  }
});

export default router;
