---
title: Murat Karakaya Akademi Dergi Tarama
emoji: 📚
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
---
## Murat Karakaya Akademi Dergi Tarama

Murat Karakaya Akademi Dergi Tarama, UBYT 2026 dergi listesi ile APC destek kayitlarini birlestirerek akademisyenlere uygun dergi onermeye odaklanan tek sayfalik bir web uygulamasidir.

Bu repo iki kullanim yolu sunar:

- `app.py`: son kullaniciya acilan FastAPI tabanli web uygulamasi
- `journal_engine.py`: web uygulamasinin veri okuma ve aday secme mantigi

Bu repo artik yalnizca web uygulamasi icin tutulmaktadir.

## Ne Yapar?

- Turkce veya Ingilizce serbest metin sorgusundan dergi onerir.
- UBYT listesi ve APC destek kayitlarini birlikte degerlendirir.
- `Tumu`, indeks ve maksimum destek miktari filtreleri sunar.
- Ollama Cloud ile `required_terms` ve `optional_terms` cikarir.
- Model yaniti gelmezse yerel kuralli fallback kullanir.
- Gerekli terimlerle sonuc cikmazsa, bu terimleri opsiyonel siralama terimlerine tasiyarak daha gevsek bir ikinci deneme yapar.

## Veri Kaynaklari

Yerel veri dosyalari:

- `ubyt.xlsx`
- `Elsevier.xlsx`
- `Wiley.xlsx`

Resmi kaynaklar ve anlasmalar:

- [UBYT 2026 Yili UBYT Programi Dergi Listesi](https://cabim.ulakbim.gov.tr/ubyt/)
- [TUBITAK fonlanan yayinevleri listesi](https://cabim.ulakbim.gov.tr/ekual/e-veri-tabanlari/universiteler/)
- [Wiley AE Makale Yayimlama Anlasmasi](https://authors.wiley.com/author-resources/Journal-Authors/open-access/affiliation-policies-payments/tubitak-agreement.html)
- [Anlasma kapsamindaki Wiley AE dergi listesi](https://cabim.ulakbim.gov.tr/wp-content/uploads/sites/4/2026/04/TUBITAK_Tarafindan_Fonlanan-Wiley_AE_DergiListesi.xlsx)
- [Springer Nature AE Makale Yayimlama Anlasmasi](https://www.springernature.com/gp/open-science/oa-agreements/turkiye/tubitak)
- [Anlasma kapsamindaki Springer Nature AE dergi listesi](https://cabim.ulakbim.gov.tr/wp-content/uploads/sites/4/2026/02/sn_2026_list.xlsx)

## Web Uygulamasini Lokal Calistirma

Proje kokune gec:

```powershell
cd C:\Codes\UBYT_MCP
```

Bagimliliklari kur:

```powershell
pip install -r requirements.txt
```

Uygulamayi baslat:

```powershell
python -m uvicorn app:app --host 0.0.0.0 --port 7860
```

Not: Bu komut repo kokunden calistirilmalidir. `C:\Codes` gibi ust bir klasorden calistirilirsa `Could not import module "app"` hatasi alirsiniz.

Tarayicida ac:

```text
http://127.0.0.1:7860
```

## Ortam Degiskenleri

Ollama Cloud entegrasyonu icin su ortam degiskenleri desteklenir:

- `OLLAMA_API_KEY`: Ollama Cloud erisim anahtari
- `OLLAMA_HOST`: varsayilan `https://ollama.com`
- `OLLAMA_MODEL`: varsayilan `gpt-oss:120b`

`OLLAMA_API_KEY` yoksa veya model yaniti alinamazsa uygulama yerel fallback ile devam eder.

## API Ozeti

- `GET /`: tek sayfalik arayuz
- `GET /health`: saglik kontrolu, `{"status":"ok"}` dondurur
- `GET /filters`: indeks ve maksimum destek miktari seceneklerini dondurur
- `POST /recommend`: sorgu, filtreler ve limit ile dergi onerileri dondurur

Ornek istek:

```powershell
curl -X POST http://127.0.0.1:7860/recommend ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Beyin MR goruntulerinden kanama tespiti yapan bir goruntu isleme algoritmasi gelistirdim.\",\"require_apc\":false,\"indexes\":[],\"max_payment_tl\":null,\"limit\":3}"
```

Ornek yanit alanlari:

- `required_terms`
- `optional_terms`
- `ranking_mode`
- `result_count`
- `keyword_source`
- `llm.status_text`
- `results`

## Arama Mantigi

Uygulama aramayi iki asamada yapar:

1. Ollama Cloud veya yerel fallback ile Ingilizce arama terimleri cikarilir.
2. UBYT/APC kapali veri kumesi icinde adaylar siralanir.

Varsayilan davranislar:

- `required_terms`: mumkun oldugunca az ve sik anchor terimler
- `optional_terms`: daha genis konu, yontem ve alan terimleri
- Ilk arama siki `required_terms` ile yapilir
- Sonuc yoksa `required_terms`, opsiyonel terimlere tasinip ikinci bir arama yapilir

Bu nedenle arayuzde bazen `strict-required`, bazen `relaxed-required-to-optional` modunda sonuc gorebilirsiniz.

## Hugging Face Spaces

Bu repo Hugging Face Docker Space olarak calisacak sekilde hazirlanmistir.

- `Dockerfile` uygulamayi `7860` portunda ayaga kaldirir.
- README frontmatter icindeki `sdk: docker` ve `app_port: 7860` alanlari HF icin gereklidir.
- Excel dosyalari binary oldugu icin push sirasinda `git-xet` gereklidir.

Hedef Space:

```text
https://huggingface.co/spaces/kmkarakaya/dergitarama
```

## Hugging Face Push Scripti

`push_hf_space.bat` dosyasi Windows icin hazirlanmis yayim scriptidir.

Neler yapar:

- gerekli dosyalari kontrol eder
- `git-xet` kurulumunu dogrular
- Docker image build eder
- container acip `/health` endpointini test eder
- Space reposunu senkronize eder
- degisiklik varsa commit ve push yapar

Temel kullanim:

```powershell
push_hf_space.bat
```

Kuru calistirma:

```powershell
push_hf_space.bat /dry-run
```

Docker kontrolunu atlayarak:

```powershell
push_hf_space.bat /skip-docker-check
```

## Proje Dosyalari

Temel dosyalar:

- `app.py`: FastAPI uygulamasi
- `journal_engine.py`: veri okuma ve deterministik aday secim mantigi
- `static/index.html`: tek sayfa arayuz
- `static/app.js`: istemci davranisi
- `static/styles.css`: arayuz stilleri
- `push_hf_space.bat`: HF Space deployment scripti
- `ubyt.xlsx`, `Elsevier.xlsx`, `Wiley.xlsx`: veri dosyalari
