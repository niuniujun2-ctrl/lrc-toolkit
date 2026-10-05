# -*- coding: utf-8 -*-
"""lx 歌词库重制辅助库 —— 读取 / 重建 / 写回 / 校验

把本文件放进歌词库的 _rebuild_work/ 下（或用 sys.path 指向它所在目录），然后：
    import os
    os.environ["LRC_WS"] = r"D:/music/歌词库"      # 歌词库根目录（不设则取当前工作目录）
    import rebuild_lib as rl
    out, stats = rl.render("曲名.lrc", TR, fmt="block", note_idx={...})
    assert not stats["missing"], stats["missing"]   # missing==0 才允许写回
    rl.commit("曲名.lrc", out, stats["bom"])        # 自动备份 _orig_lrc/<名>.pre-v2.lrc

作者: AI 助手「苍娜」(Hermes Agent)｜人类监督: niuniujun2-ctrl
"""
import re, os, shutil

WS = os.environ.get("LRC_WS") or os.getcwd()      # 歌词库根目录（可用环境变量 LRC_WS 指定）
WORK = os.path.join(WS, "_rebuild_work")


def norm(s):
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip()


def kind(t):
    t = t.strip()
    if not t: return "blank"
    if re.search(r'[ぁ-んァ-ヶー]', t): return "J"
    if re.search(r'[\u0400-\u04ff]', t): return "R"
    if re.search(r'[\uac00-\ud7af]', t): return "K"
    hl = bool(re.search(r'[A-Za-z]', t)); hc = bool(re.search(r'[\u4e00-\u9fff]', t))
    if hl and hc: return "X"
    if hl:
        w = re.findall(r"[A-Za-z']+", t)
        if w and all(x[0].islower() for x in w) and sum(map(len, w)) / len(w) <= 4.0 and len(w) >= 2:
            return "j"
        return "L"
    if hc: return "H"
    if re.fullmatch(r'[\d\s.,!?\-–—~～…\'"()]+', t): return "N"
    return "?"


def load(name):
    p = f"{WS}/{name}"
    raw = open(p, "rb").read()
    bom = raw[:3] == b'\xef\xbb\xbf'
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    recs = []
    for i, l in enumerate(lines):
        m = re.match(r'^\[([^\]]+)\](.*)$', l)
        if m and re.match(r'^\d+:\d', m.group(1)):
            recs.append({"i": i, "ts": m.group(1), "t": m.group(2).strip(), "k": kind(m.group(2))})
    return p, bom, lines, recs


def render(name, TR, fmt="block", note_idx=None, none_pats=None):
    """TR: dict  norm(原文) -> 新译文  或 None(不译,如曲名/制作行)。
    note_idx: recs 中属于注音块的索引集合(原样保留到文件末尾)。
    返回 (new_lines, stats)"""
    p, bom, lines, recs = load(name)
    if note_idx is None:
        note_idx = set()
    NONE = [re.compile(x) for x in (none_pats or [])]
    first_i, last_i = recs[0]["i"], recs[-1]["i"]
    lead = lines[:first_i]
    tail = lines[last_i + 1:]
    orig, notes, olds = [], [], []
    seen = {}
    for ridx, r in enumerate(recs):
        if ridx in note_idx:
            notes.append(r); continue
        c = seen.get(r["ts"], 0); seen[r["ts"]] = c + 1
        (orig if c == 0 else olds).append(r)

    def lookup(t):
        key = norm(t)
        if key in TR:
            return TR[key], True, key
        for rex in NONE:
            if rex.search(key):
                return None, True, key
        return None, False, key

    out = list(lead)
    newcn, missing = [], []
    if fmt == "block":
        for r in orig:
            out.append(f"[{r['ts']}]{r['t']}")
        for r in orig:
            v, ok, key = lookup(r["t"])
            if ok:
                if v is not None:
                    newcn.append(f"[{r['ts']}]{v}")
            else:
                missing.append((r["ts"], repr(key)))
        out += newcn
    else:  # adjacent
        for r in orig:
            out.append(f"[{r['ts']}]{r['t']}")
            v, ok, key = lookup(r["t"])
            if ok:
                if v is not None:
                    cn = f"[{r['ts']}]{v}"; out.append(cn); newcn.append(cn)
            else:
                missing.append((r["ts"], repr(key)))
    for r in notes:
        out.append(f"[{r['ts']}]{r['t']}")
    out += tail
    return out, {"missing": missing, "orig": len(orig), "cn": len(newcn), "notes": len(notes),
                 "olds": len(olds), "stranded": [f"[{r['ts']}]{r['t']}" for r in olds],
                 "p": p, "bom": bom}


def commit(name, new_lines, bom, tag="pre-v2"):
    p = f"{WS}/{name}"
    bak = f"{WS}/_orig_lrc/{name}.{tag}.lrc"
    if not os.path.exists(bak):
        shutil.copy2(p, bak)
    content = "\r\n".join(new_lines) + "\r\n"
    open(p, "wb").write((b'\xef\xbb\xbf' if bom else b'') + content.encode("utf-8"))
    return p, bak


def scan(name):
    p, bom, lines, recs = load(name)
    t = "\n".join(lines)
    info = {"lines": len(lines), "recs": len(recs),
            "star": t.count("**"), "wenqu": t.count("文曲"),
            "title": lines[0][:40] if lines else ""}
    return info
