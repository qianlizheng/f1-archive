#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
F1 一手素材采集器
--------------------
在境外（GitHub Actions）定时运行，把 FIA 决策文件、FIA 新闻、
F1 官网文章、外媒 RSS 落成本地归档，并生成一份摘要。

设计原则：
1. 只用标准库，零依赖，GitHub Actions 上开箱即跑。
2. 所有内容按日期归档，PDF 原文一并下载，形成本地档案库。
3. 去重靠 state/seen.json，重复运行不会重复下载。
4. 可选：把摘要推送到飞书 / 企业微信 / 钉钉机器人（国内直连）。

用法：
    python3 collect.py                # 正常采集
    python3 collect.py --dry-run      # 只打印，不写文件
    python3 collect.py --no-pdf       # 跳过 PDF 下载
    python3 collect.py --limit 8      # 每个源最多取 8 条
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36")

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(ROOT, "archive")
STATE = os.path.join(ROOT, "state", "seen.json")

# ---------------------------------------------------------------- 源定义
# type:
#   fia_docs  FIA 决策文件页，抓 PDF 直链
#   html      普通列表页，按 link_re 抓文章链接
#   rss       RSS / Atom
SOURCES = [
    {
        "name": "fia-decisions",
        "type": "fia_docs",
        "url": "https://www.fia.com/documents/",
        "base": "https://www.fia.com",
    },
    {
        "name": "fia-news",
        "type": "html",
        "url": "https://www.fia.com/news",
        "base": "https://www.fia.com",
        "link_re": r'href="(/news/[^"]+)"[^>]*>(.*?)</a>',
    },
    {
        "name": "f1-latest",
        "type": "html",
        "url": "https://www.formula1.com/en/latest.html",
        "base": "https://www.formula1.com",
        "link_re": r'href="(/en/latest/article/[^"?]+)"[^>]*>(.*?)</a>',
    },
    {
        "name": "the-race",
        "type": "rss",
        "url": "https://www.the-race.com/rss/",
    },
    {
        "name": "motorsport",
        "type": "rss",
        "url": "https://www.motorsport.com/rss/f1/news/",
    },
]


# ---------------------------------------------------------------- 工具
def fetch(url, timeout=30, binary=False):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            break
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    else:
        raise last
    return data if binary else data.decode("utf-8", "ignore")


def clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def slugify(s, maxlen=120):
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", s).strip("-")
    return s[:maxlen] or "item"


def load_seen():
    if os.path.exists(STATE):
        try:
            with open(STATE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=0)


def pdf_to_text(path):
    """有 pdftotext 就抽文本，没有就只存 PDF。"""
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-layout", path, "-"],
                             capture_output=True, timeout=60)
        if out.returncode == 0:
            return out.stdout.decode("utf-8", "ignore")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- 解析
def latest_season_url(index_url):
    """FIA 文件页默认停在上一季，这里自动找最新赛季页。"""
    page = fetch(index_url)
    found = re.findall(
        r'(?:href|value)="(?:https://www\.fia\.com)?(/documents/championships/fia-formula-one-world-championship-14/season/season-(\d{4})-\d+)"',
        page)
    if not found:
        return index_url
    best = max(found, key=lambda x: int(x[1]))[0]
    return "https://www.fia.com" + best


def parse_fia_docs(src):
    url = src.get("season_url") or latest_season_url(src["url"])
    page = fetch(url)
    hits = re.findall(r'href="(/system/files/decision-document/[^"]+\.pdf)"', page)
    items, seen_local = [], set()
    for path in hits:
        if path in seen_local:
            continue
        seen_local.add(path)
        name = urllib.parse.unquote(path.rsplit("/", 1)[-1]).rsplit(".pdf", 1)[0]
        title = name.replace("_", " ").strip()
        items.append({"title": title, "url": src["base"] + path, "kind": "pdf"})
    return items


def parse_html(src):
    page = fetch(src["url"])
    items, seen_local = [], set()
    for path, inner in re.findall(src["link_re"], page, re.S):
        if path in seen_local:
            continue
        title = clean(inner)
        if len(title) < 8:          # 过滤「Read more」之类
            continue
        seen_local.add(path)
        items.append({"title": title, "url": src["base"] + path, "kind": "page"})
    return items


def parse_rss(src):
    raw = fetch(src["url"])
    items = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return items
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    nodes = root.findall(".//item") or root.findall(".//atom:entry", ns)
    for n in nodes:
        title = (n.findtext("title") or "").strip()
        link = (n.findtext("link") or "").strip()
        if not link:
            le = n.find("atom:link", ns)
            link = le.get("href", "") if le is not None else ""
        date = (n.findtext("pubDate") or n.findtext("atom:updated", default="", namespaces=ns) or "").strip()
        if title and link:
            items.append({"title": clean(title), "url": link, "kind": "page", "date": date})
    return items


PARSERS = {"fia_docs": parse_fia_docs, "html": parse_html, "rss": parse_rss}


# ---------------------------------------------------------------- 存储
def save_item(item, src_name, day, is_pdf, download_pdf):
    folder = os.path.join(ARCHIVE, day, src_name)
    os.makedirs(folder, exist_ok=True)
    slug = slugify(item["title"], 120) or slugify(item["url"].rsplit("/", 1)[-1])
    md_path = os.path.join(folder, slug + ".md")
    if os.path.exists(md_path):
        try:
            head = open(md_path, encoding="utf-8").read(400)
        except Exception:
            head = ""
        if item["url"] not in head:          # 同名但不同条目，加哈希区分
            import hashlib
            slug += "-" + hashlib.sha1(item["url"].encode()).hexdigest()[:4]
            md_path = os.path.join(folder, slug + ".md")

    local_file = ""
    body = ""
    if is_pdf and download_pdf:
        pdf_path = os.path.join(folder, slug + ".pdf")
        try:
            data = fetch(item["url"], timeout=90, binary=True)
            with open(pdf_path, "wb") as f:
                f.write(data)
            local_file = os.path.relpath(pdf_path, ROOT)
            text = pdf_to_text(pdf_path)
            if text:
                body = text.strip()
        except Exception as e:
            body = f"[PDF 下载失败：{e}]"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {item['title']}\n\n")
        f.write(f"- 来源：{src_name}\n")
        f.write(f"- 链接：{item['url']}\n")
        f.write(f"- 采集时间：{datetime.now(CST).strftime('%Y-%m-%d %H:%M')}\n")
        if item.get("date"):
            f.write(f"- 发布时间：{item['date']}\n")
        if local_file:
            f.write(f"- 本地文件：{local_file}\n")
        f.write("\n---\n\n")
        f.write(body if body else "（正文未抽取，请打开原链接或本地 PDF）\n")

    return os.path.relpath(md_path, ROOT), len(body)


# ---------------------------------------------------------------- 推送
def push_webhook(text, url):
    """自动适配飞书 / 钉钉 / 企业微信。"""
    if not url:
        return
    if "feishu" in url or "larksuite" in url:
        payload = {"msg_type": "text", "content": {"text": text}}
    elif "dingtalk" in url:
        payload = {"msgtype": "text", "text": {"content": text}}
    elif "weixin" in url or "qyapi" in url:
        payload = {"msgtype": "text", "text": {"content": text}}
    else:
        payload = {"text": text}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"[webhook] 推送失败：{e}", file=sys.stderr)


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--limit", type=int, default=15)
    args = ap.parse_args()

    day = datetime.now(CST).strftime("%Y-%m-%d")
    seen = load_seen()
    new_items, errors = [], []

    for src in SOURCES:
        try:
            items = PARSERS[src["type"]](src)
        except Exception as e:
            errors.append(f"{src['name']}: {e}")
            print(f"[{src['name']}] 失败：{e}", file=sys.stderr)
            continue

        fresh = [i for i in items if i["url"] not in seen][: args.limit]
        print(f"[{src['name']}] 抓到 {len(items)} 条，其中新增 {len(fresh)} 条")

        for it in fresh:
            if args.dry_run:
                print(f"    · {it['title'][:70]}")
                continue
            rel, n = save_item(it, src["name"], day, it["kind"] == "pdf", not args.no_pdf)
            seen.add(it["url"])
            new_items.append((src["name"], it["title"], it["url"], rel, n))

    if args.dry_run:
        return

    save_seen(seen)

    # 摘要
    os.makedirs(ARCHIVE, exist_ok=True)
    lines = [f"# F1 素材摘要 · {datetime.now(CST).strftime('%Y-%m-%d %H:%M')}", ""]
    if not new_items:
        lines.append("本轮无新增。")
    else:
        cur = None
        for src_name, title, url, rel, n in new_items:
            if src_name != cur:
                lines.append(f"\n## {src_name}\n")
                cur = src_name
            flag = f"（正文 {n} 字）" if n else ""
            lines.append(f"- [{title}]({url}) {flag}")
    lines.append("\n> 由 collect.py 自动生成。PDF 原文在 archive/日期/ 下。")

    digest = "\n".join(lines)
    with open(os.path.join(ARCHIVE, "latest.md"), "w", encoding="utf-8") as f:
        f.write(digest)
    with open(os.path.join(ARCHIVE, f"digest-{day}.md"), "w", encoding="utf-8") as f:
        f.write(digest)

    print(f"\n新增 {len(new_items)} 条，摘要已写入 archive/latest.md")
    if errors:
        print("错误：\n  " + "\n  ".join(errors), file=sys.stderr)

    # 只推新增，避免刷屏
    if new_items:
        head = digest[:1800]
        push_webhook(head, os.environ.get("WEBHOOK_URL", ""))


if __name__ == "__main__":
    main()
