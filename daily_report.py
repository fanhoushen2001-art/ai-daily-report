#!/usr/bin/env python3
"""AI 日报 —— 每天17:00 在 GitHub Actions 上运行，推送到飞书"""
import json, os, re, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError

UA = "Mozilla/5.0 (compatible; AI-Daily-Report/1.0)"
BJT = timezone(timedelta(hours=8))
FEISHU_APP_ID = os.environ["FEISHU_APP_ID"]
FEISHU_APP_SECRET = os.environ["FEISHU_APP_SECRET"]
CHAT_ID = os.environ.get("FEISHU_CHAT_ID", "oc_2277f3a0958bcc1d546735c6e51014f5")


def http_get(url, headers=None):
    h = {"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    try:
        with urlopen(Request(url, headers=h), timeout=20) as r:
            data = r.read().decode()
            ct = r.headers.get("Content-Type", "")
            return json.loads(data) if "json" in ct else data
    except HTTPError as e:
        return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": str(e)}


def http_post(url, data, headers=None):
    h = {"User-Agent": UA, "Content-Type": "application/json", **(headers or {})}
    body = json.dumps(data).encode() if isinstance(data, dict) else data
    with urlopen(Request(url, data=body, headers=h), timeout=15) as r:
        return json.loads(r.read())


# ─── 数据采集 ───

def fetch_aihot():
    today = datetime.now(BJT).strftime("%Y-%m-%d")
    for d in [today, ""]:
        url = f"https://aihot.virxact.com/api/public/daily/{d}" if d else "https://aihot.virxact.com/api/public/daily"
        r = http_get(url, {"User-Agent": f"{UA} (aihot)"})
        if isinstance(r, dict) and r.get("date"):
            return r
    return None


def fetch_hackernews(n=10):
    ids = http_get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not isinstance(ids, list): return []
    items = []
    for sid in ids[:n]:
        item = http_get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
        if isinstance(item, dict) and item.get("title"):
            items.append(item)
    return items


def fetch_36kr(n=8):
    raw = http_get("https://www.36kr.com/feed", {"Accept": "application/xml"})
    if not isinstance(raw, str) or "<entry" not in raw: return []
    try:
        root = ET.fromstring(raw)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        items = []
        for e in entries[:n]:
            title = e.findtext("{http://www.w3.org/2005/Atom}title", "")
            link_el = e.find("{http://www.w3.org/2005/Atom}link")
            href = link_el.get("href", "") if link_el is not None else ""
            if title: items.append({"title": title.strip(), "url": href})
        return items
    except Exception:
        return []


def fetch_aibase(n=5):
    html = http_get("https://www.aibase.com/zh/news")
    if not isinstance(html, str): return []
    pattern = re.compile(r'<a[^>]*href="(/zh/news/\d+)"[^>]*>([^<]+)</a>')
    seen, items = set(), []
    for href, title in pattern.findall(html):
        t = title.strip()
        if t and t not in seen and len(t) > 4:
            seen.add(t)
            items.append({"title": t, "url": f"https://www.aibase.com{href}"})
            if len(items) >= n: break
    return items


def fetch_devto(n=5):
    data = http_get(f"https://dev.to/api/articles?top=1&per_page={n}")
    if not isinstance(data, list): return []
    return [{"title": a["title"], "url": a["url"], "tags": a.get("tags", [])[:3]} for a in data if a.get("title")]


def fetch_arxiv(n=5):
    raw = http_get(
        "https://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=5",
        {"Accept": "application/xml"}
    )
    if not isinstance(raw, str): return []
    titles = re.findall(r"<title>(.*?)</title>", raw, re.DOTALL)
    links = re.findall(r"<id>(.*?)</id>", raw, re.DOTALL)
    items = []
    for i in range(min(n, len(titles))):
        t = titles[i].strip().removeprefix("Title:").strip()
        items.append({"title": t, "url": links[i].strip() if i < len(links) else ""})
    return items


# ─── 飞书卡片 ───

def get_tenant_token():
    return http_post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    ).get("tenant_access_token", "")


def send_card(token, card):
    return http_post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        {"receive_id": CHAT_ID, "msg_type": "interactive", "content": json.dumps(card, ensure_ascii=False)},
        {"Authorization": f"Bearer {token}"}
    )


def build_card(aihot, hn, kr36, aibase, devto, arxiv):
    today = datetime.now(BJT)
    date_str = today.strftime("%Y-%m-%d")
    wd = ["一","二","三","四","五","六","日"][today.weekday()]
    elements = []

    def add_section(title, lines):
        if lines:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"**{title}**\n" + "\n".join(lines)}})
            elements.append({"tag": "hr"})

    # AI HOT
    if aihot and aihot.get("sections"):
        for sec in aihot["sections"]:
            items = sec.get("items", [])[:5]
            if items:
                lines = []
                for idx, it in enumerate(items, 1):
                    t, s, u = it.get("title",""), it.get("sourceName",""), it.get("sourceUrl","")
                    lines.append(f"{idx}. [{t}]({u}) — {s}" if u else f"{idx}. **{t}** — {s}")
                add_section(f"🤖 {sec.get('label','AI 动态')}", lines)

    # HackerNews
    if hn:
        lines = []
        for i, it in enumerate(hn[:8], 1):
            t, s, u = it.get("title",""), it.get("score",0), it.get("url","")
            lines.append(f"{i}. [{t}]({u}) ⭐{s}" if u else f"{i}. **{t}** ⭐{s}")
        add_section("📰 HackerNews 热门", lines)

    # 36氪
    if kr36:
        lines = [f"{i}. [{it['title']}]({it['url']})" for i, it in enumerate(kr36[:6], 1)]
        add_section("🇨🇳 36氪精选", lines)

    # AIbase
    if aibase:
        lines = [f"{i}. [{it['title']}]({it['url']})" for i, it in enumerate(aibase[:5], 1)]
        add_section("🧪 AIbase", lines)

    # Dev.to
    if devto:
        lines = []
        for i, it in enumerate(devto[:4], 1):
            tag_str = f" `{','.join(it['tags'])}`" if it.get('tags') else ""
            lines.append(f"{i}. [{it['title']}]({it['url']}){tag_str}")
        add_section("🔧 Dev.to 开发者精选", lines)

    # ArXiv
    if arxiv:
        lines = [f"{i}. [{it['title']}]({it['url']})" for i, it in enumerate(arxiv[:4], 1)]
        add_section("📚 ArXiv AI 论文", lines)

    # 页脚
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": f"🤖 AI 日报 · {date_str} 周{wd} · 数据来源：AI HOT / HN / 36氪 / AIbase / Dev.to / ArXiv"}]
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": f"🤖 AI 日报 · {date_str} 周{wd}"}, "template": "blue"},
        "elements": elements
    }


# ─── 主入口 ───

def main():
    print(f"=== AI 日报 {datetime.now(BJT).strftime('%Y-%m-%d %H:%M')} ===")
    sources = [
        ("AI HOT", fetch_aihot),
        ("HackerNews", lambda: fetch_hackernews(10)),
        ("36氪", lambda: fetch_36kr(8)),
        ("AIbase", lambda: fetch_aibase(5)),
        ("Dev.to", lambda: fetch_devto(5)),
        ("ArXiv", lambda: fetch_arxiv(5)),
    ]
    results = {}
    for name, fn in sources:
        print(f"  [{name}]...", end=" ", flush=True)
        try:
            data = fn()
            count = len(data) if isinstance(data, (list, dict)) and not isinstance(data, dict) or (isinstance(data, dict) and data.get("sections")) else (1 if data else 0)
            if isinstance(data, dict) and data.get("sections"):
                count = sum(len(s.get("items",[])) for s in data["sections"])
            results[name] = data
            print(f"{count}条 ✓")
        except Exception as e:
            results[name] = None
            print(f"失败: {e}")

    print(f"  发送卡片...", end=" ", flush=True)
    token = get_tenant_token()
    if not token:
        print("❌ 无法获取 token")
        return
    card = build_card(
        results.get("AI HOT"),
        results.get("HackerNews"),
        results.get("36氪"),
        results.get("AIbase"),
        results.get("Dev.to"),
        results.get("ArXiv"),
    )
    r = send_card(token, card)
    print("✅ 成功!" if r.get("code") == 0 else f"❌ {r.get('msg')}")
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
