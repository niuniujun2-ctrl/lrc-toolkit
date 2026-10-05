# lrc-toolkit —— 歌词库（.lrc）维护工具链

> 🤖 本仓库的代码与文档由 **AI 编写**（AI 助手「苍娜」，运行于 Hermes Agent）；人类作者负责需求、验收与发布。详见「关于本项目」。

给个人歌词库（lx-music / PotPlayer 一类本地播放器使用的 `.lrc`）做
**重建、回写、体检** 的小工具。纯 Python 标准库，零依赖。

适用背景：本地歌词库常见问题 —— 供应商机翻（副歌机械直译、软化、打码）、
双边（原文/译文）结构混乱（交替式/分块式混用）、注音行被误当译文、
时间戳同组两套译文、`awlrc` 内嵌巨行……这套工具用来**批量定位与维护**。

## 组件

| 文件 | 作用 |
|:--|:--|
| `rebuild_lib.py` | 重建库：读文件 → 按「原文→新译文」字典整篇重渲染（相邻式/分块式皆可）→ 校验 `missing==0` → 带备份回写 |
| `lrc_audit.py` | 体检：全库扫描编码/结构/缺译/重译/杂行/打码/宣传行/awlrc，输出报告（可 `--json`） |
| `docs/维护指南.md` | 库约定、备份铁律、三个工作程序、常见病症与坑 |
| `docs/歌词注释指南.md` | 名词解释注释（`※` 注行）的写法与考据链路 |

## 快速开始

### 体检（先跑这个）
```bash
python lrc_audit.py "D:/music/歌词库" --json audit.json
```
输出按文件列出问题；退出码 `1` 表示有问题（方便接 CI/批处理）。

### 整篇重译（配合任意翻译流程）
`rebuild_lib.py` 是库函数，通常在一个脚本里这样用：

```python
import os
os.environ["LRC_WS"] = "D:/music/歌词库"      # 库根目录（或把本文件放进库的 _rebuild_work/ 下）
import rebuild_lib as rl

TR = { "原文行文本(规范化后)": "新译文", ... }   # 键见 docs/维护指南.md
out, stats = rl.render("曲名.lrc", TR, fmt="block", note_idx={...})
assert not stats["missing"], stats["missing"]   # missing==0 才允许提交
rl.commit("曲名.lrc", out, stats["bom"])        # 自动写 _orig_lrc/<名>.pre-v2.lrc 备份
```

- `fmt="block"` 分块式 / `fmt="adjacent"` 相邻式；
- 注音块经 `note_idx` 原样垫尾；标题与词曲 credits 用 `none_pats` 正则豁免；
- `commit()` 永远先备份后写，**utf-8-sig + CRLF** 原样保持。

## 库布局约定

```
歌词库/
  曲名.flac / .mp3        ← 与 .lrc 成对
  曲名.lrc                ← 成品（原文 + 中文译文 + 注音块）
  _orig_lrc/              ← 原始下载 + “改前备份”（.pre-v2 / .pre-retrans / .pre-notes…）
  _rebuild_work/          ← 工作区（审计 JSON、对照报告、queue 进度）
```

## 硬规则（血泪总结）

1. **每条原文至多一种译文**；先检测再插入（网易云双语有交替式/分块式两种，
   识别失误会插出双份译文）。
2. 注音行（罗马音/台罗/粤拼）**不翻译、原样保留**。
3. 方言歌词（台语/粤语）是汉字行，会被“有汉字=已有译文”的检测**误判**——人工确认。
4. 改前必备份，分档命名，不覆盖旧档。
5. 脏话/成人内容按原力度保留——不做“净化”（详见 `lrc_audit.py` 的零和谐配套检查思路）。

更多见 `docs/维护指南.md`。

## 许可

MIT（见 LICENSE）。

## 关于本项目

- **本仓库代码与文档由 AI 编写**：`lrc_audit.py`、文档与测试由 AI 助手 **苍娜**
  （运行于 Hermes Agent）完成；`rebuild_lib.py` 提炼自真实歌词库维护项目。
- 人类作者 [@niuniujun2-ctrl](https://github.com/niuniujun2-ctrl) 负责提出需求、验收与发布。
- 已在真实歌词库（数百首、双语、含注释）上使用验证。
