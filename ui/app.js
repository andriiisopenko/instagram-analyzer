const views = {
  analysis: document.querySelector("#analysis-view"),
  progress: document.querySelector("#progress-view"),
  results: document.querySelector("#results-view"),
};

const form = document.querySelector("#analysis-form");
const accountSelect = document.querySelector("#account-id");
const accountHelp = document.querySelector("#account-help");
const deleteAccountButton = document.querySelector("#delete-account");
const analyzeButton = document.querySelector("#analyze-button");
const formError = document.querySelector("#form-error");
const progressBar = document.querySelector("#progress-bar");
const progressTrack = document.querySelector(".progress-track");
const progressPercent = document.querySelector("#progress-percent");
const progressMessage = document.querySelector("#progress-message");

let accounts = [];
let currentJobId = null;
let currentResult = null;

function showView(name) {
  Object.entries(views).forEach(([key, element]) => {
    element.hidden = key !== name;
  });
  window.scrollTo({ top: 0, behavior: "auto" });
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch (_) {}
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

async function loadAccounts(selectedId = null) {
  const payload = await api("/api/accounts");
  accounts = payload.accounts;
  accountSelect.replaceChildren();

  if (!accounts.length) {
    accountSelect.append(new Option("No saved accounts", ""));
    accountSelect.disabled = true;
    analyzeButton.disabled = true;
    deleteAccountButton.disabled = true;
    accountHelp.textContent = "Add and authenticate an account once through the CLI, then refresh this page.";
    return;
  }

  accounts.forEach((account) => {
    accountSelect.append(new Option(`@${account.username}`, String(account.id)));
  });
  accountSelect.disabled = false;
  analyzeButton.disabled = false;
  deleteAccountButton.disabled = false;
  const desired = selectedId && accounts.some((account) => account.id === selectedId);
  accountSelect.value = String(desired ? selectedId : accounts[0].id);
  updateAccountHelp();
}

function updateAccountHelp() {
  const selected = accounts.find((account) => String(account.id) === accountSelect.value);
  accountHelp.textContent = selected
    ? `Last used ${formatDate(selected.last_used_at)}`
    : "";
  deleteAccountButton.disabled = !selected;
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function setFormError(message = "") {
  formError.textContent = message;
  formError.hidden = !message;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError();
  analyzeButton.disabled = true;
  const data = new FormData(form);
  try {
    const job = await api("/api/analyses", {
      method: "POST",
      body: JSON.stringify({
        account_id: Number(data.get("account_id")),
        target_username: data.get("target_username"),
        analysis_type: data.get("analysis_type"),
      }),
    });
    currentJobId = job.id;
    showView("progress");
    updateProgress(0, "Waiting to start");
    await pollAnalysis();
  } catch (error) {
    showView("analysis");
    setFormError(error.message);
    analyzeButton.disabled = !accounts.length;
  }
});

async function pollAnalysis() {
  while (currentJobId) {
    const job = await api(`/api/analyses/${currentJobId}`);
    updateProgress(job.progress, job.message);
    if (job.status === "completed") {
      currentResult = job.result;
      renderResults(currentResult);
      showView("results");
      return;
    }
    if (job.status === "failed") throw new Error(job.error || "Analysis failed.");
    await new Promise((resolve) => window.setTimeout(resolve, 900));
  }
}

function updateProgress(percent, message) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  progressBar.style.width = `${value}%`;
  progressPercent.textContent = `${value}%`;
  progressMessage.textContent = message;
  progressTrack.setAttribute("aria-valuenow", String(value));
}

function renderResults(result) {
  document.querySelector("#result-target").textContent = `@${result.target_username}`;
  document.querySelector("#result-meta").textContent = `Authenticated as @${result.authenticated_username} · ${formatDate(result.completed_at)}`;

  const labels = [
    ["following", "Following"],
    ["followers", "Followers"],
    ["total_analyzed", "Total analyzed"],
    ["previously_checked", "Previously checked"],
    ["new", "New"],
  ];
  const statistics = document.querySelector("#statistics");
  statistics.replaceChildren(...labels.map(([key, label]) => {
    const item = document.createElement("div");
    item.className = "stat";
    const value = document.createElement("span");
    value.className = "stat-value";
    value.textContent = result.statistics[key];
    const name = document.createElement("span");
    name.className = "stat-label";
    name.textContent = label;
    item.append(value, name);
    return item;
  }));

  renderAccountList("#all-accounts", result.accounts);
  renderAccountList("#new-accounts", result.new_accounts);
  renderAccountList("#checked-accounts", result.previously_checked_accounts);
  document.querySelector("#all-count").textContent = result.accounts.length;
  document.querySelector("#new-count").textContent = result.new_accounts.length;
  document.querySelector("#checked-count").textContent = result.previously_checked_accounts.length;
}

function renderAccountList(selector, items) {
  const container = document.querySelector(selector);
  container.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "None";
    container.append(empty);
    return;
  }
  items.forEach((account) => {
    const row = document.createElement("div");
    row.className = "account-row";
    const username = document.createElement("span");
    username.textContent = `@${account.username}`;
    row.append(username);
    if (account.previously_checked) {
      const checked = document.createElement("span");
      checked.className = "checked-label";
      checked.textContent = "[checked]";
      row.append(checked);
    }
    container.append(row);
  });
}

accountSelect.addEventListener("change", updateAccountHelp);

deleteAccountButton.addEventListener("click", async () => {
  const account = accounts.find((item) => String(item.id) === accountSelect.value);
  if (!account || !window.confirm(`Remove @${account.username} and its saved session? Analysis history will stay intact.`)) return;
  setFormError();
  deleteAccountButton.disabled = true;
  try {
    await api(`/api/accounts/${account.id}`, { method: "DELETE" });
    await loadAccounts();
  } catch (error) {
    setFormError(error.message);
    deleteAccountButton.disabled = false;
  }
});

document.querySelector("#new-analysis").addEventListener("click", () => {
  currentJobId = null;
  currentResult = null;
  form.reset();
  if (accounts.length) accountSelect.value = String(accounts[0].id);
  updateAccountHelp();
  setFormError();
  analyzeButton.disabled = !accounts.length;
  showView("analysis");
});

document.querySelector("#html-report").addEventListener("click", async () => {
  if (!currentJobId || !currentResult) return;
  const reportWindow = window.open("", "_blank");
  try {
    const report = await api(`/api/analyses/${currentJobId}/html-report`, { method: "POST" });
    if (reportWindow) reportWindow.location = report.download_url;
    else window.location.assign(report.download_url);
  } catch (error) {
    if (reportWindow) reportWindow.close();
    window.alert(error.message);
  }
});

loadAccounts().catch((error) => {
  accountSelect.replaceChildren(new Option("Backend unavailable", ""));
  accountSelect.disabled = true;
  analyzeButton.disabled = true;
  accountHelp.textContent = error.message;
});
