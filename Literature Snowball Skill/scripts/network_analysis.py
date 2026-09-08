#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析文献库内部的引用网络，输出地位分层数据。

用途：文献滚雪球收束时，"哪几篇是核心文献"不应按轮次顺序或阅读印象判定，
而应按库内真实的引用关系判定。本脚本计算：

  1. 库内互引矩阵   A 的参考文献或正文中是否出现 B 的作者与年份
  2. 入度 / 出度    被库内引用次数 / 引用库内文献篇数
  3. 库外共引锚点   同一外部文献被几篇库内文献引用

用法:
    python network_analysis.py <知识库文件夹> [--scan <扫描目录>] [--libmap <映射文件>]

输入:
    <知识库文件夹>/_检索扫描/index.json     由 scan_library.py 生成
    <知识库文件夹>/_检索扫描/refs/*.txt     由 scan_library.py 生成
    <知识库文件夹>/*.pdf                    用于全文补充检索
    <知识库文件夹>/_检索扫描/libmap.json    可选，手工指定作者与年份（见下）

输出:
    <扫描目录>/network.json          结构化结果
    <扫描目录>/network_report.md     可直接并入 研究提炼.md 的表格与结论

libmap.json 格式（当文件名中不含年份、或作者名有歧义时使用）:
    {
      "文件名中足以唯一定位该篇的片段": {
        "authors": ["作者姓", "第二作者姓"],
        "year": "2022",
        "label": "作者2022"
      }
    }
    键为文件名中足以唯一定位该篇的片段；label 是后续表格与报告中的简称。

依赖: pypdf（或 pymupdf / pdfplumber，仅用于全文补充检索）。
"""

import argparse
import glob
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

YEAR_RE = re.compile(r"(?:19|20)\d{2}")
WINDOW = 120  # 作者名与年份共现的字符窗口


# ---------------------------------------------------------------- 工具

def width(s):
    """全角字符转半角。部分期刊 PDF 的参考文献使用全角数字，不转换会导致年份失配。"""
    out = []
    for ch in s:
        o = ord(ch)
        if o == 0x3000:
            out.append(" ")
        elif 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def load_fulltext(folder):
    """尽力抽取每篇 PDF 的全文，失败返回空串。"""
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            import fitz  # PyMuPDF

            def _extract(path):
                doc = fitz.open(path)
                text = "\n".join(p.get_text("text") or "" for p in doc)
                doc.close()
                return text
        except Exception:
            return {}

        return {os.path.splitext(os.path.basename(p))[0]: _extract(p)
                for p in sorted(glob.glob(os.path.join(folder, "*.pdf")))}

    out = {}
    for p in sorted(glob.glob(os.path.join(folder, "*.pdf"))):
        stem = os.path.splitext(os.path.basename(p))[0]
        try:
            r = PdfReader(p)
            out[stem] = "\n".join((pg.extract_text() or "") for pg in r.pages)
        except Exception:
            out[stem] = ""
    return out


def read_refs(scan_dir):
    refs = {}
    for f in glob.glob(os.path.join(scan_dir, "refs", "*.txt")):
        stem = os.path.splitext(os.path.basename(f))[0]
        try:
            refs[stem] = open(f, encoding="utf-8").read()
        except Exception:
            refs[stem] = ""
    return refs


# ---------------------------------------------------------------- 文献表

def build_lib(index, folder, libmap):
    """返回 {label: {"authors": [...], "year": "...", "stem": "..."}}。

    优先取 libmap；否则从文件名推断：作者取最后一个下划线后的片段，年份取文件名中的四位数字。
    两者缺一即标为待补，并提示用户填写 libmap.json。
    """
    lib, pending = {}, []
    for doc in index.get("docs", []):
        stem = doc.get("stem") or os.path.splitext(doc.get("file", ""))[0]

        hit = None
        for frag, info in libmap.items():
            if frag in stem:
                hit = info
                break
        if hit:
            label = hit.get("label") or ("%s%s" % (hit["authors"][0], hit["year"]))
            lib[label] = {"authors": hit["authors"], "year": str(hit["year"]), "stem": stem}
            continue

        parts = stem.split("_")
        author = parts[-1] if len(parts) > 1 else ""
        y = YEAR_RE.search(stem)
        if author and y:
            label = "%s%s" % (author, y.group(0))
            lib[label] = {"authors": [author], "year": y.group(0), "stem": stem}
        else:
            pending.append({"stem": stem, "author": author, "year": y.group(0) if y else None})
    return lib, pending


def write_libmap_template(scan_dir, pending):
    path = os.path.join(scan_dir, "libmap.template.json")
    tpl = {}
    for p in pending:
        key = p["stem"].split("_")[0][:14] or p["stem"][:14]
        tpl[key] = {"authors": [p["author"]] if p["author"] else [], "year": p["year"] or "", "label": ""}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tpl, f, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------- 互引

def make_cites(refs, fulltext, lib):
    def cites(src_label, dst_label):
        src = lib[src_label]["stem"]
        text = width(refs.get(src, "") + "\n" + fulltext.get(src, ""))
        text = re.sub(r"\s+", "", text)
        year = lib[dst_label]["year"]
        for tok in lib[dst_label]["authors"]:
            for m in re.finditer(re.escape(tok), text):
                seg = text[max(0, m.start() - WINDOW): m.end() + WINDOW]
                if year in seg:
                    return True
        return False

    return cites


def build_matrix(lib, cites):
    matrix = {}
    for a in lib:
        for b in lib:
            if a != b and cites(a, b):
                matrix.setdefault(a, []).append(b)
    indeg = {b: 0 for b in lib}
    outdeg = {a: len(matrix.get(a, [])) for a in lib}
    for a, bs in matrix.items():
        for b in bs:
            indeg[b] += 1
    return matrix, indeg, outdeg


# ---------------------------------------------------------------- 共引

def norm_key(entry):
    e = width(re.sub(r"\s+", "", entry))
    m = YEAR_RE.search(e)
    if not m:
        return None
    year = m.group(0)
    head = e[:m.start()]
    head = re.sub(r"^[\[\(]?\d{1,3}[\]\)\.、]?", "", head)
    head = re.sub(r"[^\u4e00-\u9fffA-Za-z]", "", head)
    if len(head) < 2:
        return None
    return (head[:6], year)


def co_citation(index, skip=()):
    """按 index.json 的 entry_list 统计跨篇共引。skip 中的 stem 片段将被跳过。"""
    co = {}
    for doc in index.get("docs", []):
        stem = doc.get("stem") or ""
        if any(s in stem for s in skip):
            continue
        seen = set()
        for line in doc.get("entry_list", []) or []:
            k = norm_key(line)
            if k:
                seen.add(k)
        for k in seen:
            co.setdefault("%s|%s" % k, set()).add(stem)
    return {k: sorted(v) for k, v in co.items()}


# ---------------------------------------------------------------- 报告

def short(stem, n=16):
    return stem[:n]


def render_report(lib, matrix, indeg, outdeg, co, pending, skip):
    L = []
    L.append("# 库内引用网络报告")
    L.append("")
    L.append("> 由 network_analysis.py 生成。判据：A 的参考文献或正文中出现 B 的作者与年份，"
             "且两者落在同一 %d 字窗口内，即计为 A 引用 B。" % WINDOW)
    L.append("")
    L.append("## 一、互引边表")
    L.append("")
    L.append("| 引用方 | 被引的库内文献 | 出度 |")
    L.append("| --- | --- | --- |")
    for a in sorted(lib, key=lambda x: (-outdeg[x], x)):
        if outdeg[a] == 0:
            continue
        L.append("| %s | %s | %d |" % (a, "、".join(matrix[a]), outdeg[a]))
    zeros = [a for a in lib if outdeg[a] == 0]
    if zeros:
        L.append("| 其余 %d 篇 | 未引用库内任何文献 | 0 |" % len(zeros))
    L.append("")
    L.append("## 二、地位分层")
    L.append("")
    L.append("| 层次 | 文献 | 入度 | 出度 |")
    L.append("| --- | --- | --- | --- |")
    for label in sorted(lib, key=lambda x: (-indeg[x], -outdeg[x], x)):
        if indeg[label] >= 2:
            layer = "枢纽层"
        elif outdeg[label] > 0:
            layer = "接入层"
        else:
            layer = "端点层"
        L.append("| %s | %s | %d | %d |" % (layer, label, indeg[label], outdeg[label]))
    L.append("")
    L.append("判据：入度 ≥ 2 为枢纽层；出度 > 0 且入度 ≤ 1 为接入层；其余为端点层。")
    L.append("")
    L.append("## 三、库外共引锚点（≥2 篇）")
    L.append("")
    L.append("| 共引文献 | 被几篇库内文献引用 | 引用者 |")
    L.append("| --- | --- | --- |")
    for k, docs in sorted(co.items(), key=lambda x: (-len(x[1]), x[0])):
        if len(docs) < 2:
            continue
        L.append("| %s | %d | %s |" % (k, len(docs), "、".join(short(d) for d in docs)))
    L.append("")
    L.append("## 四、口径与局限")
    L.append("")
    L.append("1. 共引按参考文献条目首部规范字符加年份匹配，同一文献在不同参考文献表中因排版顺序"
             "不同可能被拆成两个键，因此计数只构成下限。")
    if skip:
        L.append("2. 以下文件的参考文献区存在同刊他文混入，已从共引统计中排除：%s。" % "、".join(skip))
    L.append("3. 作者重名会造成误判。常见姓名尤其需要抽查若干条边，确认作者名与年份确实指向同一篇。")
    if pending:
        L.append("4. 以下文献因文件名不含年份或作者不明，未纳入网络，请填写 libmap.json 后重跑：")
        for p in pending:
            L.append("   - %s" % p["stem"])
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="分析文献库内部引用网络，输出地位分层")
    ap.add_argument("folder", help="知识库文件夹路径")
    ap.add_argument("--scan", default=None, help="扫描目录，默认 <folder>/_检索扫描")
    ap.add_argument("--libmap", default=None, help="作者年份映射文件，默认 <扫描目录>/libmap.json")
    ap.add_argument("--skip-cocite", default="", help="共引统计中跳过的文件名片段，逗号分隔")
    args = ap.parse_args()

    folder = os.path.abspath(args.folder)
    scan_dir = os.path.abspath(args.scan) if args.scan else os.path.join(folder, "_检索扫描")
    if not os.path.isdir(scan_dir):
        print("错误：扫描目录不存在 -> %s\n请先运行 scan_library.py" % scan_dir)
        return 2

    idx_path = os.path.join(scan_dir, "index.json")
    if not os.path.isfile(idx_path):
        print("错误：未找到 index.json -> %s\n请先运行 scan_library.py" % idx_path)
        return 2
    index = json.load(open(idx_path, encoding="utf-8"))

    libmap_path = args.libmap or os.path.join(scan_dir, "libmap.json")
    libmap = {}
    if os.path.isfile(libmap_path):
        libmap = json.load(open(libmap_path, encoding="utf-8"))
        print("已加载映射：%s（%d 条）" % (libmap_path, len(libmap)))

    lib, pending = build_lib(index, folder, libmap)
    print("识别到 %d 篇文献" % len(lib))
    if pending:
        tpl = write_libmap_template(scan_dir, pending)
        print("  [待补] %d 篇缺少作者或年份，已生成模板：%s" % (len(pending), tpl))
        for p in pending:
            print("    - %s" % p["stem"])

    if len(lib) < 2:
        print("可分析的文献不足两篇，终止。")
        return 1

    refs = read_refs(scan_dir)
    fulltext = load_fulltext(folder)
    cites = make_cites(refs, fulltext, lib)
    matrix, indeg, outdeg = build_matrix(lib, cites)

    skip = [s for s in args.skip_cocite.split(",") if s.strip()]
    co = co_citation(index, skip=skip)

    print("\n===== 互引边表 =====")
    for a in sorted(lib, key=lambda x: (-outdeg[x], x)):
        if outdeg[a]:
            print("%-14s -> %s" % (a, "、".join(matrix[a])))
    print("\n===== 入度 / 出度 =====")
    for label in sorted(lib, key=lambda x: (-indeg[x], -outdeg[x], x)):
        print("%-14s 入度 %d  出度 %d" % (label, indeg[label], outdeg[label]))
    print("\n===== 库外共引 >=2 篇 =====")
    for k, docs in sorted(co.items(), key=lambda x: (-len(x[1]), x[0])):
        if len(docs) >= 2:
            print("%-20s %d篇 | %s" % (k, len(docs), "、".join(short(d) for d in docs)))

    payload = {
        "lib": {k: {"authors": v["authors"], "year": v["year"]} for k, v in lib.items()},
        "matrix": matrix, "indeg": indeg, "outdeg": outdeg, "co": co,
        "pending": pending, "window": WINDOW,
    }
    with open(os.path.join(scan_dir, "network.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    report = render_report(lib, matrix, indeg, outdeg, co, pending, skip)
    with open(os.path.join(scan_dir, "network_report.md"), "w", encoding="utf-8") as f:
        f.write(report)

    print("\n输出：")
    print("  %s" % os.path.join(scan_dir, "network.json"))
    print("  %s" % os.path.join(scan_dir, "network_report.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
