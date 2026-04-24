# UBYT + APC Destek MCP Server

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

Server alti tool sunar:

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
ubyt_matches
apc_matches
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
