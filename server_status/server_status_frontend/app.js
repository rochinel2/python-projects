const API_BASE = "/api";
const REFRESH_INTERVAL_MS = 10000;
const THEME_STORAGE_KEY = "server-status-theme";

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
    themeButton: document.querySelector("#themeButton"),
    themeIcon: document.querySelector("#themeIcon"),
    themeText: document.querySelector("#themeText"),
    apiTab: document.querySelector("#apiTab"),
    serverTab: document.querySelector("#serverTab"),
    apiView: document.querySelector("#apiView"),
    serverView: document.querySelector("#serverView"),
    serverHostname: document.querySelector("#serverHostname"),
    serverSystem: document.querySelector("#serverSystem"),
    serverUptime: document.querySelector("#serverUptime"),
    serverBoot: document.querySelector("#serverBoot"),
    serverMemory: document.querySelector("#serverMemory"),
    serverMemoryDetail: document.querySelector("#serverMemoryDetail"),
    serverCpuCores: document.querySelector("#serverCpuCores"),
    serverCpuModel: document.querySelector("#serverCpuModel"),
    serverLoad: document.querySelector("#serverLoad"),
    serverDiskRows: document.querySelector("#serverDiskRows"),
    serverDmesg: document.querySelector("#serverDmesg"),
};

let timerId = null;
let currentTheme = "light";
let activeView = "api";
let lastApiPayload = {};
let lastServerPayload = {};

function getInitialTheme() {
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);

    if (savedTheme === "light" || savedTheme === "dark") {
        return savedTheme;
    }

    if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
        return "dark";
    }

    return "light";
}

function applyTheme(theme) {
    currentTheme = theme;
    document.body.classList.toggle("dark-theme", theme === "dark");

    if (theme === "dark") {
        elements.themeIcon.textContent = "Sol";
        elements.themeText.textContent = "Claro";
        elements.themeButton.setAttribute("aria-label", "Ativar tema claro");
        return;
    }

    elements.themeIcon.textContent = "Lua";
    elements.themeText.textContent = "Escuro";
    elements.themeButton.setAttribute("aria-label", "Ativar tema escuro");
}

function toggleTheme() {
    const nextTheme = currentTheme === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    applyTheme(nextTheme);
}

function formatDate(value) {
    if (!value) {
        return "-";
    }

    return new Date(value).toLocaleString("pt-BR");
}

function formatGb(value) {
    if (value === null || value === undefined) {
        return "-";
    }

    return `${value} GB`;
}

function setRawJson() {
    if (activeView === "server") {
        elements.rawJson.textContent = JSON.stringify(lastServerPayload, null, 2);
        return;
    }

    elements.rawJson.textContent = JSON.stringify(lastApiPayload, null, 2);
}

function switchView(view) {
    activeView = view;
    elements.apiTab.classList.toggle("active", view === "api");
    elements.serverTab.classList.toggle("active", view === "server");
    elements.apiView.classList.toggle("active", view === "api");
    elements.serverView.classList.toggle("active", view === "server");
    setRawJson();
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

async function loadApiStatus() {
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

    lastApiPayload = { hello, health };
}

function updateDiskRows(items) {
    elements.serverDiskRows.innerHTML = "";

    if (!items || items.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.textContent = "Nenhum disco retornado";
        row.appendChild(cell);
        elements.serverDiskRows.appendChild(row);
        return;
    }

    for (const item of items) {
        const row = document.createElement("tr");
        const values = [
            item.mountpoint || item.filesystem || "-",
            formatGb(item.used_gb),
            formatGb(item.available_gb),
            item.used_percent || "-",
        ];

        for (const value of values) {
            const cell = document.createElement("td");
            cell.textContent = value;
            row.appendChild(cell);
        }

        elements.serverDiskRows.appendChild(row);
    }
}

async function loadServerStatus() {
    const server = await fetchJson("/server/status");
    const memory = server.memory || {};
    const cpu = server.cpu || {};
    const boot = server.boot || {};
    const system = server.system || {};
    const load = cpu.load_average || {};

    elements.serverHostname.textContent = server.hostname || "-";
    elements.serverSystem.textContent = `${system.name || "-"} ${system.release || ""}`.trim();
    elements.serverUptime.textContent = boot.uptime || "-";
    elements.serverBoot.textContent = `Inicializado em ${formatDate(boot.started_at)}`;
    elements.serverMemory.textContent = memory.used_percent !== null && memory.used_percent !== undefined
        ? `${memory.used_percent}% em uso`
        : "-";
    elements.serverMemoryDetail.textContent = `${formatGb(memory.used_gb)} usados de ${formatGb(memory.total_gb)}`;
    elements.serverCpuCores.textContent = `${cpu.cores || "-"} core(s)`;
    elements.serverCpuModel.textContent = cpu.model || "-";
    elements.serverLoad.textContent = `Load average: ${load["1m"] ?? "-"} / ${load["5m"] ?? "-"} / ${load["15m"] ?? "-"}`;
    elements.serverDmesg.textContent = server.dmesg?.lines?.length
        ? server.dmesg.lines.join("\n")
        : (server.dmesg?.error || "Nenhuma mensagem retornada");

    updateDiskRows(server.disk?.items);
    lastServerPayload = server;
}

async function loadStatus() {
    elements.refreshButton.disabled = true;
    elements.refreshButton.textContent = "Atualizando...";

    try {
        await Promise.all([
            loadApiStatus(),
            loadServerStatus(),
        ]);
        setRawJson();

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
elements.themeButton.addEventListener("click", toggleTheme);
elements.apiTab.addEventListener("click", () => switchView("api"));
elements.serverTab.addEventListener("click", () => switchView("server"));

applyTheme(getInitialTheme());
switchView("api");
loadStatus();
setAutoRefresh(elements.autoRefresh.checked);
