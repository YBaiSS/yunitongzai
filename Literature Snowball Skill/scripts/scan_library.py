#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量扫描学术 PDF 知识库，抽取参考文献清单与文献综述/评论候选段落。

用法:
    python scan_library.py <知识库文件夹> [--out <输出目录>] [--hits N] [--no-cocite]

输出（默认写到 <知识库文件夹>/_检索扫描/）:
    refs/<文件名>.txt        该篇文后的参考文献区原始文本
    entries/<文件名>.txt     切分后的参考文献条目（带序号，便于引用定位）
    hits/<文件名>.md         综述/评论候选段落（含页码、命中信号、引文密度）
    co_citations.txt         跨篇共引候选（启发式，需人工核对）
    index.json               结构化索引
    SUMMARY.md               本次扫描摘要

依赖: 依次尝试 pymupdf(fitz) / pdfplumber / pypdf；三者皆无时提示安装办法。
"""

import argparse
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ---------------------------------------------------------------- 后端加载

def load_backend():
    """返回 (名称, 抽取函数)，抽取函数接收 pdf 路径，返回按页排列的文本列表。"""
    try:
        import fitz  # PyMuPDF

        def _fitz(path):
            doc = fitz.open(path)
            pages = [p.get_text("text") or "" for p in doc]
            doc.close()
            return pages

        return "pymupdf", _fitz
    except Exception:
        pass
    try:
        import pdfplumber

        def _plumber(path):
            out = []
            with pdfplumber.open(path) as pdf:
                for p in pdf.pages:
                    out.append(p.extract_text() or "")
            return out

        return "pdfplumber", _plumber
    except Exception:
        pass
    try:
        from pypdf import PdfReader

        def _pypdf(path):
            r = PdfReader(path)
            return [(p.extract_text() or "") for p in r.pages]

        return "pypdf", _pypdf
    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------- 参考文献定位

REF_HEADINGS = [
    r"^\s*参\s*考\s*文\s*献",
    r"^\s*引\s*用\s*文\s*献",
    r"^\s*文\s*献\s*注\s*释",
    r"^\s*注\s*释\s*与\s*参\s*考\s*文\s*献",
    r"^\s*Reference[s]?\s*$",
    r"^\s*Bibliography\s*$",
    r"^\s*Works\s+Cited\s*$",
    r"^\s*Literature\s+Cited\s*$",
    r"^\s*Reference[s]?\s+Cited\s*$",
    r"^\s*Selected\s+Bibliography\s*$",
]
REF_HEADING_RE = [re.compile(p, re.IGNORECASE) for p in REF_HEADINGS]


def find_reference_start(pages):
    """从后往前找参考文献区起始位置，返回 (页序号, 页内字符偏移)；找不到返回 None。"""
    n = len(pages)
    start_scan = max(0, int(n * 0.4))  # 参考文献通常出现在后 60%
    for i in range(n - 1, start_scan - 1, -1):
        text = pages[i] or ""
        for line_idx, line in enumerate(text.splitlines()):
            for rx in REF_HEADING_RE:
                if rx.match(line):
                    offset = 0
                    for prev in text.splitlines()[:line_idx + 1]:
                        offset += len(prev) + 1
                    return i, min(offset, len(text))
    return None


def reference_text(pages, start):
    if start is None:
        return "", None
    idx, off = start
    parts = [pages[idx][off:]]
    parts.extend(pages[idx + 1:])
    return "\n".join(parts), idx


NUMPAT = re.compile(r"^\s*[\[\(（]?\s*(\d{1,3})\s*[\]\)）.、]\s*\S")


NUM_STRIP_RE = re.compile(r"^\s*[\[\(（]?\s*\d{1,3}\s*[\]\)）.、]\s*")
NEW_ENTRY_HEAD_RE = re.compile(r"^[\[\(（]?[A-Z\u4e00-\u9fff]")


def _group_numbered(lines, numpat):
    entries, buf = [], []
    for ln in lines:
        if numpat.match(ln) and buf:
            entries.append(" ".join(buf).strip())
            buf = [ln.strip()]
        else:
            buf.append(ln.strip())
    if buf:
        entries.append(" ".join(buf).strip())
    cleaned = [NUM_STRIP_RE.sub("", e).strip() for e in entries]
    return [e for e in cleaned if len(e) > 4]


SENT_END_RE = re.compile(r"[.。）)\]]\s*$")


def _group_authoryear(lines):
    """作者-年制：行内含四位年份、行首为作者起始字符、且上一行已收句，则另起一条。"""
    entries, buf = [], []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        starts_new = bool(YEAR_RE.search(s)) and bool(NEW_ENTRY_HEAD_RE.match(s))
        if buf and starts_new and SENT_END_RE.search(buf[-1]):
            entries.append(" ".join(buf).strip())
            buf = [s]
        else:
            buf.append(s)
    if buf:
        entries.append(" ".join(buf).strip())
    entries = [NUM_STRIP_RE.sub("", e).strip() for e in entries if len(e) > 4]
    if len(entries) < 3:  # 切分失败，退回逐行
        return [NUM_STRIP_RE.sub("", l.strip()).strip() for l in lines if len(l.strip()) > 4]
    return entries


def split_reference_entries(text):
    lines = [l.rstrip() for l in text.splitlines()]
    lines = [l for l in lines if l.strip()]
    if not lines:
        return []
    numbered = [l for l in lines if NUMPAT.match(l)]
    if len(lines) >= 6 and len(numbered) / len(lines) >= 0.35:
        return _group_numbered(lines, NUMPAT)
    return _group_authoryear(lines)


# ---------------------------------------------------------------- 综述信号

CN_SIGNALS = [
    "文献综述", "研究综述", "文献回顾", "研究述评", "学术史", "研究脉络", "理论脉络",
    "已有研究", "既有研究", "现有研究", "既有文献", "现有文献", "前人研究", "以往研究",
    "学界", "主流观点", "代表性", "开创性", "经典", "传统", "学派", "谱系",
    "争议", "争论", "分歧", "争鸣", "不同看法", "不同观点", "两条路径", "两种取向",
    "然而", "但是", "尽管如此", "有所不同", "与之不同", "相比之下",
    "不足", "局限", "尚未", "鲜有", "缺乏", "忽视了", "忽略", "有待", "缺口", "空白",
    "在此基础上", "承继", "推进", "本文试图", "本文试图回答",
]
EN_SIGNALS = [
    "literature review", "prior research", "previous studies", "existing literature",
    "prior work", "earlier work", "the literature on", "scholarship on",
    "however", "yet ", "in contrast", "by contrast", "on the other hand",
    "debate", "controversy", "contested", "dispute", "divergent", "competing",
    "consensus", "seminal", "canonical", "classical", "strand", "school of",
    "gap", "limitations", "overlooked", "neglected", "understudied", "little attention",
    "building on", "extends", "departs from", "this paper seeks", "we argue",
]
YEAR_RE = re.compile(r"(?:19|20)\d{2}")
BRACKET_CITE_RE = re.compile(r"[\[\(（]\s*\d{1,3}\s*[\]\)）]")


def scan_paragraphs(pages, ref_page_idx):
    """对参考文献区之前的正文逐段打分，返回命中列表。"""
    limit = ref_page_idx if ref_page_idx is not None else len(pages)
    hits = []
    for pno in range(limit):
        raw = pages[pno] or ""
        if not raw.strip():
            continue
        blocks = [b.strip() for b in re.split(r"\n\s*\n", raw) if b.strip()]
        if len(blocks) <= 1:  # 无空行分隔时按行切块
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            step = 6
            blocks = [" ".join(lines[i:i + step]) for i in range(0, len(lines), step)]
        for b in blocks:
            if len(b) < 60:
                continue
            # 双栏版式常使整页连成巨块，按 1600 字窗口滑动切分，避免整块漏检
            if len(b) > 2400:
                parts = [b[i:i + 1600] for i in range(0, len(b), 800)]
            else:
                parts = [b]
            for part in parts:
                if len(part) < 60:
                    continue
                low = part.lower()
                cn_hit = [s for s in CN_SIGNALS if s in part]
                en_hit = [s for s in EN_SIGNALS if s in low]
                cites = len(YEAR_RE.findall(part)) + len(BRACKET_CITE_RE.findall(part))
                score = 2 * (len(cn_hit) + len(en_hit)) + min(cites, 10)
                if score < 6:
                    continue
                hits.append({
                    "page": pno + 1,
                    "score": score,
                    "signals": cn_hit + en_hit,
                    "cites": cites,
                    "text": part[:1500],
                })
    hits.sort(key=lambda h: -h["score"])
    # 同一页相邻滑动窗口可能重复命中同一段落，保留最强者
    dedup, seen_key = [], set()
    for h in hits:
        key = (h["page"], h["text"][:80])
        if key not in seen_key:
            seen_key.add(key)
            dedup.append(h)
    return dedup


# ---------------------------------------------------------------- 共引

def norm_key(entry):
    s = re.sub(r"\s+", " ", entry).strip()
    y = YEAR_RE.search(s)
    year = y.group(0) if y else ""
    head = re.split(r"[,，.。:]", s)[0]
    head = re.sub(r"^[\[\(（]?\d{1,3}[\]\)）.、]?\s*", "", head)
    head = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", head).lower()
    return (head[:8], year)


def co_citations(per_doc_entries, min_docs=2):
    bucket = {}
    for stem, entries in per_doc_entries.items():
        seen = set()
        for idx, e in enumerate(entries):
            k = norm_key(e)
            if not k[0]:
                continue
            if k in seen:
                continue
            seen.add(k)
            bucket.setdefault(k, []).append((stem, idx + 1, e[:160]))
    out = []
    for k, v in bucket.items():
        docs = {d for d, _, _ in v}
        if len(docs) >= min_docs:
            out.append({"key": "%s|%s" % k, "docs": len(docs), "items": v[:8]})
    out.sort(key=lambda x: (-x["docs"], x["key"]))
    return out


# ---------------------------------------------------------------- 主流程

def iter_pdfs(folder):
    out = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith("_") and not d.startswith(".")]
        for f in files:
            if f.lower().endswith(".pdf") and not f.startswith("_") and not f.startswith("~"):
                out.append(os.path.join(root, f))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description="扫描学术 PDF 知识库，抽取参考文献与综述段落")
    ap.add_argument("folder", help="知识库文件夹路径")
    ap.add_argument("--out", default=None, help="输出目录，默认 <folder>/_检索扫描")
    ap.add_argument("--hits", type=int, default=8, help="每篇保留的综述候选段数，默认 8")
    ap.add_argument("--no-cocite", action="store_true", help="跳过共引统计")
    args = ap.parse_args()

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        print("错误：文件夹不存在 -> %s" % folder)
        return 2
    out_dir = os.path.abspath(args.out) if args.out else os.path.join(folder, "_检索扫描")
    for sub in ("refs", "entries", "hits"):
        os.makedirs(os.path.join(out_dir, sub), exist_ok=True)

    backend, extract = load_backend()
    if backend is None:
        print("未找到 PDF 解析库。请先在隔离环境安装：")
        print("  pip install pypdf        # 或 pymupdf / pdfplumber")
        return 3
    print("PDF 后端: %s" % backend)

    pdfs = iter_pdfs(folder)
    if not pdfs:
        print("未在 %s 下找到 PDF 文件" % folder)
        return 1
    print("发现 %d 篇 PDF" % len(pdfs))

    index = {"folder": folder, "backend": backend, "docs": []}
    per_doc_entries = {}
    summary_lines = ["# 扫描摘要", "", "- 知识库：%s" % folder, "- PDF 后端：%s" % backend,
                     "- 文献数：%d" % len(pdfs), "",
                     "| 文件 | 页数 | 文本层 | 参考文献起始 | 条目数 | 命中段数 |",
                     "| --- | --- | --- | --- | --- | --- |"]

    for path in pdfs:
        stem = os.path.splitext(os.path.basename(path))[0]
        rel = os.path.relpath(path, folder)
        try:
            pages = extract(path)
        except Exception as e:
            print("  [跳过] %s -> 解析失败: %s" % (rel, e))
            summary_lines.append("| %s | - | 解析失败 | - | - | - |" % rel)
            index["docs"].append({"file": rel, "error": str(e)})
            continue

        nonempty = sum(1 for p in pages if p and p.strip())
        has_text = nonempty >= max(1, int(len(pages) * 0.3))
        start = find_reference_start(pages)
        reftext, ref_page = reference_text(pages, start)
        entries = split_reference_entries(reftext) if reftext.strip() else []

        with open(os.path.join(out_dir, "refs", stem + ".txt"), "w", encoding="utf-8") as f:
            f.write(reftext or "（未定位到参考文献区）")
        with open(os.path.join(out_dir, "entries", stem + ".txt"), "w", encoding="utf-8") as f:
            for i, e in enumerate(entries, 1):
                f.write("[%d] %s\n" % (i, e))
            if not entries:
                f.write("（无）")

        hits = scan_paragraphs(pages, ref_page) if has_text else []
        keep = hits[:args.hits]
        with open(os.path.join(out_dir, "hits", stem + ".md"), "w", encoding="utf-8") as f:
            f.write("# %s 综述/评论候选段落\n\n" % stem)
            f.write("- 页数：%d；有效文本页：%d；参考文献起始页：%s\n\n"
                     % (len(pages), nonempty, (ref_page + 1) if ref_page is not None else "未定位"))
            if not keep:
                f.write("（无命中。若 PDF 为扫描件或文本层异常，改用 Read 工具直接阅读。）\n")
            for h in keep:
                f.write("## 第 %d 页 · 分值 %d · 引文标记 %d\n" % (h["page"], h["score"], h["cites"]))
                f.write("- 信号词：%s\n\n" % "、".join(h["signals"][:12]))
                f.write("%s\n\n" % h["text"])

        per_doc_entries[stem] = entries
        index["docs"].append({
            "file": rel, "stem": stem, "pages": len(pages), "text_layer": has_text,
            "ref_start_page": (ref_page + 1) if ref_page is not None else None,
            "entries": len(entries), "hits": len(keep),
            "entry_list": entries,
        })
        summary_lines.append("| %s | %d | %s | %s | %d | %d |" % (
            rel, len(pages), "有" if has_text else "无（疑似扫描件）",
            (ref_page + 1) if ref_page is not None else "未定位", len(entries), len(keep)))
        print("  %s：%d 页，参考文献 %d 条，命中 %d 段" % (rel, len(pages), len(entries), len(keep)))

    if not args.no_cocite:
        co = co_citations(per_doc_entries)
        with open(os.path.join(out_dir, "co_citations.txt"), "w", encoding="utf-8") as f:
            f.write("# 跨篇共引候选（启发式匹配，务必人工核对）\n\n")
            if not co:
                f.write("（未发现跨篇共引，可能因为条目切分或作者年份格式差异较大）\n")
            for c in co:
                f.write("## 出现于 %d 篇 · %s\n" % (c["docs"], c["key"]))
                for stem, no, txt in c["items"]:
                    f.write("  - %s [%d] %s\n" % (stem, no, txt))
                f.write("\n")
        summary_lines.append("")
        summary_lines.append("跨篇共引候选：%d 条（见 co_citations.txt，需人工核对）" % len(co))

    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

    print("\n输出目录: %s" % out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
