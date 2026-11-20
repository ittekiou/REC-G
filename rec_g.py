#!/usr/bin/env python3
"""REC-G｜RSS Egg Collection Garden の仕入れ係。

eggs.txt があるフォルダを一つの庭とみなし、
  eggs.txt     … 卵の一覧（ページのURLを一行に一つ）
  shelves.txt  … 棚割り（なくてもよい）
を読んで、同じフォルダに
  garden.json  … ページ（index.html）が読む台帳
  feed.xml     … 庭ぜんぶの新着RSS
を書き出す。人が書くのはテキスト二枚だけ。

使い方:  python3 rec_g.py [--page 見本のindex.html] [フォルダ ...]
         フォルダを省略すると、下にある eggs.txt を全部さがす。
         --page を付けると、その index.html を各庭に配る（見本を直せば、全部の庭が揃う）。
         <!-- rec-g: keep --> と書いた index.html は配らずに残す（自分で作り変えた庭のため）。
Pythonの標準ライブラリだけで動く。
"""
import html
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime, format_datetime
from urllib.parse import urljoin, urlsplit

JST = timezone(timedelta(hours=9))
UA = "REC-G/0.1 (RSS Egg Collection Garden)"
KEEP = 3          # 一つの卵に残す新着の数
FEED_KEEP = 20    # feed.xml に載せる数
PAUSE = 1.0       # 一回ごとの待ち時間（秒）
MEDIA = "{http://search.yahoo.com/mrss/}"
ATOM = "{http://www.w3.org/2005/Atom}"
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"


# ---------- テキスト二枚を読む ----------

URL_RE = re.compile(r"https?://\S+")


def norm(u):
    """同じ卵かどうかを見るための形（末尾の / や http/https の違いを無視）。"""
    return re.sub(r"^https?://", "", u.strip()).rstrip("/").lower()


def read_eggs(path):
    title, site, eggs, names = "", "", [], {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            m = re.match(r"^(title|url)\s*[:：]\s*(.+)$", s, re.I)
            if m:
                if m.group(1).lower() == "title":
                    title = m.group(2).strip()
                else:
                    site = m.group(2).split()[0]
                continue
            u = URL_RE.match(s)
            if u and norm(u.group(0)) not in {norm(e) for e in eggs}:
                eggs.append(u.group(0))
                rest = s[u.end():]
                if "｜" in rest or "|" in rest:          # 「URL ｜ 表示名」なら、その名前で並べる
                    name = re.split(r"[｜|]", rest, maxsplit=1)[1].strip()
                    if name:
                        names[norm(u.group(0))] = name
    return title, site, eggs, names


def read_shelves(path):
    shelves, place, cur, n = [], {}, None, 0
    if not os.path.exists(path):
        return shelves, place
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or (s.startswith("#") and not s.startswith("## ")):
                continue
            if s.startswith("## "):
                head, _, note = s[3:].partition("｜")
                sid, _, name = head.strip().partition(" ")
                cur = {"id": sid, "name": name.strip() or sid, "note": note.strip()}
                shelves.append(cur)
                n = 0
                continue
            u = URL_RE.match(s)
            if u and cur:
                n += 1
                place.setdefault(norm(u.group(0)), (cur["id"], n, u.group(0)))
    return shelves, place


# ---------- 札（nest.json）から卵を拾う ----------

def eggs_from_nest(folder):
    """札（nest.json）から卵を拾う。CHIC TEC の私書箱（box/NNN/rec-g/）なら部屋の札を自動で読む。
    それ以外の庭は、eggs.txt に「nest: ../nest.json」のように書いたときだけ読む。
    RSS（feeds）があればそれを、なければ本拠地のリンク（links）を卵にする。
    GitHub の申し込みページなど、卵にならないリンクは飛ばす。"""
    here = os.path.abspath(folder)
    room = os.path.dirname(here)
    is_box = re.fullmatch(r"\d{3}", os.path.basename(room) or "") and os.path.basename(os.path.dirname(room)) == "box"
    path = None
    if is_box:                                            # CHIC TEC の私書箱（box/001/rec-g/ など）は自動で
        path = os.path.join(room, "nest.json")
    else:                                                 # ほかの庭は eggs.txt に「nest: 札の場所」と書いたときだけ
        try:
            with open(os.path.join(here, "eggs.txt"), encoding="utf-8") as f:
                m = re.search(r"^nest\s*[:：]\s*(\S+)", f.read(), re.M)
            if m:
                path = os.path.normpath(os.path.join(here, m.group(1)))
        except OSError:
            pass
    if not path or not os.path.exists(path):
        return "", []
    try:
        with open(path, encoding="utf-8") as f:
            nest = json.load(f)
    except Exception:
        return "", []
    name = (nest.get("name") or "").strip()
    if name.startswith("🈳"):                             # 空き部屋の札からは卵を拾わない（名前だけ）
        return name, []
    feeds = [x if isinstance(x, str) else (x or {}).get("url", "") for x in nest.get("feeds", [])]
    eggs = [u for u in feeds if URL_RE.match(u or "")]
    if not eggs:
        for l in nest.get("links", []):
            u = (l or {}).get("url", "")
            host = (urlsplit(u).hostname or "").lower()
            if URL_RE.match(u) and host not in ("github.com", "www.github.com") and "/rec-g" not in u:
                eggs.append(u)
    return name, eggs


# ---------- ページのURLから RSS を見つける ----------

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(), r.geturl()


def known_feed(url):
    """よく使う場所は、ページを読まずに RSS の住所がわかる。"""
    p = urlsplit(url)
    host, path = (p.hostname or "").lower(), p.path.rstrip("/")
    if host == "note.com" and path:                       # note のアカウント・マガジン
        return f"https://note.com{path}/rss"
    if host == "bsky.app" and path.startswith("/profile/"):
        return f"https://bsky.app{path}/rss"
    if host == "medium.com" and path.startswith("/@"):
        return f"https://medium.com/feed/{path[1:]}"
    if host.endswith(".substack.com"):
        return f"https://{host}/feed"
    if host.endswith(".medium.com"):
        return f"https://{host}/feed"
    return None


def looks_like_feed(data):
    head = data[:600].lstrip().lower()
    return head.startswith(b"<?xml") or b"<rss" in head or b"<feed" in head


def find_feed(url):
    """戻り値：(RSSの住所, RSSの中身)。見つからなければ例外。"""
    k = known_feed(url)
    if k:
        return k, fetch(k)[0]
    data, final = fetch(url)
    if looks_like_feed(data):                             # 最初から RSS の住所だった
        return url, data
    page = data.decode("utf-8", "replace")
    for m in re.finditer(r"<link\b[^>]*>", page, re.I):   # ページの中の RSS の印
        tag = m.group(0)
        if re.search(r'rel=["\']?alternate', tag, re.I) and re.search(r"(rss|atom)\+xml", tag, re.I):
            h = re.search(r'href=["\']([^"\']+)', tag, re.I)
            if h:
                f = urljoin(final, html.unescape(h.group(1)))
                time.sleep(PAUSE)
                return f, fetch(f)[0]
    raise ValueError("RSS が見つからない")


# ---------- RSS を読む ----------

def any_date(s):
    s = (s or "").strip()
    if not s:
        return ""
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(JST).isoformat()
    except ValueError:
        try:
            return parsedate_to_datetime(s).astimezone(JST).isoformat()
        except Exception:
            return ""


def plain(text, limit=60):
    t = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[:limit - 1] + "…"


def image_of(it):
    enc = it.find("enclosure")
    if enc is not None and enc.get("type", "").startswith("image") and enc.get("url"):
        return enc.get("url")
    for th in it.iter(f"{MEDIA}thumbnail"):
        u = th.get("url") or (th.text or "").strip()
        if u:
            return u
    for mc in it.iter(f"{MEDIA}content"):
        if mc.get("medium") == "image" and mc.get("url"):
            return mc.get("url")
    im = it.find(f"{ITUNES}image")
    if im is not None and im.get("href"):
        return im.get("href")
    for body in (it.findtext("description"), it.findtext(CONTENT), it.findtext(f"{ATOM}content")):
        m = re.search(r'<img[^>]+src=["\']([^"\']+)', html.unescape(body or ""))
        if m:
            return html.unescape(m.group(1))
    return ""


def read_feed(data):
    data = re.sub(rb"&(?!(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#x[0-9A-Fa-f]+);)", b"&amp;", data)
    root = ET.fromstring(data)
    items = []
    if root.tag == f"{ATOM}feed":
        title = (root.findtext(f"{ATOM}title") or "").strip()
        link = ""
        for l in root.findall(f"{ATOM}link"):
            if l.get("rel", "alternate") == "alternate":
                link = l.get("href", "")
        for e in root.iter(f"{ATOM}entry"):
            href = ""
            for l in e.findall(f"{ATOM}link"):
                if l.get("rel", "alternate") == "alternate":
                    href = l.get("href", "")
            text = e.findtext(f"{ATOM}summary") or e.findtext(f"{ATOM}content")
            items.append({"title": (e.findtext(f"{ATOM}title") or "").strip() or plain(text, 40),
                          "url": href, "image": image_of(e),
                          "date": any_date(e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated"))})
    else:
        ch = root.find("channel")
        title = (ch.findtext("title") or "").strip() if ch is not None else ""
        link = (ch.findtext("link") or "").strip() if ch is not None else ""
        for it in root.iter("item"):
            items.append({"title": (it.findtext("title") or "").strip() or plain(it.findtext("description"), 40),
                          "url": (it.findtext("link") or "").strip(), "image": image_of(it),
                          "date": any_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date"))})
    items = [i for i in items if i["url"] and i["title"]]
    items.sort(key=lambda i: i["date"], reverse=True)
    return title, link, items


# ---------- 書き出す ----------

def write_feed(garden, out, page):
    from xml.sax.saxutils import escape as esc
    rows = []
    for egg in garden["eggs"]:
        for it in egg.get("latest", []):
            rows.append((it, egg["title"]))
    rows.sort(key=lambda r: r[0]["date"], reverse=True)
    seen, lines = set(), [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">', "<channel>",
        f"<title>{esc(garden['title'])}</title>", f"<link>{esc(page)}</link>",
        f"<description>{esc(garden['title'])}｜REC-G で集めた新着</description>",
        f"<lastBuildDate>{format_datetime(datetime.now(JST).replace(microsecond=0))}</lastBuildDate>"]
    for it, src in rows:
        if it["url"] in seen or len(seen) >= FEED_KEEP:
            continue
        seen.add(it["url"])
        lines += ["<item>", f"<title>{esc(it['title'])}</title>", f"<link>{esc(it['url'])}</link>",
                  f'<guid isPermaLink="true">{esc(it["url"])}</guid>',
                  f"<category>{esc(src)}</category>", f"<description>{esc(src)}</description>"]
        if it["date"]:
            lines.append(f"<pubDate>{format_datetime(datetime.fromisoformat(it['date']))}</pubDate>")
        if it["image"]:
            lines.append(f'<media:thumbnail url="{esc(it["image"])}"/>')
        lines.append("</item>")
    lines += ["</channel>", "</rss>", ""]
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def build(folder):
    eggs_txt = os.path.join(folder, "eggs.txt")
    title, site, eggs, names = read_eggs(eggs_txt)
    nest_name, nest_eggs = eggs_from_nest(folder)         # 札にある卵を先頭に
    have = {norm(e) for e in eggs}
    eggs = [u for u in nest_eggs if norm(u) not in have] + eggs
    if not title and nest_name:
        title = nest_name + "の集卵処"
    shelves, place = read_shelves(os.path.join(folder, "shelves.txt"))
    for key, (_, _, orig) in place.items():               # 棚にだけ書いた卵も、卵として扱う
        if key not in {norm(e) for e in eggs}:
            eggs.append(orig)

    old = {}
    gj = os.path.join(folder, "garden.json")
    if os.path.exists(gj):                                # 読めなかった卵は、前回の中身のまま
        try:
            old = {norm(e["page"]): e for e in json.load(open(gj, encoding="utf-8")).get("eggs", [])}
        except Exception:
            pass

    out = []
    for n, page in enumerate(eggs):
        shelf, order, _ = place.get(norm(page), ("", 900 + n, page))
        egg = {"page": page, "shelf": shelf, "order": order}
        try:
            feed, data = find_feed(page)
            t, link, items = read_feed(data)
            egg.update({"feed": feed, "title": names.get(norm(page)) or t or page, "link": link or page,
                        "latest": items[:KEEP], "latest_at": items[0]["date"] if items else "", "ok": True})
            print(f"ok   {page} -> {feed} ({len(items)})")
        except Exception as e:
            prev = old.get(norm(page), {})
            egg.update({"feed": prev.get("feed", ""), "title": names.get(norm(page)) or prev.get("title", page),
                        "link": prev.get("link", page), "latest": prev.get("latest", []),
                        "latest_at": prev.get("latest_at", ""), "ok": False})
            print(f"skip {page}: {type(e).__name__}: {e}", file=sys.stderr)
        out.append(egg)
        time.sleep(PAUSE)

    garden = {"title": title or "REC-G", "url": site, "updated": datetime.now(JST).replace(microsecond=0).isoformat(),
              "shelves": shelves, "eggs": out}
    with open(gj, "w", encoding="utf-8") as f:
        json.dump(garden, f, ensure_ascii=False, indent=2)
        f.write("\n")
    write_feed(garden, os.path.join(folder, "feed.xml"), site or "./")
    print(f"garden: {folder} ({len(out)} eggs, {len(shelves)} shelves)")


def find_gardens(top="."):
    for d, dirs, files in os.walk(top):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        if "eggs.txt" in files:
            yield d


def deliver_page(page, folders):
    """見本の index.html を、各庭に配る。中身が同じなら何もしない。"""
    with open(page, encoding="utf-8") as f:
        master = f.read()
    for d in folders:
        dst = os.path.join(d, "index.html")
        if os.path.abspath(dst) == os.path.abspath(page):
            continue
        cur = ""
        if os.path.exists(dst):
            with open(dst, encoding="utf-8") as f:
                cur = f.read()
            if "<!-- rec-g: keep -->" in cur:
                print(f"keep {dst}")
                continue
        if cur != master:
            with open(dst, "w", encoding="utf-8") as f:
                f.write(master)
            print(f"page {dst}")


if __name__ == "__main__":
    args, page = sys.argv[1:], None
    if "--page" in args:
        i = args.index("--page")
        page = args[i + 1]
        del args[i:i + 2]
    folders = args or list(find_gardens())
    if page and os.path.exists(page):
        deliver_page(page, folders)
    for folder in folders:
        build(folder)
