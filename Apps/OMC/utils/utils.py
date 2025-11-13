"""
filename: utils.py
author: gbox3d

위 주석을 수정하지 마시오
"""

import shlex, json, re

def _coerce_value(v: str):
    """문자열을 bool/int/float/JSON로 자연 변환"""
    lv = v.lower()
    if lv in ("true", "false"):
        return lv == "true"
    if lv in ("null", "none"):
        return None
    # JSON 객체/배열 시도
    if (lv.startswith("{") and lv.endswith("}")) or (lv.startswith("[") and lv.endswith("]")):
        try:
            return json.loads(v)
        except Exception:
            pass
    # 숫자 시도
    try:
        if re.fullmatch(r"[+-]?\d+", v):
            return int(v)
        if re.fullmatch(r"[+-]?\d*\.\d+", v):
            return float(v)
    except Exception:
        pass
    # 콤마 리스트 "a,b,c" → ["a","b","c"]
    if "," in v and not re.search(r"\s", v):
        return [ _coerce_value(x) for x in v.split(",") ]
    return v

def _parse_tokens(tokens):
    """
    key=value, --key value, --flag, -k v (간단), 위치 인자까지 파싱
    반환: (positionals:list, options:dict)
    """
    pos = []
    opts = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.startswith("--"):
            key = t[2:]
            # --flag (불리언 토글)
            if i+1 >= len(tokens) or tokens[i+1].startswith("-") or "=" in tokens[i+1]:
                opts[key] = True
                i += 1
                continue
            # --key value
            val = _coerce_value(tokens[i+1])
            opts[key] = val
            i += 2
        elif t.startswith("-") and len(t) > 1 and not "=" in t:
            key = t[1:]
            if i+1 < len(tokens) and not tokens[i+1].startswith("-"):
                val = _coerce_value(tokens[i+1])
                opts[key] = val
                i += 2
            else:
                opts[key] = True
                i += 1
        elif "=" in t:
            k, v = t.split("=", 1)
            opts[k] = _coerce_value(v)
            i += 1
        else:
            pos.append(_coerce_value(t))
            i += 1
    return pos, opts

def parse_command_line(cmdline: str):
    """
    명령줄 구문 분석
    반환: (positionals:list, options:dict)
    """

    parts = shlex.split(cmdline)  # 따옴표/공백 안전 토큰화
    cmd = str(parts[0]).lower() if parts else ""
    args = parts[1:]
    pos, opts = _parse_tokens(args)

    return cmd, pos, opts
