---
title: DergiSec
emoji: 📚
colorFrom: amber
colorTo: red
sdk: docker
app_port: 7860
---

## UBYT + APC Destek MCP Server

Bu repo artik iki kullanim yolu sunar:

- `server.py`: MCP destekli istemciler icin stdio tabanli server
- `app.py`: Hugging Face Spaces veya tarayici tabanli kullanim icin tek sayfalik web uygulamasi

Akademisyen son kullanicilar icin onerilen giris noktasi web uygulamasidir. Tek bir serbest metin alaniyla sorgu alir, sonucu dergi kapagi hissi veren kartlar olarak gosterir.

## Hugging Face Spaces Docker Kurulumu

Bu repo Hugging Face Docker Space olarak calisacak sekilde hazirlandi. Space olustururken Docker SDK secilebilir; repo kokundeki `Dockerfile` ve bu README ust bilgisindeki `sdk: docker` ayari otomatik kullanilir.

Space acildiginda uygulama `7860` portundan su bilecenleri servis eder:

- `GET /`: tek sayfalik arayuz
- `POST /recommend`: serbest metin sorgusundan dergi kartlari ureten API
- `GET /health`: saglik kontrolu

## Web Uygulamasini Lokal Calistirma

Bagimliliklari kur:

```powershell
pip install -r requirements.txt
```

Ardindan web uygulamasini baslat:

```powershell
uvicorn app:app --host 0.0.0.0 --port 7860
```

Tarayicida ac:

```text
http://127.0.0.1:7860
```

Ornek API cagrisi:

```powershell
curl -X POST http://127.0.0.1:7860/recommend ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Beyin MR goruntulerinden kanama tespiti yapan bir goruntu isleme algoritmasi gelistirdim.\",\"require_apc\":false,\"indexes\":[\"SCIE\"],\"limit\":3}"
```

Bu proje, UBYT yayin tesvik listesini ve Elsevier/Wiley APC destek listelerini yerel bir MCP server olarak Codex, GitHub Copilot gibi MCP destekleyen yapay zeka istemcilerine acar.

Destek turleri farklidir:

- `ubyt.xlsx`: UBYT dergilerinde yayin yapildiginda TUBITAK yayin tesvik odemesi bilgisini verir.
- `Elsevier.xlsx` ve `Wiley.xlsx`: ilgili dergilerde APC ucretinin TUBITAK tarafindan karsilanabildigi destek listelerini verir.

Server `stdio` transport kullanir. Yani server normal bir web portu acmaz; MCP istemcisi gerekli oldugunda `python server.py` komutunu arka planda baslatir ve standart giris/cikis uzerinden haberlesir.

## 1. Dosya Yapisi

Proje klasoru:

```text
C:\Codes\UBYT_MCP
```

Beklenen dosyalar:

```text
ubyt.xlsx
Elsevier.xlsx
Wiley.xlsx
server.py
requirements.txt
README.md
```

Excel dosyalari proje kokunde durmalidir:

```text
C:\Codes\UBYT_MCP\ubyt.xlsx
C:\Codes\UBYT_MCP\Elsevier.xlsx
C:\Codes\UBYT_MCP\Wiley.xlsx
```

## 2. Python Bagimliliklarini Kur

PowerShell veya VS Code terminalinde proje klasorune gel:

```powershell
cd C:\Codes\UBYT_MCP
```

Bagimliliklari kur:

```powershell
pip install -r requirements.txt
```

Gerekli paketler:

- `mcp`
- `pandas`
- `openpyxl`

## 3. Server'i Manuel Test Et

Terminalde:

```powershell
cd C:\Codes\UBYT_MCP
python server.py
```

Bu komut calistiginda ekrana bir sey yazmadan beklemesi normaldir. Cunku MCP server `stdio` modunda calisir ve bir MCP istemcisinden mesaj bekler.

Testi kapatmak icin:

```text
Ctrl+C
```

Not: Server'i manuel calisir halde birakman gerekmez. Codex'e tanittiktan sonra Codex server'i kendisi baslatir.

## 4. Codex'e MCP Server Olarak Ekle

### Yontem A: `codex` komutu terminalde calisiyorsa

Terminalde su komutu calistir:

```powershell
codex mcp add ubyt -- python C:\Codes\UBYT_MCP\server.py
```

Kontrol et:

```powershell
codex mcp list
```

Beklenen ciktiya benzer:

```text
Name  Command  Args                         Status
ubyt  python   C:\Codes\UBYT_MCP\server.py  enabled
```

### Yontem B: `codex` komutu taninmiyorsa

VS Code Codex extension icindeki `codex.exe` dosyasini bulup ayni komutu onunla calistir.

PowerShell:

```powershell
$codex = Get-ChildItem "$env:USERPROFILE\.vscode\extensions" -Recurse -Filter codex.exe | Select-Object -First 1 -ExpandProperty FullName
& $codex mcp add ubyt -- python C:\Codes\UBYT_MCP\server.py
```

Kontrol:

```powershell
& $codex mcp list
```

Bu projede gorulen ornek `codex.exe` yolu:

```text
C:\Users\KMK\.vscode\extensions\openai.chatgpt-26.422.21459-win32-x64\bin\windows-x86_64\codex.exe
```

Extension surumu degisebilecegi icin yukaridaki `$codex = Get-ChildItem ...` komutu daha geneldir.

## 5. Elle Config Ekleme Alternatifi

Komutla ekleme calismazsa Codex config dosyasini elle duzenleyebilirsin:

```text
C:\Users\KMK\.codex\config.toml
```

Dosyanin sonuna sunu ekle:

```toml
[mcp_servers.ubyt]
command = "python"
args = ["C:\\Codes\\UBYT_MCP\\server.py"]
```

Kaydettikten sonra VS Code icindeki Codex oturumunu yeniden baslat.

## 6. VS Code Codex Icinde Test Et

VS Code'da Codex'i yeniden baslat veya yeni bir Codex oturumu ac.

Sonra Codex'e sunlari sor:

```text
UBYT MCP ile 0140-6736 ISSN numarali dergiyi ara.
```

Beklenen sonuc:

```text
LANCET
ISSN: 0140-6736
eISSN: 1474-547X
```

Baska bir test:

```text
UBYT listesinden LANCET dergisini bul.
```

Beklenen davranis: Codex `search_journals` aracini kullanir ve LANCET ile baslayan/eslesen dergileri listeler.

APC destek testi:

```text
Wiley APC destek listesinde Abacus dergisini ara.
```

Birlesik destek testi:

```text
CA-A CANCER JOURNAL FOR CLINICIANS dergisi UBYT tesvik listesinde mi ve APC destegi var mi?
```

## 7. GitHub Copilot ile VS Code Icinde Kullan

GitHub Copilot, VS Code icinde MCP server'lari `.vscode/mcp.json` dosyasindan okuyabilir.

Bu proje icin dosya hazir:

```text
.vscode/mcp.json
```

Icerigi:

```json
{
  "servers": {
    "ubyt": {
      "type": "stdio",
      "command": "python",
      "args": ["${workspaceFolder}/server.py"]
    }
  }
}
```

Calistirma adimlari:

1. VS Code'u `C:\Codes\UBYT_MCP` klasorunde ac.
2. GitHub Copilot Chat panelini ac.
3. Chat modunu `Agent` olarak sec.
4. `.vscode/mcp.json` dosyasini ac.
5. Dosyanin ust tarafinda gorunen `Start` butonuna bas.
6. Copilot Chat'teki tools/araclar ikonundan `ubyt` server ve araclarinin gorundugunu kontrol et.
7. Copilot'a sunu sor:

```text
UBYT MCP ile 0140-6736 ISSN numarali dergiyi ara.
```

Beklenen sonuc:

```text
LANCET
ISSN: 0140-6736
eISSN: 1474-547X
```

Copilot MCP tool kullanmak icin izin isterse onay ver. Server web portu acmaz; Copilot gerekli oldugunda `python server.py` komutunu arka planda calistirir.

## 8. UBYT Tesvik ve APC Destegi

UBYT ve APC destekleri farkli seylerdir:

- UBYT listesinde bulunmak yayin tesvik odemesi ile ilgilidir.
- Elsevier/Wiley APC listesinde bulunmak makale islem ucretinin desteklenmesi ile ilgilidir.
- Bir dergi sadece UBYT listesinde, sadece APC listesinde veya iki listede birden olabilir.

Tek dergi kontrolu icin:

```text
Bu dergi UBYT tesvik listesinde mi ve Elsevier/Wiley APC destegi var mi?
```

Bu istek icin ajan genellikle `check_journal_support` tool'unu kullanir.

APC listelerinde arama icin:

```text
Elsevier veya Wiley APC destek listesinde 3 Biotech dergisini ara.
```

Bu istek icin ajan `search_apc_supported_journals` tool'unu kullanir.

## 9. Ajan Destekli Aday Dergi Bulma

Server konuya ozel hard-coded tip/alan sozlukleri kullanmaz. Konu yorumlama isi Codex veya Copilot ajaninda kalir. MCP server'in gorevi, ajanin cikardigi anahtar kelimeleri ve filtreleri UBYT/APC listelerine hizli ve deterministik sekilde uygulamaktir.

Codex veya Copilot'a su sekilde sor:

```text
Bu makale konusuna gore uygun UBYT dergileri bul. Once anahtar kelimeleri cikar, sonra find_journal_candidates tool'unu kullan.
```

Ornek konu:

```text
Beyin MR goruntulerinden kanama tespiti yapan yapay zeka yayini
```

Serbest dogal dil sorgu ornegi:

```text
Beyin kanamasinin ne zaman olustugunu MR goruntulerinden tespit eden bir goruntu isleme algoritmasi gelistirdim. Hangi dergilere gonderebilirim, ilk 3 dergiyi ilgi sirasina gore siralayarak ver.
```

Bu tip bir istekte beklenen kullanim sekli sunlardir:

- Ajan once konu bilesenlerini ayirir: `brain`, `hemorrhage`, `timing/onset`, `MR/MRI`, `image processing`, `algorithm`.
- Ardindan yontem uygunlugu yuksek alan terimlerini uretir: `medical imaging`, `medical image analysis`, `image processing`, `computer assisted radiology`, `mri`.
- Klinik olarak ilgili ama yontem odagi zayif dergileri otomatik ust siraya tasimamak icin closed-set shortlist uretir.
- `prepare_scope_review_candidates` ile yalnizca UBYT/APC veri kumesinden aday listesi cikarir; web'i yeni dergi bulmak icin degil, bu adaylarin resmi aims/scope sayfalarini dogrulamak icin kullanir.
- Son asamada ajan yalnizca dogrulanan adaylar icinden ilk 3 dergiyi ilgi sirasina gore aciklayarak sunar.

Bu sorgu icin ajan sunu benzeri bir arac cagrisi yapabilir:

```text
prepare_scope_review_candidates(
  optional_terms=["medical imaging", "medical image analysis", "image processing", "computer assisted radiology", "brain", "mri", "hemorrhage", "detection"],
  indexes=["SCIE"],
  sort_by="relevance",
  limit=10
)
```

Beklenen cevap formati yalnizca ham dergi listesi degil, kisa gerekceli bir siralamadir. Bu ornek sorgu icin uygun bir cevap soyle olabilir:

```text
1. IEEE TRANSACTIONS ON MEDICAL IMAGING
  MRI, medical image processing, pattern recognition ve machine learning kapsaminda dogrudan yontem odakli en guclu aday.

2. Medical Image Analysis
  Calismanin asil katkisi yeni bir goruntu isleme veya derin ogrenme yontemiyse, yontem makalesi olarak cok uygun bir secenek.

3. COMPUTERIZED MEDICAL IMAGING AND GRAPHICS
  AI-enabled imaging solutions ve uygulamali medikal goruntu analizi tarafinda guclu, yontem agirlikli bir alternatiftir.
```

Kullanici ilk cevapten sonra su takip sorgusunu girebilir:

```text
Bu 3 dergi icinden hangilerinin yayin ucretleri karsilaniyor?
```

Bu noktada beklenen kullanim sekli sudur:

- Ajan once onceki mesajdaki 3 dergiyi baglamdan tasir.
- Tercihen `check_multiple_journal_support` ile bu dergileri tek cagrida kontrol eder.
- Cevapta bu 3 dergi icin APC destegi gorunmuyorsa bunu acikca soyler; sonradan APC zorunlu hale gelirse yeni bir `require_apc=true` sorgusu ile alternatif shortlist uretir.

Bu takip sorgusu icin arac kullanim mantigi soyle olabilir:

```text
check_multiple_journal_support(
  queries=[
    "IEEE TRANSACTIONS ON MEDICAL IMAGING",
    "Medical Image Analysis",
    "COMPUTERIZED MEDICAL IMAGING AND GRAPHICS"
  ]
)
```

Beklenen cevap soyle olabilir:

```text
Bu 3 dergi icin mevcut Elsevier/Wiley APC veri setinde yayin ucreti destegi gorunmuyor.

IEEE TRANSACTIONS ON MEDICAL IMAGING:
UBYT listesinde var, ancak APC destegi gorunmuyor.

Medical Image Analysis:
UBYT listesinde var, ancak APC destegi gorunmuyor.

COMPUTERIZED MEDICAL IMAGING AND GRAPHICS:
UBYT listesinde var, ancak APC destegi gorunmuyor.
```

Kullanici daha sonra tek bir dergi icin su sorguyu da sorabilir:

```text
Brain Imaging and Behavior adli dergi UBYT listesinde mi? APC karsilaniyor mu?
```

Bu sorguda ajan, tek adimda `check_journal_support` aracini kullanabilir:

```text
check_journal_support(query="Brain Imaging and Behavior")
```

Beklenen cevap, APC destegi bilgisini veri kaynagi ile birlikte dikkatli vermelidir:

```text
Brain Imaging and Behavior UBYT listesinde gorunuyor.
APC destegi de var gorunuyor.

Ancak burada dikkat edilmesi gereken nokta sunudur:
APC eslesmesi `Elsevier.xlsx` veri dosyasindaki kayittan geliyor, fakat eslesen satirin `publisher_or_imprint` alani `Springer`.
```

Bu nedenle ajan, bu tip durumlarda "Elsevier listesinde var" demek yerine daha kesin bir dil kullanmalidir:

```text
Mevcut MCP veri dosyasina gore APC eslesmesi bulundu.
Eslesme kaynagi: Elsevier.xlsx
Imprint/Yayinci: Springer
Eslesme alani: eISSN
```

Bu ornek onemlidir; cunku veri dosyasinin adi ile derginin fiili imprint/yayinci bilgisi her zaman ayni sey olmayabilir. Kullanici listeyi gozle kontrol ettiginde celiski gordugunu dusunurse, yanit `raw_source_file`, `publisher_or_imprint` ve eslesme tipini birlikte aciklamalidir.

Kullanici toplu dergi kontrolu icin su tip bir sorgu da girebilir:

```text
Asagidaki dergiler UBYT listesinde mi?
IEEE Journal of Translational Engineering in Health and Medicine
Health Information Management Journal
Health Informatics Journal
```

Bu durumda ajan, dergi adlarini ayri ayri cikartip tek seferde `check_multiple_journal_support` aracini kullanabilir:

```text
check_multiple_journal_support(
  queries=[
    "IEEE Journal of Translational Engineering in Health and Medicine",
    "Health Information Management Journal",
    "Health Informatics Journal"
  ]
)
```

Beklenen cevap soyle olabilir:

```text
Bu uc dergi de UBYT listesinde gorunuyor.

IEEE Journal of Translational Engineering in Health and Medicine:
UBYT: Evet

Health Information Management Journal:
UBYT: Evet

Health Informatics Journal:
UBYT: Evet
```

Kullanici bunun hemen ardindan su follow-up sorgusunu girebilir:

```text
Evet. APC durumlari.
```

Bu follow-up icin ajan, onceki mesajdaki ayni 3 dergiyi baglamdan tasiyip yine `check_multiple_journal_support` ile toplu kontrol yapabilir.

Beklenen cevap soyle olabilir:

```text
Bu uc dergi icin mevcut Elsevier/Wiley APC veri setinde APC destegi gorunmuyor.

IEEE Journal of Translational Engineering in Health and Medicine:
APC: Gorunmuyor

Health Information Management Journal:
APC: Gorunmuyor

Health Informatics Journal:
APC: Gorunmuyor
```

Buradaki beklenti onemlidir: ilgi sirasi yalnizca MEP puanina gore verilmez. Ajan, konu uyumunu onceleyip gerekirse daha yuksek puanli ama kapsamsal olarak daha genel dergileri alt siraya koyabilir.

Ajan bu konudan su gibi dergi anahtar kelimeleri cikarabilir:

```text
radiology, imaging, medical imaging, neuro, neurology, brain, stroke
```

Sonra MCP tool'u soyle kullanilir:

```text
find_journal_candidates(
  optional_terms=["radiology", "imaging", "medical imaging", "neuro", "neurology", "brain", "stroke"],
  indexes=["SCIE"],
  require_apc=true,
  apc_providers=["elsevier", "wiley"],
  sort_by="relevance",
  limit=20
)
```

Ayni genel tool baska alanlarda da kullanilir:

```text
optional_terms=["economics", "finance", "management"]
optional_terms=["education", "learning", "teaching"]
optional_terms=["engineering", "materials", "mechanical"]
```

Not: Excel'de dergilerin aims/scope metni olmadigi icin server semantik uygunluk iddiasinda bulunmaz. Nihai dergi secimi icin derginin aims/scope sayfasi, makale turu, yayin ucreti, indeks durumu ve kabul politikalari ayrica kontrol edilmelidir.

Hem UBYT tesvik listesinde hem APC destek listesinde olan adaylar icin:

```text
Bu makale konusu icin hem UBYT listesinde olan hem de Elsevier veya Wiley APC destegi bulunan dergileri bul.
```

## 10. MCP Tool'lari

Server sekiz tool sunar:

```text
search_journals(query: str, limit: int = 10)
```

Dergi adi, ISSN veya eISSN ile arama yapar. Ornekler:

```text
LANCET
0140-6736
01406736
Nature Reviews
```

```text
get_journal_by_number(number: str)
```

ISSN veya eISSN ile kesin eslesme arar. Ornek:

```text
1542-4863
```

```text
find_journal_candidates(
  required_terms: list[str] = [],
  optional_terms: list[str] = [],
  exclude_terms: list[str] = [],
  indexes: list[str] = [],
  require_ubyt: bool = false,
  require_apc: bool = false,
  apc_providers: list[str] = [],
  source: str | None = None,
  min_mep_score: float | None = None,
  max_payment_tl: int | None = None,
  sort_by: str = "relevance",
  limit: int = 20
)
```

Ajanin cikardigi anahtar kelimeler, indeksler ve sayisal filtrelerle aday dergi listesi uretir.

Bu tool hizli yerel aday filtreleme icindir. Derginin gercek aims/scope uygunlugunu tek basina dogrulamaz.

APC filtreleri:

```text
require_apc=true
apc_providers=["elsevier", "wiley"]
```

Desteklenen `sort_by` degerleri:

```text
relevance
mep_desc
payment_desc
name_asc
```

```text
search_apc_supported_journals(
  query: str,
  providers: list[str] = [],
  limit: int = 20
)
```

Elsevier/Wiley APC destek listelerinde dergi adi, ISSN veya eISSN ile arama yapar. Ornek:

```text
search_apc_supported_journals("Abacus", providers=["wiley"])
search_apc_supported_journals("3 Biotech", providers=["elsevier"])
search_apc_supported_journals("14676281", providers=["wiley"])
```

```text
check_journal_support(query: str | None = None, number: str | None = None)
```

Tek dergi icin UBYT tesvik ve APC destek durumunu birlikte kontrol eder. Donen ozet:

```text
ubyt_incentive_eligible
apc_funding_eligible
both_eligible
apc_providers
apc_evidence
ubyt_matches
apc_matches
```

`apc_evidence` ozeti, ozellikle veri kaynagi ile imprint/yayinci farkli olabildiginde kullanislidir. Ornek alanlar:

```text
match_count
source_files
publishers_or_imprints
match_types
best_match
```

```text
check_multiple_journal_support(
  queries: list[str] = [],
  numbers: list[str] = []
)
```

Birden fazla dergi icin UBYT ve APC destek durumunu tek cagrida kontrol eder. Ozellikle "Bu 3 dergi icinden hangilerinin yayin ucretleri karsilaniyor?" gibi follow-up sorularda ajanin tek tek birden cok tool cagrisi yapmasi yerine bu tool tercih edilmelidir.

```text
prepare_scope_review_candidates(
  required_terms: list[str] = [],
  optional_terms: list[str] = [],
  exclude_terms: list[str] = [],
  indexes: list[str] = [],
  require_apc: bool = false,
  apc_providers: list[str] = [],
  source: str | None = None,
  min_mep_score: float | None = None,
  max_payment_tl: int | None = None,
  sort_by: str = "relevance",
  limit: int = 10
)
```

Bu tool closed-set shortlist uretir. Agent web'de yeni dergi kesfetmez; yalnizca bu tool'un dondurdugu adaylarin resmi aims/scope sayfalarini dogrular.

Donen alanlar arasinda su alanlar bulunur:

```text
closed_set_only
candidate_ids
web_verification_policy
candidates[].candidate_id
candidates[].canonical_title
candidates[].issn
candidates[].eissn
candidates[].preferred_url
candidates[].verification_query
candidates[].must_match_identifiers
candidates[].scope_hints
```

Ornek closed-set kullanim akisi:

```text
prepare_scope_review_candidates(
  optional_terms=["neuroradiology", "radiology", "medical imaging", "brain", "mri", "hemorrhage"],
  indexes=["SCIE"],
  require_apc=true,
  apc_providers=["elsevier", "wiley"],
  sort_by="relevance",
  limit=5
)
```

Bu akista agent su kurala uymak zorundadir:

```text
Web yalnizca donen candidate_id listesindeki dergileri dogrulamak icin kullanilir.
Listede olmayan hicbir dergi final oneriye eklenmez.
Resmi sayfa canonical title veya ISSN/eISSN ile eslesmiyorsa aday reddedilir.
```

```text
recommend_journals_for_topic(topic: str, limit: int = 20)
```

Geriye uyumluluk icin duran sinirli yardimci tool'dur. Alan-ozel eslestirme yapmaz; konu metnini basit token'lara boler. Daha iyi sonuc icin ajan `find_journal_candidates` kullanmalidir. Ornek:

```text
Beyin MR goruntulerinden kanama tespiti yapan yapay zeka yayini
```

## 11. Sorun Giderme

### `codex : The term 'codex' is not recognized`

Bu, Codex CLI'in terminal PATH'inde olmadigi anlamina gelir. Yontem B'yi kullan:

```powershell
$codex = Get-ChildItem "$env:USERPROFILE\.vscode\extensions" -Recurse -Filter codex.exe | Select-Object -First 1 -ExpandProperty FullName
& $codex mcp add ubyt -- python C:\Codes\UBYT_MCP\server.py
```

### `ModuleNotFoundError: No module named ...`

Bagimliliklari kur:

```powershell
cd C:\Codes\UBYT_MCP
pip install -r requirements.txt
```

### `Excel file not found` veya `APC file not found`

Excel dosyalarinin burada oldugunu kontrol et:

```text
C:\Codes\UBYT_MCP\ubyt.xlsx
C:\Codes\UBYT_MCP\Elsevier.xlsx
C:\Codes\UBYT_MCP\Wiley.xlsx
```

### MCP eklendi ama Codex gormuyor

1. VS Code'daki Codex oturumunu kapat.
2. VS Code'u yeniden baslat.
3. Terminalden kontrol et:

```powershell
codex mcp list
```

veya `codex` PATH'te degilse:

```powershell
$codex = Get-ChildItem "$env:USERPROFILE\.vscode\extensions" -Recurse -Filter codex.exe | Select-Object -First 1 -ExpandProperty FullName
& $codex mcp list
```

### GitHub Copilot `ubyt` MCP server'ini gormuyor

1. VS Code'un `C:\Codes\UBYT_MCP` klasorunu actigindan emin ol.
2. `.vscode/mcp.json` dosyasinin var oldugunu kontrol et.
3. GitHub Copilot Chat'te `Agent` modunu sec.
4. `.vscode/mcp.json` dosyasindaki `Start` butonuna bas.
5. VS Code'u yeniden baslat.

Copilot Business veya Enterprise kullaniyorsan kurum politikasinda MCP server kullanimi kapali olabilir. Bu durumda Copilot MCP araclarini listelemez.
