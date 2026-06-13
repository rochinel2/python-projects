const API_BASE = "/api";
const REFRESH_INTERVAL_MS = 10000;

const elements = {
    apiStatus: document.querySelector("#apiStatus"),
    apiVersion: document.querySelector("#apiVersion"),
    uptime: document.querySelector("#uptime"),
    uptimeSeconds: document.querySelector("#uptimeSeconds"),
    startedAt: document.querySelector("#startedAt"),
    checkedAt: document.querySelector("#checkedAt"),
    refreshInfo: document.querySelector("#refreshInfo"),
    rawJson: document.querySelector("#rawJson"),
    connectionPill: document.querySelector("#connectionPill"),
    connectionText: document.querySelector("#connectionText"),
    refreshButton: document.querySelector("#refreshButton"),
    autoRefresh: document.querySelector("#autoRefresh"),
};

let timerId = null;

function formatDate(value) {
    if (!value) {
        return "-";
    }

    return new Date(value).toLocaleString("pt-BR");
}

function setConnectionState(state, text) {
    elements.connectionPill.classList.remove("ok", "error");
    elements.connectionPill.classList.add(state);
    elements.connectionText.textContent = text;
}

async function fetchJson(path) {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: {
            "Accept": "application/json",
        },
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
}

async function loadStatus() {
    elements.refreshButton.disabled = true;
    elements.refreshButton.textContent = "Atualizando...";

    try {
        const [hello, health] = await Promise.all([
            fetchJson("/hello"),
            fetchJson("/health"),
        ]);

        elements.apiStatus.textContent = health.status || "running";
        elements.apiVersion.textContent = `Versao ${hello.version || "-"}`;
        elements.uptime.textContent = health.uptime || "-";
        elements.uptimeSeconds.textContent = `${health.uptime_seconds ?? "-"} segundos`;
        elements.startedAt.textContent = formatDate(health.started_at);
        elements.checkedAt.textContent = formatDate(health.checked_at);
        elements.refreshInfo.textContent = `Atualizado as ${new Date().toLocaleTimeString("pt-BR")}`;
        elements.rawJson.textContent = JSON.stringify({ hello, health }, null, 2);

        setConnectionState("ok", "Online");
    } catch (error) {
        elements.apiStatus.textContent = "offline";
        elements.apiVersion.textContent = "Versao -";
        elements.uptime.textContent = "-";
        elements.uptimeSeconds.textContent = "- segundos";
        elements.startedAt.textContent = "-";
        elements.checkedAt.textContent = "-";
        elements.refreshInfo.textContent = "Falha na ultima atualizacao";
        elements.rawJson.textContent = JSON.stringify({
            error: "Nao foi possivel consultar a API",
            detail: error.message,
        }, null, 2);

        setConnectionState("error", "Offline");
    } finally {
        elements.refreshButton.disabled = false;
        elements.refreshButton.textContent = "Atualizar agora";
    }
}

function setAutoRefresh(enabled) {
    if (timerId) {
        clearInterval(timerId);
        timerId = null;
    }

    if (enabled) {
        timerId = setInterval(loadStatus, REFRESH_INTERVAL_MS);
    }
}

elements.refreshButton.addEventListener("click", loadStatus);
elements.autoRefresh.addEventListener("change", (event) => {
    setAutoRefresh(event.target.checked);
});

loadStatus();
setAutoRefresh(elements.autoRefresh.checked);
