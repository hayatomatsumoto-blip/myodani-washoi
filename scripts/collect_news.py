#!/usr/bin/env python3
"""名谷の最新情報を自動収集して data/news.json に書く。

情報源:
  - 須磨パティオ WordPress REST API（認証不要）
  - おでかけKOBE sitemap + __NUXT_DATA__（認証不要）

フィルタ（おでかけKOBE）:
  - 区コードに suma を含む
  - かつ 名谷周辺キーワードにヒット
  - 垂水区名谷町を除外
"""

from __future__ import annotations

import concurrent.futures
import html
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news.json"

UA = "myodani-washoi-news-collector/1.0 (+https://github.com/hayatomatsumoto-blip/myodani-washoi)"
PATIO_TYPES = ("event", "news", "shopnews")
ODEKAKE_SITEMAP = "https://event.city.kobe.lg.jp/sitemap.xml"

# 名谷駅周辺（須磨区）を拾う語。垂水区「名谷町」単体は TARUMI_EXCLUDE で落とす。
MYODANI_KEYWORDS = (
    "名谷",
    "須磨パティオ",
    "パティオ",
    "中落合",
    "北落合",
    "南落合",
    "友が丘",
    "多井畑",
    "北須磨",
    "tete名谷",
    "ヒトトバル",
    "おやこふらっと",
    "SUMAile",
    "すまいれ",
    "落合中央公園",
    "名谷図書館",
    "名谷駅",
    "名谷あそび",
)
TARUMI_EXCLUDE = ("垂水区名谷町", "垂水区名谷")


def fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8", "replace")


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def item(
    *,
    id_: str,
    title: str,
    summary: str,
    url: str,
    source: str,
    starts_at: str | None = None,
    ends_at: str | None = None,
    fetched_at: str | None = None,
) -> dict:
    return {
        "id": id_,
        "title": title.strip(),
        "summary": (summary or "").strip(),
        "url": url,
        "source": source,
        "startsAt": starts_at,
        "endsAt": ends_at,
        "fetchedAt": fetched_at or now_iso(),
    }


# --- 須磨パティオ ---------------------------------------------------------

def collect_patio() -> list[dict]:
    items: list[dict] = []
    for ptype in PATIO_TYPES:
        page = 1
        while page <= 20:
            url = (
                f"https://patio.gr.jp/wp-json/wp/v2/{ptype}"
                f"?per_page=50&page={page}"
                f"&_fields=id,title,link,date,excerpt"
            )
            try:
                raw = fetch(url)
            except urllib.error.HTTPError as e:
                if e.code == 400:
                    break
                raise
            rows = json.loads(raw)
            if not rows:
                break
            for row in rows:
                title = strip_html(row.get("title", {}).get("rendered", ""))
                summary = strip_html(row.get("excerpt", {}).get("rendered", ""))
                items.append(
                    item(
                        id_=f"patio-{ptype}-{row['id']}",
                        title=title,
                        summary=summary[:280],
                        url=row.get("link") or "",
                        source="須磨パティオ",
                        starts_at=row.get("date"),
                    )
                )
            if len(rows) < 50:
                break
            page += 1
    return items


# --- おでかけKOBE ---------------------------------------------------------

def resolve_ref(data: list, ref, seen: set | None = None):
    if seen is None:
        seen = set()
    if not isinstance(ref, int) or ref in seen or ref < 0 or ref >= len(data):
        return None
    seen = seen | {ref}
    v = data[ref]
    if isinstance(v, (str, bool, float, type(None), int)):
        return v
    if isinstance(v, list):
        if v and v[0] == "Date":
            return v[1]
        if v and isinstance(v[0], str) and v[0] in (
            "ShallowReactive",
            "Reactive",
            "Ref",
            "EmptyRef",
            "EmptyReactive",
        ):
            return resolve_ref(data, v[1], seen)
        return [resolve_ref(data, x, seen) if isinstance(x, int) else x for x in v]
    if isinstance(v, dict):
        return {k: resolve_ref(data, x, seen) for k, x in v.items()}
    return v


def parse_odekake_page(url: str) -> dict | None:
    try:
        html_text = fetch(url, timeout=25)
    except Exception:
        return None
    m = re.search(
        r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html_text, re.S
    )
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    root = resolve_ref(data, 1)
    if not isinstance(root, dict) or "data" not in root:
        return None
    values = list(root["data"].values())
    if not values:
        return None
    ev = values[0]
    if not isinstance(ev, dict):
        return None
    if ev.get("status") and ev.get("status") != "published":
        return None
    ed = ev.get("entryData") or {}
    event = ed.get("event") or {}
    base = ed.get("base") or {}
    web = ed.get("web") or {}
    areas = event.get("area") or []
    if isinstance(areas, str):
        areas = [areas]
    title = strip_html(base.get("name") or "")
    summary = strip_html(web.get("summary") or base.get("summary") or "")
    location = strip_html(event.get("location") or "")
    return {
        "id": ev.get("id") or url.rsplit("/", 1)[-1],
        "title": title,
        "summary": summary[:280],
        "url": url,
        "areas": areas,
        "location": location,
        "startsAt": base.get("startDate") or base.get("startDateTime"),
        "endsAt": base.get("endDate") or base.get("endDateTime"),
    }


def is_myodani_odekake(row: dict) -> bool:
    areas = row.get("areas") or []
    if "suma" not in areas:
        return False
    blob = f"{row.get('title','')} {row.get('summary','')} {row.get('location','')}"
    if any(x in blob for x in TARUMI_EXCLUDE):
        return False
    # 垂水区の住所に「名谷」が紛れても、須磨区以外の単独住所なら落とす
    if "垂水区" in blob and "須磨区" not in blob and "名谷" in blob:
        return False
    return any(k in blob for k in MYODANI_KEYWORDS)


def collect_odekake(workers: int = 8) -> list[dict]:
    xml = fetch(ODEKAKE_SITEMAP, timeout=60)
    urls = re.findall(
        r"<loc>(https://event\.city\.kobe\.lg\.jp/event/[^<]+)</loc>", xml
    )
    items: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for row in ex.map(parse_odekake_page, urls):
            if not row or not is_myodani_odekake(row):
                continue
            items.append(
                item(
                    id_=f"odekake-{row['id']}",
                    title=row["title"],
                    summary=row["summary"],
                    url=row["url"],
                    source="おでかけKOBE",
                    starts_at=row.get("startsAt"),
                    ends_at=row.get("endsAt"),
                )
            )
    return items


# --- merge / write --------------------------------------------------------

def sort_key(it: dict):
    return it.get("startsAt") or it.get("fetchedAt") or ""


def merge(items: list[dict]) -> dict:
    # id で重複排除。新しい fetchedAt を優先
    by_id: dict[str, dict] = {}
    for it in items:
        prev = by_id.get(it["id"])
        if not prev or (it.get("fetchedAt") or "") >= (prev.get("fetchedAt") or ""):
            by_id[it["id"]] = it
    ordered = sorted(by_id.values(), key=sort_key, reverse=True)
    return {
        "updatedAt": now_iso(),
        "count": len(ordered),
        "items": ordered,
    }


def main() -> int:
    print("collect patio…", flush=True)
    patio = collect_patio()
    print(f"  patio: {len(patio)}", flush=True)
    print("collect odekake…", flush=True)
    odekake = collect_odekake()
    print(f"  odekake(myodani): {len(odekake)}", flush=True)
    payload = merge(patio + odekake)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} ({payload['count']} items)", flush=True)
    # 一覧サマリを stdout に
    for it in payload["items"][:40]:
        print(
            f"- [{it['source']}] {it['title'][:60]} | {it.get('startsAt') or '-'} | {it['url']}",
            flush=True,
        )
    if payload["count"] > 40:
        print(f"… and {payload['count'] - 40} more", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
