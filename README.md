---
title: Murat Karakaya Akademi Dergi Tarama
emoji: 📚
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
---
## Murat Karakaya Akademi Dergi Tarama

Murat Karakaya Akademi Dergi Tarama, UBYT 2026 dergi listesi ile APC destek kayıtlarını birleştirerek akademisyenlere uygun dergi önermeye odaklanan tek sayfalık bir web uygulamasıdır.

![Murat Karakaya Akademi Dergi Tarama workflow](workflow1.0.png)

Bu repo iki kullanım yolu sunar:

- `app.py`: son kullanıcıya açılan FastAPI tabanlı web uygulaması
- `journal_engine.py`: web uygulamasının veri okuma ve aday seçme mantığı

## Ne Yapar?

- Türkçe veya İngilizce serbest metin sorgusundan dergi önerir.
- UBYT listesi ve APC destek kayıtlarını birlikte değerlendirir.
- `Tümü`, indeks, maksimum destek miktarı ve `3/5/8/10/15` dergi sayısı filtreleri sunar.
- Ollama Cloud ile journal title taramasına uygun `required_terms` ve `optional_terms` çıkarır.
- Model yanıtı gelmezse yerel kurallı fallback kullanır.
- Gerekli terimlerle sonuç çıkmazsa, bu terimleri opsiyonel sıralama terimlerine taşıyarak daha gevşek bir ikinci deneme yapar.
- Yerel shortlist oluştuktan sonra, uygun olduğunda Ollama judge ile aynı aday havuzunu yeniden sıralar.
- Her sorgu bloğu için aynı sonuç kümesini Excel olarak indirir.
- Sorgu sırasında Ollama, shortlist, judge, APC bağlama ve kart hazırlama adımlarını status panelinde gösterir.

## Veri Kaynakları

Yerel veri dosyaları:

- `ubyt.xlsx`
- `Elsevier.xlsx`
- `Wiley.xlsx`

Resmî kaynaklar ve anlaşmalar:

- [UBYT 2026 Yılı UBYT Programı Dergi Listesi](https://cabim.ulakbim.gov.tr/ubyt/)
- [TÜBİTAK fonlanan yayınevleri listesi](https://cabim.ulakbim.gov.tr/ekual/e-veri-tabanlari/universiteler/)
- [Wiley AE Makale Yayımlama Anlaşması](https://authors.wiley.com/author-resources/Journal-Authors/open-access/affiliation-policies-payments/tubitak-agreement.html)
- [Anlaşma kapsamındaki Wiley AE dergi listesi](https://cabim.ulakbim.gov.tr/wp-content/uploads/sites/4/2026/04/TUBITAK_Tarafindan_Fonlanan-Wiley_AE_DergiListesi.xlsx)
- [Springer Nature AE Makale Yayımlama Anlaşması](https://www.springernature.com/gp/open-science/oa-agreements/turkiye/tubitak)
- [Anlaşma kapsamındaki Springer Nature AE dergi listesi](https://cabim.ulakbim.gov.tr/wp-content/uploads/sites/4/2026/02/sn_2026_list.xlsx)

## Web Uygulamasını Lokal Çalıştırma

Proje köküne geç:

```powershell
cd C:\Codes\UBYT_MCP
```

Bağımlılıkları kur:

```powershell
pip install -r requirements.txt
```

Uygulamayı başlat:

```powershell
python -m uvicorn app:app --host 0.0.0.0 --port 7860
```

Not: Bu komut repo kökünden çalıştırılmalıdır. `C:\Codes` gibi üst bir klasörden çalıştırılırsa `Could not import module "app"` hatası alırsınız.

Tarayıcıda aç:

```text
http://127.0.0.1:7860
```

## Hugging Face Spaces Görüntülenme Sayacı

Uygulama ana sayfa yüklendiğinde public bir CounterAPI sayacını `+1` artırır ve dönen toplam değeri ana sayfada gösterir. Böylece sayaç Hugging Face Space container dosya sistemine bağlı kalmaz.

Gerekli ayarlar:

- `COUNTERAPI_WORKSPACE`: CounterAPI üzerinde oluşturduğunuz public workspace slug değeri
- `COUNTERAPI_COUNTER_NAME`: opsiyonel; varsayılan `page-views`

Bu değerler lokal ortamda shell environment değişkeni olarak, Hugging Face Spaces'ta ise Space Settings > Variables bölümünden verilebilir.

Notlar:

- Sayaç değeri CounterAPI tarafında tutulduğu için HF free runtime yeniden başlasa bile sıfırlanmaz.
- Bu sayı benzersiz ziyaretçi değil, public sayfa görüntüleme sayacıdır.
- `COUNTERAPI_WORKSPACE` tanımlı değilse ana sayfada sayaç için yapılandırma uyarısı gösterilir.

## Hızlı Kullanım Kılavuzu

1. Makalenizin konusunu, anahtar kelimelerini, özetini veya hakkında bilgi almak istediğiniz derginin adını yazın.
2. Arama seçeneklerini belirleyin: APC filtresi, maksimum destek miktarı, indeks ve dergi sayısı.
3. Gelen kartlarda hangi derginin UBYT listesinde yer aldığını ve hangilerinin Elsevier veya Wiley anlaşmaları kapsamında APC desteği alabildiğini inceleyin.
4. Dergi kartlarına tıklayarak ayrıntıları açın; dergi sayfasına gidin veya dergiyi webde arayın.
5. Sorgunuzu düzelterek yeniden arama yapın ve sonuçları farklı filtrelerle karşılaştırın.
6. `İndir` düğmesiyle ekrandaki sonuçları ayrıntılı Excel dosyası olarak indirin.

## Ortam Değişkenleri

Ollama Cloud entegrasyonu için şu ortam değişkenleri desteklenir:

- `OLLAMA_API_KEY`: Ollama Cloud erişim anahtarı
- `OLLAMA_HOST`: varsayılan `https://ollama.com`
- `OLLAMA_MODEL`: varsayılan `gpt-oss:120b`
- `OLLAMA_JUDGE_ENABLED`: varsayılan `1`; `0` yapılırsa shortlist sonrası Ollama judge rerank kapatılır
- `COUNTERAPI_WORKSPACE`: public CounterAPI workspace slug değeri
- `COUNTERAPI_COUNTER_NAME`: görüntülenme sayacı adı; varsayılan `page-views`

`OLLAMA_API_KEY` yoksa veya model yanıtı alınamazsa uygulama yerel term fallback ve yerel shortlist sıralaması ile devam eder.

Geliştirme notu:

- `7860` portunda çalışan uygulama auto-reload kullanmıyor; backend değişikliğinden sonra `uvicorn` sürecini yeniden başlatmak gerekir.

## API Özeti

- `GET /`: tek sayfalık arayüz
- `GET /health`: sağlık kontrolü, `{"status":"ok"}` döndürür
- `GET /client-config`: istemci tarafında kullanılacak public yapılandırmayı döndürür
- `GET /filters`: indeks ve maksimum destek miktarı seçeneklerini döndürür
- `POST /recommend`: sorgu, filtreler ve limit ile dergi önerileri döndürür
- `POST /export-results`: mevcut sorgu bloğundaki sonuç kümesini veya aynı filtrelerle oluşan tüm sonucu Excel olarak döndürür

Örnek istek:

```powershell
curl -X POST http://127.0.0.1:7860/recommend ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Beyin MR görüntülerinden kanama tespiti yapan bir görüntü işleme algoritması geliştirdim.\",\"require_apc\":false,\"indexes\":[],\"max_payment_tl\":null,\"limit\":3}"
```

Örnek yanıt alanları:

- `required_terms`
- `optional_terms`
- `ranking_mode`
- `candidate_pool_count`
- `result_count`
- `keyword_source`
- `llm.status_text`
- `rerank.status`
- `rerank_source`
- `results`

## Arama Mantığı

Uygulama aramayı dört aşamada yapar:

1. Ollama Cloud veya yerel fallback ile, dergi başlıklarında geçmesi muhtemel İngilizce arama terimleri çıkarılır.
2. UBYT/APC kapalı veri kümesi içinde title matching ve metadata filtreleri ile yerel aday havuzu oluşturulur.
3. Uygunsa aynı aday havuzu Ollama judge'e verilerek yeniden sıralanır; başarısız olursa yerel sıra korunur.
4. APC kayıtları bağlanır, kart payload'i hazırlanır ve aynı sonuç kümesi için Excel export verisi üretilir.

Varsayılan davranışlar:

- `required_terms`: mümkün olduğunca az ve sık anchor terimler
- `optional_terms`: journal başlıklarında geçmesi muhtemel daha geniş konu, yöntem ve alan terimleri
- İlk arama sıkı `required_terms` ile yapılır
- Sonuç yoksa `required_terms`, opsiyonel terimlere taşınıp ikinci bir arama yapılır
- Ollama judge yalnızca mevcut shortlist içindeki `candidate_id` değerlerini yeniden sıralar; yeni dergi uydurmaz
- Judge kullanılamazsa veya geçersiz structured output döndürürse uygulama yerel shortlist ile devam eder

Bu nedenle arayüzde bazen `strict-required`, bazen `relaxed-required-to-optional` modunda sonuç görebilirsiniz.

## Sonuç Bloğu ve Excel Export

- Her sorgu bloğu kendi sonuç kümesini taşır; `İndir` düğmesi o bloğun mevcut sonuç kartlarını Excel olarak indirir.
- Export dosyası `Özet` ve `Dergi Sonuçları` sayfalarını içerir.
- `Dergi Sonuçları` sayfasında başlık, eşleşen terimler, APC desteği, kaynak dosyaları, imprint, dergi sayfası ve benzeri detay alanları bulunur.
- Export, UI'da görünen aynı sonuç payload'ını kullandığı için LLM drift nedeniyle farklı bir liste üretmez.

## Status Paneli

Sorgu sırasında status paneli şu aşamaları gösterir:

- Ollama erişimi ve term yanıtı
- Başlık tarama terimlerinin hazırlanması
- Yerel shortlist oluşturma
- Ollama judge yeniden sıralama
- APC destek kayıtlarını bağlama
- Kart, drawer ve Excel export verisini hazırlama

Sorgu tamamlandığında panel; aday havuzu boyutu, judge durumu ve sonuç sayısı gibi o sorguya özel özet satırları gösterir.

## Hugging Face Spaces

Bu repo Hugging Face Docker Space olarak çalışacak şekilde hazırlanmıştır.

- `Dockerfile` uygulamayı `7860` portunda ayağa kaldırır.
- README frontmatter içindeki `sdk: docker` ve `app_port: 7860` alanları HF için gereklidir.
- Excel dosyaları binary olduğu için push sırasında `git-xet` gereklidir.

Hedef Space:

```text
https://huggingface.co/spaces/kmkarakaya/dergitarama
```

## Hugging Face Push Scripti

`push_hf_space.bat` dosyası Windows için hazırlanmış yayım scriptidir.

Neler yapar:

- gerekli dosyaları kontrol eder
- `git-xet` kurulumunu doğrular
- Docker image build eder
- container açıp `/health` endpointini test eder
- Space reposunu geçici bir klasöre clone eder
- proje dosyalarını bu geçici clone içine senkronize eder
- değişiklik varsa commit ve push yapar
- deploy bitince geçici klasörü siler

Temel kullanım:

```powershell
push_hf_space.bat
```

Kuru çalıştırma:

```powershell
push_hf_space.bat /dry-run
```

Docker kontrolünü atlayarak:

```powershell
push_hf_space.bat /skip-docker-check
```

Not: Script artık `C:\Codes\dergitarama-space` gibi kalıcı bir yerel Space klasörü kullanmaz. Hugging Face Space reposu yalnızca deploy sırasında geçici bir klasöre clone edilir ve işlem sonunda silinir.

## Proje Dosyaları

Temel dosyalar:

- `app.py`: FastAPI uygulaması
- `journal_engine.py`: veri okuma ve deterministik aday seçim mantığı
- `static/index.html`: tek sayfa arayüz
- `static/app.js`: istemci davranışı
- `static/styles.css`: arayüz stilleri
- `push_hf_space.bat`: HF Space deployment scripti
- `ubyt.xlsx`, `Elsevier.xlsx`, `Wiley.xlsx`: veri dosyaları
