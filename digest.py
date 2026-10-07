"""Haftalık özet: son 7 günün taramalarından en iyi içerikleri seçip Markdown olarak yazar.

GitHub Actions her pazar bunu çalıştırıp depoda bir issue açar; GitHub de sana e-posta atar.

Kullanım:
    python digest.py --restore https://kullanici.github.io/ai-radar/ --out digest.md --mention kullanici
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import quote

import yaml

from radar import ARCHIVE_DIR, ROOT, restore_archive

DAYS = 7


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


def load_week(interests):
    """Son DAYS günün arşivindeki tüm yazıları, ilgi etiketleriyle puanlanmış olarak döndürür."""
    limit = (datetime.now() - timedelta(days=DAYS)).strftime("%Y-%m-%d")
    patterns = {tag: pattern(tag) for tag in interests}
    items, seen_links = [], set()
    for path in sorted(ARCHIVE_DIR.glob("*.html"), reverse=True):
        if path.stem[:10] < limit:
            continue
        data = read_page_data(path)
        for item in data["items"]:
            if item["l"] in seen_links:
                continue
            seen_links.add(item["l"])
            feed = data["feeds"][item["f"]]
            text = f"{item['t']} {item['s']}".lower()
            hits = [tag for tag, p in patterns.items() if p.search(text)]
            if feed["filter"] and not hits:
                continue
            items.append({
                **item, "hits": hits, "source": feed["name"],
                "category": data["categories"][feed["cat"]],
                "title_hit": any(patterns[tag].search(item["t"].lower()) for tag in hits),
            })
    return items


def pick(items, count, per_source=2, where=lambda i: True):
    """En çok etiket geçenleri seçer; çeşitlilik için kaynak başına en fazla `per_source` yazı."""
    chosen, per = [], {}
    for item in sorted(filter(where, items), key=lambda i: (len(i["hits"]), i["d"] or ""), reverse=True):
        if per.get(item["source"], 0) >= per_source:
            continue
        per[item["source"]] = per.get(item["source"], 0) + 1
        chosen.append(item)
        if len(chosen) == count:
            break
    return chosen


def claude_link(prompt):
    return "https://claude.ai/new?q=" + quote(prompt)


def line(item):
    tags = ", ".join(f"`{t}`" for t in item["hits"][:5])
    ask = claude_link(f"Şu içeriği oku: {item['l']}\nBaşlık: {item['t']}\n\n"
                      "Türkçe ve sade anlat: basit özet, neden önemli, bilmem gereken kavramlar, "
                      "eleştirel bakış. Sonra bana 2 soru sorarak tartışalım.")
    title = item["t"].replace("[", "(").replace("]", ")")  # Markdown linkini bozmasın
    return f"- **[{title}]({item['l']})**  \n  {item['source']} · {tags} · [🤖 Claude ile tartış]({ask})"


def build(items, site_url, mention):
    top = pick(items, 7, where=lambda i: i["title_hit"] and len(i["hits"]) >= 2)
    rest = [i for i in items if i not in top]
    videos = pick(rest, 4, per_source=1, where=lambda i: "Video" in i["category"])
    learn = pick(rest, 4, per_source=1, where=lambda i: "Öğren" in i["category"])
    everything = top + videos + learn

    brainstorm = claude_link(
        "Bu hafta yapay zeka dünyasında öne çıkanlar:\n" +
        "\n".join(f"{n + 1}. {i['t']} ({i['source']}) — {i['l']}" for n, i in enumerate(everything)) +
        "\n\nKafamdaki beyin gibi davran: 1) Haftanın 3 ana trendini çıkar. "
        "2) Bunlardan beslenen 5 yaratıcı proje fikri üret (biri çılgın olsun). "
        "3) Bu hafta öğrenmem gereken tek konuyu seç. Sonra beyin fırtınasına devam edelim. Türkçe yaz.")

    parts = [
        f"@{mention} haftalık AI Radar özetin hazır 👋" if mention else "Haftalık AI Radar özeti 👋",
        f"\n{len(items)} içerik tarandı · [Siteyi aç]({site_url}) · **[🧠 Haftanın beyin fırtınası]({brainstorm})**",
    ]
    for title, group in [("🎯 Haftanın öne çıkanları", top), ("🎥 İzlemeye değer", videos), ("📚 Öğren", learn)]:
        if group:
            parts.append(f"\n## {title}\n" + "\n".join(map(line, group)))
    return "\n".join(parts) + "\n"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Haftalık AI Radar özeti")
    parser.add_argument("--restore", metavar="URL", required=True, help="taramaların indirileceği site")
    parser.add_argument("--out", default="digest.md")
    parser.add_argument("--mention", help="issue'da etiketlenecek GitHub kullanıcısı (e-posta bildirimi için)")
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / "feeds.yaml").read_text(encoding="utf-8"))
    restore_archive(args.restore)
    items = load_week(config["interests"])
    if not items:
        sys.exit("Bu hafta için tarama bulunamadı")
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(build(items, args.restore, args.mention))
    print(f"{len(items)} içerikten özet yazıldı -> {args.out}")


if __name__ == "__main__":
    main()
