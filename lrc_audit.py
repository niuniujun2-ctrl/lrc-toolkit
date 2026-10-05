#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""歌词库体检 (lrc_audit) —— 全库扫描 .lrc 的健康状况

检查项（启发式，输出供人工复核）:
  - 编码: UTF-8 BOM 是否在、是否有裸 LF、U+FFFD 替换符
  - 结构: 解析 [时间戳] 行, 分类 (日/俄/韩/拉丁/注音/中文/混合)
  - 缺译: 外文原文行没有同时间戳的中文同伴
  - 重译: 同一时间戳出现 2 条以上独立译文
  - 杂行: 注音区里混进的译文行
  - 打码: ** ／＊；宣传行/水印: 文曲、TME享有 等
  - awlrc: lx-music 的 [awlrc:...] 内嵌巨行

用法:
  python lrc_audit.py [目录或 .lrc ...]        # 默认扫描当前目录
  python lrc_audit.py "D:/music" --json audit.json

退出码: 0=全部通过, 1=发现问题, 2=用法错误
作者: AI 助手「苍娜」(Hermes Agent)｜人类监督: niuniujun2-ctrl
"""
import argparse
import json
import os
import re
import sys
import collections

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CJK = re.compile(r"[\u4e00-\u9fff]")
JP = re.compile(r"[ぁ-んァ-ヶー]")
RU = re.compile(r"[\u0400-\u04ff]")
KO = re.compile(r"[\uac00-\ud7af]")
TS = re.compile(r"^\[(\d+:\d[^\]]*)\](.*)$")

# 宣传行 / 平台水印（正则）
SIGN_PATTERNS = [r"文曲", r"TME享有", r"本翻译作品", r"由.{0,12}大模型", r"机器翻译由"]
# 行尾 credits/标题豁免（缺译判定时跳过含这些词的行）
CREDITS = re.compile(r"词|曲|编曲|制作|混音|母带|演唱|作词|作曲|出品|OP|ED|策划|监制")


def kind(t):
    t = t.strip()
    if not t:
        return "blank"
    if JP.search(t):
        return "J"
    if RU.search(t):
        return "R"
    if KO.search(t):
        return "K"
    hl = bool(re.search(r"[A-Za-z]", t))
    hc = bool(CJK.search(t))
    if hl and hc:
        return "X"
    if hl:
        w = re.findall(r"[A-Za-z']+", t)
        if w and all(x[0].islower() for x in w) and sum(map(len, w)) / len(w) <= 4.0 and len(w) >= 2:
            return "j"       # 罗马音/粤拼一类注音行
        return "L"
    if hc:
        return "H"
    if re.fullmatch(r"[\d\s.,!?\-–—~～…'\"()]+", t):
        return "N"
    return "?"


def parse(path):
    raw = open(path, "rb").read()
    bom = raw[:3] == b"\xef\xbb\xbf"
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    text = raw.decode("utf-8-sig", errors="replace")
    fffd = text.count("\ufffd")
    lines = text.replace("\r\n", "\n").split("\n")
    recs = []
    for i, l in enumerate(lines):
        m = TS.match(l)
        if m:
            recs.append({"i": i, "ts": m.group(1), "t": m.group(2).strip(), "k": kind(m.group(2))})
    return {"bom": bom, "crlf": crlf, "stray_lf": lf, "fffd": fffd, "lines": lines, "recs": recs}


def audit_file(path):
    info = parse(path)
    recs = info["recs"]
    issues = []

    if info["fffd"]:
        issues.append(("替换符", "%d 处 U+FFFD" % info["fffd"]))
    if info["stray_lf"]:
        issues.append(("行尾", "%d 处裸 LF（应为全 CRLF）" % info["stray_lf"]))
    if not info["bom"]:
        issues.append(("编码", "缺少 UTF-8 BOM（utf-8-sig）"))

    # 注音区 = 文件尾部连续的 注音/符号/空 行（全小写拉丁也算——罗马音常见形态）
    def is_note_line(t):
        if kind(t) in ("j", "N", "blank"):
            return True
        return bool(re.fullmatch(r"[a-z][a-z\s']*", t.strip()))

    k = len(recs) - 1
    while k >= 0 and is_note_line(recs[k]["t"]):
        k -= 1
    note_set = set(range(k + 1, len(recs)))
    pure_note = len(recs) > 0 and k + 1 == 0

    byts = collections.OrderedDict()
    for idx, r in enumerate(recs):
        byts.setdefault(r["ts"], []).append((idx, r))

    missing, dup = [], []
    for ts, items in byts.items():
        zh = [(idx, r) for idx, r in items
              if CJK.search(r["t"]) and not r["t"].startswith("※")]
        if pure_note:
            break
        in_notes = all(idx in note_set for idx, _ in items)
        if in_notes:
            continue
        foreign = any(r["k"] in ("J", "R", "K", "L", "X", "j") for idx, r in items if idx not in note_set)
        orig_is_cjk = bool(CJK.search(items[0][1]["t"]))
        if foreign and not zh:
            if any(idx == 0 for idx, _ in items):
                continue                     # 文件首行（标题行）豁免
            txt = " ".join(r["t"] for _, r in items)
            if not CREDITS.search(txt):
                missing.append({"ts": ts, "text": txt[:60]})
        if len(zh) >= 2 and not orig_is_cjk:
            dup.append({"ts": ts, "texts": [r["t"][:40] for _, r in zh]})

    if missing:
        issues.append(("缺译", "%d 组" % len(missing), missing[:8]))
    if dup:
        issues.append(("重译", "%d 组" % len(dup), dup[:8]))

    stray = [{"ts": recs[i]["ts"], "text": recs[i]["t"][:40], "kind": recs[i]["k"]}
             for i in sorted(note_set) if recs[i]["k"] in ("H", "J", "X")]
    if stray:
        issues.append(("杂行", "%d 行" % len(stray), stray[:8]))

    star = sum(l.count("**") + l.count("＊") for l in info["lines"])
    if star:
        issues.append(("打码", "%d 处" % star))

    for pat in SIGN_PATTERNS:
        hits = [l.strip()[:60] for l in info["lines"] if re.search(pat, l)]
        if hits:
            issues.append(("宣传行/水印", "%s × %d" % (pat, len(hits)), hits[:3]))

    aw = sum(1 for l in info["lines"] if "[awlrc" in l.lower())
    if aw:
        issues.append(("awlrc", "%d 行" % aw))

    stats = {"timed_lines": len(recs), "missing": len(missing), "dup": len(dup), "stray": len(stray)}
    return issues, stats


def main():
    ap = argparse.ArgumentParser(description="歌词库体检（.lrc 全库扫描）")
    ap.add_argument("paths", nargs="*", help="目录或 .lrc 文件（默认当前目录）")
    ap.add_argument("--json", dest="json_out", help="把完整结果写到该 JSON 文件")
    a = ap.parse_args()
    targets = []
    for p in (a.paths or ["."]):
        if os.path.isdir(p):
            for dp, _dn, fn in os.walk(p):
                for f in fn:
                    if f.lower().endswith(".lrc"):
                        targets.append(os.path.join(dp, f))
        elif os.path.isfile(p) and p.lower().endswith(".lrc"):
            targets.append(p)
    targets.sort()
    if not targets:
        print("没有找到 .lrc 文件")
        return 2

    results = {}
    n_bad = 0
    print("==== 歌词库体检 ====")
    print("扫描 %d 个文件" % len(targets))
    for fp in targets:
        try:
            issues, stats = audit_file(fp)
        except Exception as e:
            issues, stats = [("读取失败", "%s: %s" % (type(e).__name__, e))], {}
        try:
            name = os.path.relpath(fp)
        except ValueError:
            name = fp
        if issues:
            n_bad += 1
            print("\n-- %s" % name)
            for it in issues:
                t = it[0]
                rest = "  ".join(str(x) for x in it[1:])
                print("   [%s] %s" % (t, rest))
        results[name] = {"issues": [{"type": i[0], "detail": i[1:]} for i in issues], "stats": stats}

    print("\n==== 结果: 有问题 %d / %d ====" % (n_bad, len(targets)))
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
        print("JSON 已写入:", a.json_out)
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
