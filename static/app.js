const form = document.getElementById("query-form");
const stream = document.getElementById("stream");
const template = document.getElementById("response-template");
const drawer = document.getElementById("drawer");
const drawerContent = document.getElementById("drawer-content");
const statusPanel = document.getElementById("status-panel");
const statusTitle = document.getElementById("status-title");
const statusCopy = document.getElementById("status-copy");
const statusSteps = document.getElementById("status-steps");
const maxPaymentSelect = document.getElementById("max-payment");
const indexFilterSelect = document.getElementById("index-filter");
const pageCredits = document.querySelectorAll("[data-version-stamp]");
const visitCounter = document.getElementById("visit-counter");

const STATUS_PHASES = [
  {
    title: "Ollama Cloud erişimi kuruluyor",
    copy: "Sorgu, journal title eşleşmesinde kullanılacak İngilizce arama terimlerini üretmesi için Ollama Cloud'a hazırlanıyor.",
    step: "Ollama erişimi deneniyor",
  },
  {
    title: "Ollama terim yanıtı doğrulanıyor",
    copy: "Structured output kontrol ediliyor; model yanıt veremezse yerel terim fallback'i otomatik devreye alınacak.",
    step: "Ollama geri dönüşü kontrol ediliyor",
  },
  {
    title: "Title tarama terimleri hazırlanıyor",
    copy: "Zorunlu ve sıralama terimleri normalize edilerek Excel'deki dergi başlıklarında taramaya uygun hale getiriliyor.",
    step: "Başlık tarama terimleri hazırlanıyor",
  },
  {
    title: "Yerel shortlist oluşturuluyor",
    copy: "UBYT veri setinde title matching yapılıyor, aday havuzu skorluyor ve ilk sıralama çıkarılıyor.",
    step: "Yerel aday havuzu skorluyor",
  },
  {
    title: "Ollama judge yeniden sıralaması deneniyor",
    copy: "Yerel shortlist, gerekirse Ollama judge'e verilerek kullanıcı sorgusuna göre yeniden sıralanıyor; başarısız olursa yerel sıra korunuyor.",
    step: "Ollama judge sıralaması değerlendiriliyor",
  },
  {
    title: "APC destek kayıtları bağlanıyor",
    copy: "Elsevier ve Wiley kayıtlarıyla APC destek ve yayınevi bilgileri aday dergilere bağlanıyor.",
    step: "APC destek kayıtları bağlanıyor",
  },
  {
    title: "Kartlar ve indirme verisi hazırlanıyor",
    copy: "Sonuç kartları, detay drawer içeriği ve Excel indirme payload'ı birlikte oluşturuluyor.",
    step: "Kart ve çıktı verisi hazırlanıyor",
  },
];

const STATUS_FINAL_PHASE_ROTATION = [
  {
    title: "Kart özetleri hazırlanıyor",
    copy: "Sonuç kartlarının başlık, metrik ve badge alanları birleştiriliyor.",
  },
  {
    title: "Detay drawer verisi hazırlanıyor",
    copy: "Açılır detay panelinde gösterilecek APC, UBYT ve eşleşme alanları paketleniyor.",
  },
  {
    title: "Excel indirme verisi hazırlanıyor",
    copy: "İndir butonunun kullanacağı export payload'ı aynı sonuç kümesi için hazırlanıyor.",
  },
  {
    title: "Son sonuçlar arayüze aktarılıyor",
    copy: "Backend yanıtı işlenip sonuç bloğu ve kart listesi ekrana yazdırılmak üzere tamamlanıyor.",
  },
];

let statusTimer = null;
let statusPhaseIndex = 0;
let statusDotFrame = 0;
let clientConfigPromise = null;

function buildVersionStamp(date = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  const year = String(date.getFullYear());
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hour = pad(date.getHours());
  const minute = pad(date.getMinutes());
  const second = pad(date.getSeconds());
  return `${year}${month}${day}-${hour}${minute}${second}`;
}

function renderPageCredit() {
  if (!pageCredits.length) return;
  const creditText = `Murat Karakaya Akademi 2026 • Versiyon ${buildVersionStamp()}`;
  pageCredits.forEach((node) => {
    node.textContent = creditText;
  });
}

function renderVisitCounter(count) {
  if (!visitCounter) return;
  const formattedCount = Number(count || 0).toLocaleString("tr-TR");
  visitCounter.textContent = `Bu uygulama şimdiye kadar ${formattedCount} kez görüntülendi.`;
}

function getCounterValue(result) {
  const data = result?.data || result;
  if (!data) return null;

  if (typeof result?.value === "number") {
    return result.value;
  }

  const upCount = Number(data.up_count || 0);
  const downCount = Number(data.down_count || 0);
  if (Number.isFinite(upCount) && Number.isFinite(downCount)) {
    return upCount - downCount;
  }

  return null;
}

async function loadClientConfig() {
  if (!clientConfigPromise) {
    clientConfigPromise = fetch("/client-config").then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    });
  }

  return clientConfigPromise;
}

async function recordVisit() {
  if (!visitCounter) return;
  try {
    const config = await loadClientConfig();
    const counterConfig = config?.counterapi;

    if (!counterConfig?.enabled || !counterConfig.workspace) {
      visitCounter.textContent = "Görüntülenme sayacı henüz yapılandırılmadı.";
      return;
    }

    if (typeof Counter === "undefined") {
      throw new Error("CounterAPI library not loaded");
    }

    const counter = new Counter({
      workspace: counterConfig.workspace,
      timeout: 5000,
    });
    const result = await counter.up(counterConfig.counter_name || "page-views");
    const count = getCounterValue(result);

    if (!Number.isFinite(count)) {
      throw new Error("CounterAPI response missing numeric count");
    }

    renderVisitCounter(count);
  } catch (error) {
    visitCounter.textContent = "Görüntülenme bilgisi şu anda alınamıyor.";
  }
}

function formatPaymentLimitLabel(value) {
  if (value === null || value === undefined || value === "") {
    return "Maksimum destek miktarı: Tümü";
  }

  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return `Maksimum destek miktarı: ${value}`;
  }

  return `Maksimum destek miktarı: ${amount.toLocaleString("tr-TR")} TL ve altı`;
}

function formatIndexesLabel(indexes) {
  if (!indexes.length) {
    return "İndeks: Tümü";
  }

  return `İndeks: ${indexes.join(", ")}`;
}

function formatRequireApcLabel(requireApc) {
  return requireApc ? "APC: Sadece destekli olanları öne çıkar" : "";
}

function formatRerankLabel(rerankInfo) {
  const status = rerankInfo?.status || "local";
  if (status === "success") {
    return "Yeniden sıralama: Ollama Judge";
  }
  if (["request_failed", "invalid_response", "import_error"].includes(status)) {
    return "Yeniden sıralama: Lokal fallback";
  }
  return "Yeniden sıralama: Lokal";
}

const exportPayloads = new Map();

function buildExportRequest(query, payload) {
  return {
    query,
    query_summary: payload.query_summary || {},
    results: payload.results || [],
  };
}

function downloadFilenameFromResponse(response, fallback = "dergi-sonuclari.xlsx") {
  const header = response.headers.get("Content-Disposition") || "";
  const match = header.match(/filename="?([^";]+)"?/i);
  return match?.[1] || fallback;
}

async function downloadResultsExcel(exportRequest, trigger) {
  const originalLabel = trigger.textContent;
  trigger.disabled = true;
  trigger.textContent = "İndiriliyor...";

  try {
    const response = await fetch("/export-results", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(exportRequest),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const downloadLink = document.createElement("a");
    downloadLink.href = objectUrl;
    downloadLink.download = downloadFilenameFromResponse(response);
    document.body.append(downloadLink);
    downloadLink.click();
    downloadLink.remove();
    URL.revokeObjectURL(objectUrl);
  } finally {
    trigger.disabled = false;
    trigger.textContent = originalLabel;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function termPillsMarkup(terms) {
  if (!terms.length) {
    return '<span class="response-note">yok</span>';
  }

  return terms
    .map((term) => `<span class="response-pill">${escapeHtml(term)}</span>`)
    .join("");
}

function appliedRequiredMarkup(rankingMode, terms) {
  if (rankingMode === "relaxed-required-to-optional") {
    return '<span class="response-note">Bu turda zorunlu filtre uygulanmadı.</span>';
  }

  return termPillsMarkup(terms);
}

async function loadFilterOptions() {
  try {
    const response = await fetch("/filters");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    if (Array.isArray(payload.max_payment_options)) {
      maxPaymentSelect.innerHTML = payload.max_payment_options
        .map((option) => `<option value="${option.value}">${option.label}</option>`)
        .join("");
    }

    if (Array.isArray(payload.index_options)) {
      indexFilterSelect.innerHTML = payload.index_options
        .map((option) => `<option value="${option.value}">${option.label}</option>`)
        .join("");
      indexFilterSelect.value = "";
    }
  } catch (error) {
    maxPaymentSelect.value = "";
    indexFilterSelect.value = "";
  }
}

function badgeKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function badgeMarkup(badge, result = null) {
  const classes = ["badge"];
  const key = badgeKey(badge);

  if (key === "ubyt") {
    classes.push("badge-ubyt");
  } else {
    classes.push("badge-provider", `badge-provider-${key}`);
  }

  if (result?.apc_supported) {
    classes.push("badge-apc-context");
  }

  return `<span class="${classes.join(" ")}">${badge}</span>`;
}

function provenanceText(result) {
  return (result.provenance?.sources || []).join(" • ");
}

function statusStepMarkup(label, state) {
  return `
    <div class="status-step ${state}">
      <span class="status-step-dot"></span>
      <span class="status-step-label">${label}</span>
    </div>
  `;
}

function renderStatus(index) {
  const activePhase = STATUS_PHASES[index] || STATUS_PHASES[0];
  statusTitle.textContent = activePhase.title;
  statusCopy.textContent = activePhase.copy;

  statusSteps.innerHTML = STATUS_PHASES.map((phase, phaseIndex) => {
    const state = phaseIndex < index ? "completed" : phaseIndex === index ? "active" : "";
    return statusStepMarkup(phase.step, state);
  }).join("");
}

function startStatusFlow() {
  clearInterval(statusTimer);
  statusPhaseIndex = 0;
  statusDotFrame = 0;
  statusPanel.classList.remove("done", "error");
  statusPanel.classList.add("active");
  statusPanel.setAttribute("aria-hidden", "false");
  renderStatus(statusPhaseIndex);

  statusTimer = setInterval(() => {
    if (statusPhaseIndex < STATUS_PHASES.length - 1) {
      statusPhaseIndex += 1;
      renderStatus(statusPhaseIndex);
      return;
    }

    statusDotFrame = (statusDotFrame + 1) % 4;
    const dots = ".".repeat(statusDotFrame || 1);
    const rotationIndex = statusDotFrame % STATUS_FINAL_PHASE_ROTATION.length;
    const activeWaitingPhase = STATUS_FINAL_PHASE_ROTATION[rotationIndex];
    statusTitle.textContent = `${activeWaitingPhase.title}${dots}`;
    statusCopy.textContent = activeWaitingPhase.copy;
  }, 1500);
}

function llmAccessStep(llm) {
  if (llm.attempted || llm.enabled) {
    return `Ollama erişimi: ${llm.host || "https://ollama.com"}`;
  }

  return "Ollama erişimi atlandı; yerel terim fallback'i hazır";
}

function llmResponseStep(payload) {
  const llm = payload?.query_summary?.llm || {};
  const model = llm.model || "gpt-oss:120b";
  const source = payload?.query_summary?.keyword_source;

  if (source === "ollama-cloud") {
    return `Ollama terim yanıtı alındı: ${model}`;
  }

  if (llm.attempted || llm.enabled) {
    return "Ollama terim yanıtı kullanılamadı; yerel fallback devrede";
  }

  return "Ollama terim yanıtı istenmedi";
}

function termSummaryStep(payload) {
  const requiredCount = payload?.query_summary?.required_terms?.length || 0;
  const optionalCount = payload?.query_summary?.applied_optional_terms?.length || 0;
  return `Başlık tarama terimleri hazır: ${requiredCount} zorunlu, ${optionalCount} sıralama terimi`;
}

function shortlistSummaryStep(payload) {
  const poolCount = payload?.query_summary?.candidate_pool_count ?? payload?.results?.length ?? 0;
  const rankingMode = rankingModeLabel(payload?.query_summary?.ranking_mode || "strict-required");
  return `Yerel shortlist hazır: ${poolCount} aday, mod ${rankingMode.toLowerCase()}`;
}

function rerankSummaryStep(payload) {
  const rerank = payload?.query_summary?.rerank || {};
  const candidatePoolCount = payload?.query_summary?.candidate_pool_count ?? payload?.results?.length ?? 0;

  if (rerank.status === "success") {
    return `Ollama judge uygulandı: ${candidatePoolCount} aday yeniden sıralandı`;
  }

  if (rerank.status === "skipped_small_pool") {
    return "Ollama judge atlandı: aday havuzu küçük, yerel sıra korundu";
  }

  if (["request_failed", "invalid_response", "import_error", "disabled"].includes(rerank.status)) {
    return "Ollama judge kullanılamadı; yerel sıra korundu";
  }

  return "Yeniden sıralama yapılmadı; yerel sıra kullanıldı";
}

function apcSummaryStep(payload) {
  return payload?.query_summary?.require_apc
    ? "APC kayıtları bağlandı; yalnızca APC odaklı filtre aktif"
    : "APC kayıtları bağlandı; APC bilgileri aday kartlara işlendi";
}

function renderSummaryStep(payload) {
  const resultCount = payload?.query_summary?.result_count ?? payload?.results?.length ?? 0;
  return `${resultCount} sonuç için kartlar, detay paneli ve Excel çıktısı hazırlandı`;
}

function buildStatusCopy(payload) {
  const llmText = payload?.query_summary?.llm?.status_text;
  const rerankText = payload?.query_summary?.rerank?.status_text;
  return [llmText, rerankText].filter(Boolean).join(" ")
    || "Arama tamamlandı; aday havuzu, yeniden sıralama ve kart oluşturma adımları tamamlandı.";
}

function resolvedStatusSteps(payload) {
  const llm = payload?.query_summary?.llm || {};

  return [
    llmAccessStep(llm),
    llmResponseStep(payload),
    termSummaryStep(payload),
    shortlistSummaryStep(payload),
    rerankSummaryStep(payload),
    apcSummaryStep(payload),
    renderSummaryStep(payload),
  ];
}

function finishStatusFlow(state = "done", payload = null) {
  clearInterval(statusTimer);
  statusPanel.classList.remove("active", "done", "error");
  statusPanel.classList.add(state);

  if (state === "done") {
    statusTitle.textContent = "Sonuçlar hazır";
    statusCopy.textContent = buildStatusCopy(payload);
    statusSteps.innerHTML = resolvedStatusSteps(payload)
      .map((step) => statusStepMarkup(step, "completed"))
      .join("");
  } else {
    statusTitle.textContent = "Sorgu tamamlanamadı";
    statusCopy.textContent = "Geçici bir hata oluştu. Aynı sorguyu tekrar deneyebilir veya opsiyonları değiştirebilirsiniz.";
  }
}

function metricMarkup(label, value, accent = "") {
  return `
    <div class="metric-chip ${accent}">
      <span class="metric-label">${label}</span>
      <strong class="metric-value">${value || "-"}</strong>
    </div>
  `;
}

function definitionRow(label, value) {
  return `
    <div>
      <dt>${label}</dt>
      <dd>${value || "-"}</dd>
    </div>
  `;
}

function apcDetailMarkup(detail) {
  const link = detail.url && detail.url !== "-"
    ? `<a class="drawer-link secondary" href="${detail.url}" target="_blank" rel="noreferrer">Kaynağı aç</a>`
    : "";

  return `
    <section class="detail-card">
      <div class="detail-card-header">
        <h3>${detail.provider}</h3>
        <span class="detail-card-meta">${detail.raw_source_file}</span>
      </div>
      <p class="detail-card-title">${detail.journal_title}</p>
      <dl class="drawer-grid compact">
        ${definitionRow("ISSN", detail.issn)}
        ${definitionRow("eISSN", detail.eissn)}
        ${definitionRow("Imprint / yayıncı", detail.publisher_or_imprint)}
        ${definitionRow("Ana disiplin", detail.discipline)}
        ${definitionRow("Konu", detail.subject)}
        ${definitionRow("Yayın modeli", detail.publishing_model)}
        ${definitionRow("OA lisansı", detail.oa_license)}
        ${definitionRow("WoS index", detail.wos_index)}
        ${definitionRow("Quartile", detail.quartile)}
        ${definitionRow("Impact factor", detail.impact_factor)}
        ${definitionRow("Journal ID", detail.journal_id)}
        ${definitionRow("Eşleşme tipi", detail.match_type)}
        ${definitionRow("Eşleşme skoru", detail.match_score)}
      </dl>
      ${link}
    </section>
  `;
}

function buildGoogleJournalSearchUrl(result) {
  const queryParts = [result.title, result.issn, result.eissn, "journal"]
    .map((value) => (typeof value === "string" ? value.trim() : value))
    .filter((value) => value && value !== "-");

  if (!queryParts.length) {
    return "";
  }

  return `https://www.google.com/search?q=${encodeURIComponent(queryParts.join(" "))}`;
}

function rankingModeLabel(mode) {
  if (mode === "relaxed-required-to-optional") {
    return "Genişletilmiş eşleşme";
  }
  return "Zorunlu terim eşleşmesi";
}

function cardMarkup(result) {
  const serialized = encodeURIComponent(JSON.stringify(result));
  const providerClasses = (result.badges || [])
    .filter((badge) => badge !== "UBYT")
    .map((badge) => `provider-${badgeKey(badge)}`)
    .join(" ");
  const supportClass = result.apc_supported ? "apc-supported" : "ubyt-only";
  const fallbackSearchUrl = result.preferred_url ? "" : buildGoogleJournalSearchUrl(result);
  const urlButton = result.preferred_url
    ? `<a class="card-link" href="${result.preferred_url}" target="_blank" rel="noreferrer">Dergi sayfasına git</a>`
    : fallbackSearchUrl
      ? `<a class="card-link" href="${fallbackSearchUrl}" target="_blank" rel="noreferrer">Dergi sayfasını bul</a>`
      : "";

  return `
    <article class="journal-card ${result.orientation} ${supportClass} ${providerClasses}" data-result="${serialized}">
      <div class="cover-topline">${result.orientation.toUpperCase()}</div>
      <h3>${result.title}</h3>
      <p class="card-reason">${result.fit_reason}</p>
      <div class="badge-row">${result.badges.map((badge) => badgeMarkup(badge, result)).join("")}</div>
      <div class="metric-grid">
        ${metricMarkup("Tesvik", result.support_amount, "warm")}
        ${metricMarkup("MEP", result.mep_score)}
        ${metricMarkup("Index", result.index_label)}
      </div>
      ${urlButton}
    </article>
  `;
}

function drawerMarkup(result) {
  const matchedTerms = (result.matched_terms || []).join(", ") || "Doğrudan anahtar kelime kanıtı kaydedilmedi.";
  const scopeSubjects = result.scope_hints?.subjects?.join(", ") || "APC metadata konu ipucu bulunmuyor.";
  const apcEvidence = result.apc_evidence?.best_match;
  const aliases = (result.title_aliases || []).join(" • ") || "-";
  const apcDetails = (result.apc_details || []).map(apcDetailMarkup).join("");
  const fallbackSearchUrl = result.preferred_url ? "" : buildGoogleJournalSearchUrl(result);
  const externalLink = result.preferred_url
    ? `<a class="drawer-link" href="${result.preferred_url}" target="_blank" rel="noreferrer">Dergi sayfasına git</a>`
    : fallbackSearchUrl
      ? `<a class="drawer-link" href="${fallbackSearchUrl}" target="_blank" rel="noreferrer">Dergi sayfasını bul</a>`
      : "";

  return `
    <div class="drawer-header ${result.orientation}">
      <p class="drawer-eyebrow">${result.orientation.toUpperCase()}</p>
      <h2>${result.title}</h2>
    </div>
    <p class="drawer-text">${result.fit_reason}</p>
    <div class="drawer-badges">${result.badges.map((badge) => badgeMarkup(badge, result)).join("")}</div>
    <section class="detail-section">
      <div class="section-head">
        <p class="drawer-eyebrow">UBYT kaydı</p>
      </div>
      <dl class="drawer-grid compact">
        ${definitionRow("ISSN", result.ubyt_details?.issn)}
        ${definitionRow("eISSN", result.ubyt_details?.eissn)}
        ${definitionRow("Teşvik tutarı", result.ubyt_details?.support_amount)}
        ${definitionRow("MEP puanı", result.ubyt_details?.mep_score)}
        ${definitionRow("Index", result.ubyt_details?.index_label)}
        ${definitionRow("Program", result.ubyt_details?.source_program)}
        ${definitionRow("Yıl", result.ubyt_details?.source_year)}
        ${definitionRow("Başlık eşdeğerleri", aliases)}
      </dl>
    </section>

    <dl class="drawer-grid">
      ${definitionRow("Eşleşen terimler", matchedTerms)}
      ${definitionRow("Konu ipucu", scopeSubjects)}
      ${definitionRow("UBYT", result.ubyt_eligible ? "Var" : "Yok")}
      ${definitionRow("APC", result.apc_supported ? "Destekli" : "Görünmüyor")}
      ${definitionRow("APC imprint", apcEvidence?.publisher_or_imprint || "-")}
      ${definitionRow("APC kaynak dosyası", apcEvidence?.raw_source_file || "-")}
      ${definitionRow("Kaynaklar", provenanceText(result))}
      ${definitionRow("Model kaynağı", result.provenance?.model_source || "cloud/local")}
    </dl>

    <section class="detail-section">
      <div class="section-head">
        <p class="drawer-eyebrow">APC kaynak kayıtları</p>
        <p class="section-summary">${(result.apc_details || []).length ? `${(result.apc_details || []).length} kayıt bulundu` : "Bu dergi için APC kaydı görünmüyor."}</p>
      </div>
      <div class="detail-card-stack">
        ${apcDetails || `<div class="empty-state compact">Elsevier/Wiley listelerinde bu dergi için ek APC kaydı bulunmadı.</div>`}
      </div>
    </section>

    ${externalLink}
  `;
}

function appendResponseBlock(query, payload) {
  const node = template.content.firstElementChild.cloneNode(true);
  const queryNumber = stream.querySelectorAll(".response-block").length + 1;
  const requiredTerms = payload.query_summary?.required_terms || [];
  const appliedRequiredTerms = payload.query_summary?.applied_required_terms || [];
  const appliedOptionalTerms = payload.query_summary?.applied_optional_terms || [];
  const rankingMode = payload.query_summary?.ranking_mode || "strict-required";
  const resultCount = payload.query_summary?.result_count ?? payload.results.length;
  node.querySelector(".response-query").textContent = query;
  node.querySelector(".response-label").textContent = `Sorgu ${queryNumber}`;
  const sourceLabel = payload.query_summary?.keyword_source === "ollama-cloud"
    ? "Ollama Cloud"
    : "Yerel fallback";
  const selectedIndexes = payload.query_summary?.indexes || [];
  const requireApc = Boolean(payload.query_summary?.require_apc);
  node.querySelector(".response-result-count").textContent = `${resultCount} sonuç`;
  node.querySelector(".response-ranking-mode").textContent = `Sıralama modu: ${rankingModeLabel(rankingMode)}`;
  node.querySelector(".response-rerank").textContent = formatRerankLabel(payload.query_summary?.rerank);
  node.querySelector(".response-max-payment").textContent = formatPaymentLimitLabel(payload.query_summary?.max_payment_tl);
  node.querySelector(".response-indexes").textContent = formatIndexesLabel(selectedIndexes);
  const requireApcNode = node.querySelector(".response-require-apc");
  requireApcNode.textContent = formatRequireApcLabel(requireApc);
  requireApcNode.hidden = !requireApc;
  node.querySelector(".response-source").textContent = `Kaynak: ${sourceLabel}`;
  node.querySelector(".response-required").innerHTML = termPillsMarkup(requiredTerms);
  node.querySelector(".response-applied-required").innerHTML = appliedRequiredMarkup(rankingMode, appliedRequiredTerms);
  node.querySelector(".response-optional").innerHTML = termPillsMarkup(appliedOptionalTerms);
  const downloadButton = node.querySelector("[data-download-results]");
  const exportKey = `query-${queryNumber}`;
  exportPayloads.set(exportKey, buildExportRequest(query, payload));
  downloadButton.dataset.exportKey = exportKey;
  const wall = node.querySelector(".card-wall");

  if (!payload.results.length) {
    wall.innerHTML = `<div class="empty-state">Bu sorgu için yerel shortlist oluşmadı. Daha geniş veya İngilizce anahtar kelimeler deneyin.</div>`;
  } else {
    wall.innerHTML = payload.results.map(cardMarkup).join("");
  }

  stream.prepend(node);
}

async function submitQuery(event) {
  event.preventDefault();
  const query = document.getElementById("query-input").value.trim();
  const requireApc = document.getElementById("require-apc").checked;
  const maxPayment = Number(document.getElementById("max-payment").value || 0);
  const indexFilter = document.getElementById("index-filter").value;
  const limit = Number(document.getElementById("result-limit").value || 3);
  if (!query) return;

  const button = form.querySelector("button[type='submit']");
  button.disabled = true;
  button.textContent = "Aranıyor...";
  startStatusFlow();

  try {
    const response = await fetch("/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        require_apc: requireApc,
        limit,
        indexes: indexFilter ? [indexFilter] : [],
        max_payment_tl: maxPayment || null,
      }),
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    appendResponseBlock(query, payload);
    finishStatusFlow("done", payload);
  } catch (error) {
    appendResponseBlock(query, {
      query_summary: { result_count: 0, llm: {}, applied_required_terms: [], applied_optional_terms: [], ranking_mode: "strict-required" },
      results: [],
    });
    finishStatusFlow("error");
  } finally {
    button.disabled = false;
    button.textContent = "Uygun dergileri bul";
  }
}

renderPageCredit();
recordVisit();
loadFilterOptions();

function openDrawer(result) {
  drawerContent.innerHTML = drawerMarkup(result);
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
}

form.addEventListener("submit", submitQuery);

stream.addEventListener("click", (event) => {
  const closeTrigger = event.target.closest("[data-close-drawer]");
  if (closeTrigger) {
    closeDrawer();
    return;
  }

  const downloadTrigger = event.target.closest("[data-download-results]");
  if (downloadTrigger) {
    const exportRequest = exportPayloads.get(downloadTrigger.dataset.exportKey || "") || {};
    downloadResultsExcel(exportRequest, downloadTrigger);
    return;
  }

  const card = event.target.closest(".journal-card");
  if (!card) return;
  const result = JSON.parse(decodeURIComponent(card.dataset.result || "%7B%7D"));
  openDrawer(result);
});

drawer.addEventListener("click", (event) => {
  if (event.target.matches("[data-close-drawer]")) {
    closeDrawer();
  }
});
