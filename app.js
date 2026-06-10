const statusPill = document.getElementById("status-pill");
const runTime = document.getElementById("run-time");
const edition = document.getElementById("edition");
const resultTitle = document.getElementById("result-title");
const resultDetail = document.getElementById("result-detail");
const logOutput = document.getElementById("log-output");
const summaryLine = document.getElementById("summary-line");
const body = document.body;

function setState(state) {
  body.classList.remove("state-ok", "state-alert", "state-offline", "state-idle");
  statusPill.className = "pill";

  if (state === "ok") {
    body.classList.add("state-ok");
    statusPill.classList.add("pill-ok");
    statusPill.textContent = "resultado encontrado";
    return;
  }

  if (state === "idle") {
    body.classList.add("state-idle");
    statusPill.classList.add("pill-waiting");
    statusPill.textContent = "monitor ativo";
    return;
  }

  if (state === "alert") {
    body.classList.add("state-alert");
    statusPill.classList.add("pill-alert");
    statusPill.textContent = "sistema indisponivel";
    return;
  }

  body.classList.add("state-offline");
  statusPill.classList.add("pill-offline");
  statusPill.textContent = "fora do ar";
}

function formatDate(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function keywordSummary(status) {
  if (!status) return "Sem dados de leitura.";
  const parts = [];
  if (typeof status.has_agente === "boolean") {
    parts.push(`agente de farmacia: ${status.has_agente ? "sim" : "nao"}`);
  }
  if (typeof status.has_concurso === "boolean") {
    parts.push(`concurso: ${status.has_concurso ? "sim" : "nao"}`);
  }
  if (typeof status.has_processo === "boolean") {
    parts.push(`processo seletivo: ${status.has_processo ? "sim" : "nao"}`);
  }
  return parts.join(" | ");
}

function buildLogPreview(logText) {
  if (!logText) return "Nenhum log disponível.";

  const lines = logText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const tail = lines.slice(-12);
  return tail.length ? tail.join("\n") : "Nenhum log disponível.";
}

async function loadText(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Falha ao carregar ${path}`);
  }
  return response.text();
}

function inferStateFromLog(logText, statusText) {
  const haystack = `${logText}\n${statusText}`.toLowerCase();
  if (haystack.includes("indisponivel") || haystack.includes("erro critico")) {
    return "alert";
  }
  if (haystack.includes("resultado encontrado") || haystack.includes("nova publicacao relevante")) {
    return "ok";
  }
  if (
    haystack.includes("ultima edicao carregada") ||
    haystack.includes("nenhuma novidade relevante") ||
    haystack.includes("estado inicial gravado")
  ) {
    return "idle";
  }
  return "alert";
}

async function init() {
  try {
    const [statusText, logText] = await Promise.all([
      loadText("ultimo_status.txt"),
      loadText("registro"),
    ]);

    const status = JSON.parse(statusText);
    const state = inferStateFromLog(logText, statusText);
    setState(state);

    runTime.textContent = formatDate(status.updated_at);
    edition.textContent = status.edition || "Última edição não informada.";
    resultTitle.textContent =
      state === "ok"
        ? "Resultado encontrado"
        : state === "alert"
          ? "Sistema indisponível"
          : "Monitor ativo";
    resultDetail.textContent =
      state === "ok"
        ? keywordSummary(status)
        : state === "alert"
          ? "Falha no acesso ao diário ou leitura interrompida."
          : "Leitura concluída sem nova publicação relevante.";
    logOutput.textContent = buildLogPreview(logText);
    summaryLine.textContent = `Fonte: ${status.source || "não informada"} • Atualizado em ${formatDate(status.updated_at)}`;
  } catch (error) {
    setState("alert");
    runTime.textContent = "--";
    edition.textContent = "Não foi possível carregar os dados publicados.";
    resultTitle.textContent = "Sistema indisponível";
    resultDetail.textContent = "A página não conseguiu ler `ultimo_status.txt` ou `registro`.";
    logOutput.textContent = String(error?.message || error);
    summaryLine.textContent = "Dados não carregados.";
  }
}

init();
