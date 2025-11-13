// filename: www/index.js
// 이주석은 지우지 하세요.


import {
    getState,
    getMetadata,
    setMetadata,
    mergeMetadata,
    getMetadataByKey,
    saveMetadata,
    loadMetadata,
    deleteMetadata,
    setBaseHost,
    setAuthToken
} from "./libs/apiHelper.js";


function syntaxHighlight(json) {
    json = JSON.stringify(json, null, 2);
    json = json.replace(
        /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
        (match) => {
            let cls = "number";
            if (/^"/.test(match)) {
                if (/:$/.test(match)) cls = "key";
                else cls = "string";
            } else if (/true|false/.test(match)) cls = "boolean";
            else if (/null/.test(match)) cls = "null";
            return `<span class="${cls}">${match}</span>`;
        }
    );
    return json;
}


const DEFAULT_MMS_CONFIG = {
    apiIp: ".",
    apiPort: 8080,
    authToken: 7204,
    init: true
};


async function main() {

    const mmsConfig = JSON.parse(localStorage.getItem("mmsConfig")) || {};    

    console.log("MMS CONFIG LOAD", mmsConfig);

    if(!mmsConfig.init) {
        // 초기화 작업 수행
        localStorage.setItem("mmsConfig", JSON.stringify(DEFAULT_MMS_CONFIG));
        console.log("MMS CONFIG INITIALIZED");        

        // 페이지 새로고침
        window.location.reload();
        return;
    }

    const inputHost = document.getElementById("input-host");
    const inputPort = document.getElementById("input-port");
    const inputAuthToken = document.getElementById("input-auth-token");

    inputHost.value = mmsConfig.apiIp;
    inputPort.value = mmsConfig.apiPort;
    inputAuthToken.value = mmsConfig.authToken;


    //init API host and auth token
    const host = inputHost.value;
    const port = inputPort.value;
    const authToken = inputAuthToken.value;

    // 기존 로직 유지: 최종적으로 '.'(상대경로) 사용
    if (host === ".") {
        setBaseHost(host);
    } else if (host === "") {
        const _url = new URL(window.location.href);
        setBaseHost(`${_url.protocol}//${_url.hostname}:${port}`);
    } else {
        setBaseHost(`http://localhost:${port}`);
    }    
    setAuthToken(authToken);

    

    const dumpTextOut = document.getElementById("dumpTextOut");

    document.getElementById("btndump").addEventListener("click", async () => {
        const data = await getMetadata();
        console.log("=== METADATA DUMP ===");
        console.log(data);

        dumpTextOut.innerHTML = `<pre>${syntaxHighlight(data)}</pre>`;

    });

    //-------------------------

    document.getElementById("btn-set-metadata").addEventListener("click", async () => {
        const key = document.getElementById("input-metadata-key").value;
        const value = document.getElementById("input-metadata-value").value;
        const res = await setMetadata(key, value);
        console.log("SET METADATA", key, value, res);
    });



}

export default main;
