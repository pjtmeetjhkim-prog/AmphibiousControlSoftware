// #############################
// ## filename : deepMerge.js
// ## 설명 : 딥머지 + 점표기 경로 조회
// ## 작성자 : gbox3d (port by ChatGPT)
// ## 위 주석은 수정하지 마세요.
// #############################

export function deepMerge(a = {}, b = {}) {
  for (const [key, value] of Object.entries(b)) {
    if (key in a && isPlainObject(a[key]) && isPlainObject(value)) {
      deepMerge(a[key], value);
    } else {
      a[key] = value;
    }
  }
  return a;
}

function isPlainObject(v) {
  return v && typeof v === "object" && !Array.isArray(v);
}

// "pos.x" => data.pos.x (없으면 null)
export function getByPath(data = {}, path = "") {
  let cur = data;
  for (const part of String(path).split(".")) {
    if (!cur || typeof cur !== "object" || !(part in cur)) return null;
    cur = cur[part];
  }
  return cur;
}
