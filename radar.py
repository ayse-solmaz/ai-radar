"""AI Radar: feeds.yaml içindeki RSS kaynaklarını tarar ve bir web sayfası üretir.

Puanlama (ilgi etiketleri) tarayıcıda yapılır; bu betik sadece yeni yazıları toplar
ve sayfanın içine gömer. Böylece etiketleri sayfada değiştirip sonucu hemen görebilirsin.

Kullanım:
    python radar.py              # önizleme: output/preview.html (seen.json'a dokunmaz)
    python radar.py --hours 72   # daha geniş zaman aralığı
    python radar.py --publish    # siteyi site/ içine yaz, seen.json'u güncelle (GitHub Actions bunu çalıştırır)
    python radar.py --publish --restore https://kullanici.github.io/ai-radar/
                                 # önceki günleri canlı siteden indirip arşive ekle
    python radar.py --publish --restore URL --reset-archive
                                 # arşivi sıfırla: sadece bugünün sayfası kalır
    python radar.py --publish --all   # daha önce gösterilenleri de tekrar al
    python radar.py --no-open    # sayfayı tarayıcıda açma
"""
import argparse
import hashlib
import html
import json
import re
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests
import yaml

ROOT = Path(__file__).parent
SEEN_FILE = ROOT / "seen.json"
TEMPLATE = ROOT / "template.html"
SITE_DIR = ROOT / "site"
ARCHIVE_DIR = SITE_DIR / "archive"
PREVIEW_FILE = ROOT / "output" / "preview.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (ai-radar kisisel RSS okuyucu)"}
SEEN_KEEP_DAYS = 30
ARCHIVE_KEEP_DAYS = 14
WEEK_DAYS = 7
WEEK_PER_CATEGORY = 12
# Özetleri uzun tutuyoruz: etiketler özetin tamamında aranır, sayfa görünümde kısaltır.
SUMMARY_LEN = 1000


# ---------- 1. İndirme ----------

def fetch(feed, host_locks):
    """Bir kaynağı indirir. (yazılar, hata) döndürür.

    Reddit gibi siteler kısa sürede çok istek gelince 429 döner. Bu yüzden
    aynı siteye aynı anda tek istek atıyoruz, 429 gelirse bekleyip tekrar deniyoruz.
    """
    with host_locks[urlparse(feed["url"]).netloc]:
        return _fetch_with_retry(feed)


def _fetch_with_retry(feed):
    for attempt in range(3):
        try:
            r = requests.get(feed["url"], headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            return [], type(e).__name__
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))  # 10, 20 sn: Reddit kısa beklemede yine reddediyor
            continue
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        return feedparser.parse(r.content).entries, None
    return [], "HTTP 429 (çok fazla istek)"


# ---------- 2. Temizleme ----------

def entry_time(entry):
    """Yazının yayın zamanını UTC datetime olarak döndürür (yoksa None).

    feedparser tarihi zaten UTC'ye çevirip (yıl, ay, gün, saat, dk, sn, ...) şeklinde verir.
    """
    for key in ("published_parsed", "updated_parsed"):
        if entry.get(key):
            return datetime(*entry[key][:6], tzinfo=timezone.utc)
    return None


def clean_text(raw, max_len):
    """HTML etiketlerini atar, boşlukları düzeltir ve metni kısaltır."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    text = " ".join(text.split())
    # arXiv özetleri "arXiv:2610.01234v1 Announce Type: new Abstract: ..." diye başlıyor
    text = re.sub(r"^arXiv:\S+ Announce Type: \S+ Abstract:\s*", "", text)
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "…"
    return text


def thumbnail(entry):
    """YouTube videolarının kapak resmi ({"img": url} ya da {})."""
    url = (entry.get("media_thumbnail") or [{}])[0].get("url", "")
    # Sadece YouTube: diğer siteler (Reddit vb.) resimlerin dışarıdan yüklenmesini engelliyor
    if not re.match(r"https://i\d?\.ytimg\.com/", url):
        return {}
    return {"img": url.replace("hqdefault", "mqdefault")}


# ---------- 3. Daha önce gösterilenler ----------

def load_seen():
    try:
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except ValueError:
        print("uyarı: seen.json bozuk, sıfırdan başlanıyor")
        return {}


def save_seen(seen):
    limit = (datetime.now() - timedelta(days=SEEN_KEEP_DAYS)).strftime("%Y-%m-%d")
    seen = {k: day for k, day in seen.items() if day >= limit}
    SEEN_FILE.write_text(json.dumps(seen, indent=0), encoding="utf-8")


# ---------- 4. Toplama ----------

def collect(config, hours, seen):
    """Tüm kaynaklardan son `hours` saatteki, `seen` içinde olmayan yazıları toplar.

    Kategori ya da kaynak kendi `hours` değerini verebilir (haftalık video kanalları gibi).
    """
    now = datetime.now(timezone.utc)
    default_limit = config["settings"]["default_limit"]

    feeds = [(n, {"hours": cat.get("hours", hours), **feed})
             for n, cat in enumerate(config["categories"]) for feed in cat["feeds"]]
    host_locks = {urlparse(feed["url"]).netloc: threading.Lock() for _, feed in feeds}
    # Kaynakları aynı anda 10'ar 10'ar indir (sırayla indirmek çok uzun sürer)
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda cf: fetch(cf[1], host_locks), feeds))

    feed_meta, items, errors, titles = [], [], [], set()
    for index, ((category, feed), (entries, error)) in enumerate(zip(feeds, results)):
        feed_meta.append({
            "name": feed["name"], "cat": category,
            "filter": bool(feed.get("filter")), "limit": feed.get("limit", default_limit),
        })
        if error:
            errors.append(f"{feed['name']}: {error}")
            continue
        cutoff = now - timedelta(hours=feed["hours"])
        for entry in entries:
            link = entry.get("link") or ""
            published = entry_time(entry)
            if not link.startswith(("http://", "https://")) or (published and published < cutoff):
                continue
            key = hashlib.sha1(link.encode()).hexdigest()[:16]
            if key in seen:
                continue
            title = clean_text(entry.get("title"), 200)
            if title.lower() in titles:  # aynı yazı farklı linkle başka akışta (ör. Medium etiketleri)
                continue
            titles.add(title.lower())
            seen[key] = None  # aynı yazı iki kaynakta varsa bir kez al
            items.append({
                "key": key,
                "t": title,
                "l": link,
                "s": clean_text(entry.get("summary"), SUMMARY_LEN),
                "f": index,
                "d": published.isoformat() if published else None,
                **thumbnail(entry),
            })
    return feed_meta, items, errors


# ---------- 5. Sayfa ve arşiv ----------

def render(data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)


def restore_archive(site_url, since=""):
    """Önceki taramaları canlı siteden indirir (`since` tarihinden eskileri atlar).

    Sayfalar büyük olduğu için git'e konmuyor; arşiv yayındaki sitenin kendisinde duruyor.
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    base = site_url.rstrip("/") + "/archive/"
    try:
        r = requests.get(base + "list.json", headers=HEADERS, timeout=20)
        stamps = r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        stamps = []
    restored = 0
    for stamp in stamps:
        target = ARCHIVE_DIR / f"{stamp}.html"
        # "2026-10-08" (günlük) ya da eski biçim "2026-10-07_1438"
        if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}(_\d{4})?", stamp):
            continue
        if stamp[:10] < since or target.exists():
            continue
        try:
            r = requests.get(f"{base}{stamp}.html", headers=HEADERS, timeout=30)
        except requests.RequestException:
            continue
        if r.status_code == 200:
            target.write_bytes(r.content)
            restored += 1
    print(f"arşivden {restored}/{len(stamps)} sayfa geri yüklendi")


def read_page_data(path):
    """Arşiv sayfasına gömülü veriyi (const D = {...}) okur."""
    page = path.read_text(encoding="utf-8")
    start = page.index("const D = ") + len("const D = ")
    end = page.index(";\nconst STORE", start)
    return json.loads(page[start:end])


def pattern(tag):
    """template.html'deki eşleştirmenin aynısı: tam kelime + çekimli haller."""
    tag = tag.rstrip("*").lower()
    m = re.match(r"^(.{4,})(ization|isation|ation)$", tag) or (
        re.search(r"[-\s]", tag) and re.match(r"^(.{4,})ing$", tag))
    body = re.escape(m.group(1)) + r"\w*" if m else re.escape(tag) + "(?:s|es)?"
    return re.compile(rf"(?<!\w){body}(?!\w)")


def week_candidates(data):
    """Son 7 günün (arşiv + bu tarama) en iyi adaylarını seçer; asıl sıralamayı sayfa yapar.

    Haftada ~10 bin yazı birikiyor, hepsini gömmek sayfayı şişirir. Bu yüzden varsayılan
    etiketlerle ön eleme yapıp her kategoriden en iyi WEEK_PER_CATEGORY yazıyı alıyoruz.
    """
    limit = (datetime.now() - timedelta(days=WEEK_DAYS)).strftime("%Y-%m-%d")
    pages = [read_page_data(p) for p in sorted(ARCHIVE_DIR.glob("*.html")) if p.stem[:10] >= limit]
    patterns = [pattern(tag) for tag in data["interests"]]
    pool = {}
    for page in pages + [data]:
        for item in page["items"]:
            feed = page["feeds"][item["f"]]
            text = f"{item['t']} {item['s']}".lower()
            hits = sum(1 for p in patterns if p.search(text))
            key = item["t"].lower()  # başlığa göre: aynı yazı farklı linklerle gelebiliyor
            if hits and key not in pool:
                pool[key] = (hits, {
                    "t": item["t"], "l": item["l"], "s": item["s"][:400], "d": item["d"],
                    "src": feed["name"], "cat": page["categories"][feed["cat"]],
                    **({"img": item["img"]} if item.get("img") else {}),
                })
    ranked = [entry for _, entry in sorted(pool.values(), key=lambda p: (p[0], p[1]["d"] or ""), reverse=True)]
    # Kategori başına kota: yoksa uzun ve kelime dolu arXiv özetleri tüm listeyi kaplıyor
    chosen, per_category = [], {}
    for entry in ranked:
        per_category[entry["cat"]] = per_category.get(entry["cat"], 0) + 1
        if per_category[entry["cat"]] <= WEEK_PER_CATEGORY:
            chosen.append(entry)
    return chosen


def merge_today(data, day):
    """Gün içindeki önceki taramanın yazılarını bu taramaya ekler.

    Arşivde her gün tek sayfa var; gün içinde tekrar taranırsa (elle çalıştırma, yedek zamanlama)
    sayfa sadece aradaki birkaç yeni yazıya düşmesin diye günün yazıları birleştirilir.
    """
    pages = sorted(ARCHIVE_DIR.glob(f"{day}*.html"))
    if not pages:
        return
    old = read_page_data(pages[-1])  # günün son sayfası o güne kadarki her şeyi içerir
    feed_index = {feed["name"]: n for n, feed in enumerate(data["feeds"])}
    links = {item["l"] for item in data["items"]}
    for item in old["items"]:
        name = old["feeds"][item["f"]]["name"]
        if name in feed_index and item["l"] not in links:  # feeds.yaml'dan çıkarılan kaynaklar düşer
            data["items"].append({**item, "f": feed_index[name]})


def tidy_archive():
    """Her gün için tek sayfa bırakır (en yenisi, adı sadece tarih) ve eski günleri siler."""
    limit = (datetime.now() - timedelta(days=ARCHIVE_KEEP_DAYS)).strftime("%Y-%m-%d")
    by_day = {}
    for page in sorted(ARCHIVE_DIR.glob("*.html")):
        by_day.setdefault(page.stem[:10], []).append(page)
    for day, pages in by_day.items():
        *older, newest = pages
        for page in older:
            page.unlink()
        if day < limit:
            newest.unlink()
        elif newest.stem != day:
            newest.rename(ARCHIVE_DIR / f"{day}.html")


def publish(data, stamp):
    """Sayfayı site/archive/<tarih>.html ve site/index.html olarak yazar."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    tidy_archive()
    archive = sorted({p.stem for p in ARCHIVE_DIR.glob("*.html")} | {stamp}, reverse=True)
    (ARCHIVE_DIR / f"{stamp}.html").write_text(
        render({**data, "archive": archive, "current": stamp, "base": ""}), encoding="utf-8")
    (ARCHIVE_DIR / "list.json").write_text(json.dumps(archive), encoding="utf-8")
    index = SITE_DIR / "index.html"
    index.write_text(
        render({**data, "archive": archive, "current": stamp, "base": "archive/"}), encoding="utf-8")
    return index


# ---------- 6. Ana akış ----------

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Günlük AI haber radarı")
    parser.add_argument("--hours", type=int, help="son kaç saat taransın (varsayılan: feeds.yaml)")
    parser.add_argument("--publish", action="store_true", help="siteyi docs/ içine yaz ve seen.json'u güncelle")
    parser.add_argument("--restore", metavar="URL", help="önceki taramaları bu siteden indir (--publish ile)")
    parser.add_argument("--reset-archive", action="store_true", help="önceki günleri geri yükleme (arşivi sıfırla)")
    parser.add_argument("--all", action="store_true", help="daha önce gösterilenleri de al (--publish ile)")
    parser.add_argument("--no-open", action="store_true", help="sayfayı tarayıcıda açma")
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / "feeds.yaml").read_text(encoding="utf-8"))
    hours = args.hours or config["settings"]["hours"]

    started = time.time()
    seen = load_seen() if args.publish else {}
    today = datetime.now().strftime("%Y-%m-%d")
    feed_meta, items, errors = collect(config, hours, {} if args.all else dict(seen))

    now = datetime.now().astimezone()
    data = {
        "generated": now.isoformat(timespec="minutes"),
        "hours": hours,
        "interests": config["interests"],
        "highlightMin": config["settings"].get("highlight_min", 2),
        "categories": [cat["name"] for cat in config["categories"]],
        "feeds": feed_meta,
        "items": items,
        "errors": errors,
    }

    keys = [item.pop("key") for item in items]
    new_count = len(items)  # merge_today aynı listeye günün önceki yazılarını ekler
    if args.publish:
        if args.restore:
            restore_archive(args.restore, since=today if args.reset_archive else "")
        merge_today(data, today)
        data["week"] = week_candidates(data)
        out = publish(data, today)
        seen.update({key: today for key in keys})
        save_seen(seen)
    else:
        data["week"] = week_candidates(data)
        PREVIEW_FILE.parent.mkdir(exist_ok=True)
        PREVIEW_FILE.write_text(render({**data, "archive": [], "current": None, "base": ""}), encoding="utf-8")
        out = PREVIEW_FILE

    print(f"{new_count} yeni içerik (sayfada toplam {len(items)}), {len(errors)} kaynak hatası, {time.time() - started:.0f} sn -> {out}")
    for e in errors:
        print("  hata:", e)
    if not args.no_open:
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
