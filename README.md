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

### Sayfada neler var?

- **🏷️ İlgi alanların:** Etiketleri açıp kapatabilir, silebilir, yenilerini ekleyebilirsin. Her etiketin yanındaki sayı
  o taramada kaç yazıda geçtiğini gösterir — hangi etiketin işe yaradığını buradan görürsün. Çekimli halleri otomatik
  bulunur (`llm` → LLMs, `quantization` → quantized). `filter: true` olan kaynaklardan (arXiv) sadece etiketlerinden biri
  geçenler gösterilir. Kalıcı yapmak için **Kopyala**'ya bas ve `feeds.yaml`'daki `interests` listesine yapıştır.
- **🎯 Senin için öne çıkanlar:** Başlığında etiketin geçen, en az 2 etiketli yazılar (kaynak başına en fazla 2).
- **🧠 Mini ben:** Kendini birkaç cümleyle anlatırsın; aşağıdaki tüm Claude butonları bunu kullanır:
  - 🤖 **Basitleştir ve tartış** — yazıyı sade Türkçe anlatır, sonra seninle tartışır
  - 💡 **Proje çıkar** — yazıdan hafta sonu / bir haftalık / iddialı 3 proje fikri
  - 🧠 **Bugünün beyin fırtınası** — günün öne çıkanlarından trendler ve 5 proje fikri
  - 🎓 **Öğrenme yolu** — bir konu seç; o konudaki tutorial ve videoları listeler, Claude'la adım adım öğrenme planı çıkarır
- **📅 Son 7 günün en iyileri:** Haftanın taramalarından senin etiketlerine göre seçilen yazılar, videolar ve tutoriallar.
  Her gün güncellenir; **Haftanın beyin fırtınası** butonu haftayı Claude'la değerlendirir.
- **⭐ Defterim:** ☆ Kaydet ile beğendiklerini biriktir; **Defterimi özetle** kafanda dönen temaları ve proje önerisini çıkarır.
- Sağ üstteki tarih menüsünden son 14 güne bakabilirsin. Her gün tek sayfadır: gün içinde tekrar taranırsa
  yeni yazılar o günün sayfasına eklenir. Daha eski günler kendiliğinden silinir.

Claude butonları claude.ai'yi hazır bir mesajla açar: API anahtarı ya da ek ücret gerekmez, kendi Claude hesabın kullanılır.
Profil, etiketler ve defter **sadece o tarayıcıda** saklanır (telefon ve bilgisayar ayrı tutar).

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

GitHub'da **Actions → AI Radar → Run workflow**. İki seçenek var:
- *Daha önce gösterilenleri de tekrar göster:* son 36 saatin tüm yazılarını yeniden alır
- *Arşivi sıfırla:* tarih menüsünde sadece bugün kalır

Ya da komut satırından:

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
