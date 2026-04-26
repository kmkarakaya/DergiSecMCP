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

const STATUS_PHASES = [
  {
    title: "Ollama Cloud'a erişiliyor",
    copy: "Türkçe veya karışık sorgu, İngilizce akademik arama terimlerine dönüştürülmek üzere modele gönderiliyor.",
    step: "Ollama erişimi deneniyor",
  },
  {
    title: "Ollama yanıtı bekleniyor",
    copy: "Modelden dönen anahtar kelimeler doğrulanıyor; gerekiyorsa yerel fallback hazır tutuluyor.",
    step: "Ollama geri dönüşü kontrol ediliyor",
  },
  {
    title: "Konu ve anahtar kelimeler çıkarılıyor",
    copy: "Arama terimleri netleştiriliyor ve lokal aday havuzu için uygun hale getiriliyor.",
    step: "Konu ve anahtar kelimeler çıkarılıyor",
  },
  {
    title: "UBYT listesi taranıyor",
    copy: "Lokal veri setinde uygun dergiler eşleştiriliyor ve ilk shortlist çıkartılıyor.",
    step: "UBYT adayları sıralanıyor",
  },
  {
    title: "APC destek kayıtları bağlanıyor",
    copy: "Elsevier ve Wiley kayıtlarıyla destek bilgileri birleştiriliyor.",
    step: "APC destek kayıtları bağlanıyor",
  },
  {
    title: "Kartlar hazırlanıyor",
    copy: "Dergi kapakları, metrikler ve detay panelleri oluşturuluyor.",
    step: "Kart görünümü oluşturuluyor",
  },
];

let statusTimer = null;
let statusPhaseIndex = 0;
let statusDotFrame = 0;

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
    statusTitle.textContent = `Kartlar hazırlanıyor${dots}`;
  }, 1500);
}

function resolvedStatusSteps(payload) {
  const llm = payload?.query_summary?.llm || {};
  const host = llm.host || "https://ollama.com";
  const model = llm.model || "gpt-oss:120b";
  const isCloud = payload?.query_summary?.keyword_source === "ollama-cloud";

  const accessStep = llm.attempted || llm.enabled
    ? `Ollama erişimi: ${host}`
    : "Ollama erişimi atlandı";

  const responseStep = isCloud
    ? `Ollama geri dönüşü alındı: ${model}`
    : "Ollama geri dönüşü kullanılamadı; yerel fallback devrede";

  return [
    accessStep,
    responseStep,
    "Konu ve anahtar kelimeler çıkarılıyor",
    "UBYT adayları sıralanıyor",
    "APC destek kayıtları bağlanıyor",
    "Kart görünümü oluşturuluyor",
  ];
}

function finishStatusFlow(state = "done", payload = null) {
  clearInterval(statusTimer);
  statusPanel.classList.remove("active", "done", "error");
  statusPanel.classList.add(state);

  if (state === "done") {
    const llm = payload?.query_summary?.llm || {};
    statusTitle.textContent = "Sonuçlar hazır";
    statusCopy.textContent = llm.status_text || "Dergi kartları aşağıda oluşturuldu. İsterseniz aynı metni yeni opsiyonlarla tekrar deneyebilirsiniz.";
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