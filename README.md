# 📡 AI Radar

Her sabah ~50 yapay zeka kaynağını (arXiv, laboratuvar blogları, Medium,
freeCodeCamp, dev.to, Reddit, Hacker News, GitHub Trending, YouTube...) tarayıp
tek bir web sayfasında toplayan kişisel haber radarı.

**Canlı site:** https://ayse-solmaz.github.io/ai-radar/

## Nasıl çalışır?

```
GitHub Actions (her gün 08:00)
  └─ radar.py --publish
       1. feeds.yaml'daki kaynakları paralel indir
       2. son 36 saati al, daha önce alınanları at (seen.json)
       3. hepsini template.html'in içine göm -> site/index.html + site/archive/<tarih>.html
  └─ site/ klasörünü GitHub Pages'e yükle, seen.json'u depoya kaydet
```

Puanlama **tarayıcıda** yapılır:

- Sayfanın üstündeki **İlgi alanların** panelinde etiketleri açıp kapatabilir, silebilir, yenilerini ekleyebilirsin.
  Her etiketin yanındaki sayı, o taramada kaç yazıda geçtiğini gösterir — hangi etiketin işe yaradığını buradan görürsün.
- Etiketler geçen yazılar üste çıkar ve rozetle işaretlenir; 2+ etiket geçenler **"Senin için öne çıkanlar"** bölümüne girer.
- `filter: true` olan kaynaklardan (arXiv) sadece etiketlerinden biri geçen yazılar gösterilir.
- Çoğul -s otomatik eşleşir (`llm` → LLMs). Sonuna `*` koyarsan devamı da eşleşir (`fine-tun*` → fine-tuning).
- Sitedeki değişiklikler sadece o tarayıcıda saklanır. Kalıcı yapmak için **Kopyala**'ya bas ve
  `feeds.yaml`'daki `interests` listesine yapıştır.
- Sağ üstteki tarih menüsünden son 30 günün taramalarına bakabilirsin.

Sayfalar büyük olduğu için (arXiv özetleri) git'e konmaz; arşiv yayındaki sitede durur ve
her çalışmada oradan geri indirilir.

## Bilgisayarında denemek

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python radar.py
```

Bu bir **önizleme**dir: `output/preview.html` açılır, `seen.json`'a dokunulmaz.

## Siteyi elle güncellemek

GitHub'da **Actions → AI Radar → Run workflow**, ya da:

```bash
gh workflow run radar.yml
```

## Kaynak eklemek

`feeds.yaml` içinde ilgili kategoriye ekle, commit'le ve push'la:

```yaml
      - name: Medium · bir yazar
        url: https://medium.com/feed/@kullaniciadi
```

İşe yarayan RSS kalıpları:

| Site | Kalıp |
|---|---|
| Medium etiketi | `https://medium.com/feed/tag/<etiket>` |
| Medium yazarı | `https://medium.com/feed/@<kullanici>` |
| dev.to etiketi | `https://dev.to/feed/tag/<etiket>` |
| Substack | `https://<isim>.substack.com/feed` |
| Reddit | `https://www.reddit.com/r/<subreddit>/top/.rss?t=day` |
| Hacker News arama | `https://hnrss.org/newest?q=<kelime>&points=50` |
| YouTube kanalı | `https://www.youtube.com/feeds/videos.xml?channel_id=<id>` |
| arXiv kategorisi | `https://rss.arxiv.org/rss/<kategori>` |
