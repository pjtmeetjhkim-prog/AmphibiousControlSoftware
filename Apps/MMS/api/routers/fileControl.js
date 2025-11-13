import express from 'express'
import fs from "fs-extra";
import path from 'path';

const router = express.Router()

//cors 정책 설정 미들웨어 
router.use((req, res, next) => {

    res.set('Access-Control-Allow-Origin', '*'); //cors 전체 허용
    res.set('Access-Control-Allow-Methods', '*');
    res.set("Access-Control-Allow-Headers", "*");

    console.log(req.header('content-type'))
    console.log(`check file control mw auth ${req.originalUrl}`)
    next()
})

//raw 바디 미들웨어, content-type : application/octet-stream 일 경우 req.body로 받아온다.
router.use(express.raw({ limit: '1gb' })) //파일용량 1기가 바이트로 제한
router.use(express.json()) //json 바디 미들웨어, content-type : application/json 일 경우 req.body로 받아온다.
router.use(express.text()) //text 바디 미들웨어, content-type : application/text 일 경우 req.body로 받아온다.


router.route('/').get((req, res) => {
    res.json({ r: 'ok', info: 'file control system' })
})

router.route('/filelist').get((req, res) => {

    let _cwd = req.query.cwd
    let _files = []
    fs.readdirSync(_cwd).forEach(file => {
        console.log(file);
        _files.push(file)
    });
    res.json({ r: "ok", files: _files });
})

router.route('/write').post((req, res) => {

    try {
        let _name = req.headers['write-name']
        let _cwd = req.headers['write-directory']

        fs.writeFileSync(`${_cwd}/${_name}`, req.body)
        console.log(req.body)
        res.json({ r: 'ok', size: req.body.length })
    }
    catch (e) {
        console.log(e)
        let result = { result: 'err', err: e }
        res.json(result)
    }

})

router.route('/read').post((req, res) => {

    console.log(req.body)


    try {

        res.set('full-path', path.resolve(req.body.path))

        // res.json({r:'ok',path: path.resolve(req.body.path) })

        res.sendFile(`${path.resolve(req.body.path)}/${req.body.file}`)
    }
    catch (e) {
        console.log(e)
        let result = { result: 'err', err: e }
        res.json(result)
    }
})

router.route('/getVideo').get((req, res) => {
    try {
        // query 파라미터로 파일 경로/이름 받기
        // 예: /api/v1/read?file=video.mp4&path=./uploads
        const { file, path: dirPath } = req.query;
        if (!file) {
          return res.status(400).send('file query param missing');
        }
        const fullPath = path.join(path.resolve(dirPath || '.'), file);
    
        console.log('Video request:', fullPath);
        // res.sendFile는 기본적으로 Range 요청(206 Partial Content)을 어느 정도 지원
        return res.sendFile(fullPath, (err) => {
          if (err) {
            console.error(err);
            return res.status(500).send(err.toString());
          }
        });
      } catch (err) {
        console.error(err);
        res.status(500).send(err.toString());
      }

});

//delete file
router.route('/delete').post((req, res) => {
    try {
        let _path = req.body.path
        let _file = req.body.file

        fs.unlinkSync(`${_path}/${_file}`)
        res.json({ r: 'ok', file: _file })
    }
    catch (e) {
        console.log(e)
        let result = { result: 'err', err: e }
        res.json(result)
    }
})


//파일 업로더 
//application/octet-stream 는 raw body 파서에 의해 처리되므로(데이터 원격 저장용도) , 이것을제외한 모든 형식의 데이터가 업로딩된다. 
router.route('/upload').post((req, res) => {
    try {

        let _path = process.env.UPLOAD_PATH

        //없으면 만들기 
        if (!fs.existsSync(_path)) {
            // Do something
            console.log(`${_path} not exists and create it`)
            fs.mkdirSync(_path);
        }

        let file_size = parseInt(req.headers['file-size'])
        let uploadName = decodeURIComponent(req.headers['upload-name']);

        let filepath = `${_path}/${uploadName}`;
        console.log(`start write file path : ${filepath}, file size :${file_size}`);

        //파일 오픈 
        let fd = fs.openSync(filepath, "w");
        let _index = 0;

        //포스트는 데이터가 조각조각 들어 온다.
        req.on('data', (data) => {
            _index += data.length;
            console.log(`data receive : ${data.length} , ${_index}`);
            fs.writeSync(fd, data);
        });

        req.on('end', () => {
            console.log(`data receive end : ${_index}`);
            fs.closeSync(fd);
            // let result = { result: 'ok', fn: filepath }
            // res.end(JSON.stringify(result));
            res.json({ r: 'ok', size: _index, fn: filepath })
        })
    }
    catch (e) {
        console.log(e)
        let result = { result: 'err', err: e }
        // res.end(JSON.stringify(result));
        res.json(result)
    }
})

export default router