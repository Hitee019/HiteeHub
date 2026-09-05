const SAMPLE_TRANSACTIONS = [
  { merchant: "NETFLIX.COM 8552654578 CA", amount: 15.49, date: "2026-01-05" },
  { merchant: "NETFLIX.COM 8552654578 CA", amount: 15.49, date: "2026-02-05" },
  { merchant: "NETFLIX.COM 8552654578 CA", amount: 15.49, date: "2026-03-06" },
  { merchant: "NETFLIX.COM 8552654578 CA", amount: 15.49, date: "2026-04-05" },
  { merchant: "SPOTIFY USA", amount: 11.99, date: "2026-01-12" },
  { merchant: "SPOTIFY USA", amount: 11.99, date: "2026-02-12" },
  { merchant: "SPOTIFY USA", amount: 11.99, date: "2026-03-13" },
  { merchant: "SPOTIFY USA", amount: 11.99, date: "2026-04-12" },
  { merchant: "PLANET FITNESS", amount: 24.99, date: "2026-01-01" },
  { merchant: "PLANET FITNESS", amount: 24.99, date: "2026-02-01" },
  { merchant: "PLANET FITNESS", amount: 24.99, date: "2026-03-01" },
  { merchant: "PLANET FITNESS", amount: 24.99, date: "2026-04-01" },
  { merchant: "PLANET FITNESS", amount: 24.99, date: "2026-05-01" },
  { merchant: "STARBUCKS #4521", amount: 6.75, date: "2026-01-03" },
  { merchant: "STARBUCKS #8832", amount: 5.25, date: "2026-01-20" },
];

const $ = (selector) => document.querySelector(selector);
const jsonInput = $("#jsonInput");
const inputStatus = $("#inputStatus");
const detectButton = $("#detectButton");
const dropZone = $("#dropZone");
const fileInput = $("#fileInput");

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatCharge(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(value);
}

function setInputStatus(text, isError = false) {
  inputStatus.textContent = text;
  inputStatus.classList.toggle("error-text", isError);
}

function parseInput() {
  const parsed = JSON.parse(jsonInput.value);
  if (!Array.isArray(parsed)) throw new Error("JSON must be an array of transactions.");
  if (!parsed.length) throw new Error("Add at least one transaction.");
  return parsed;
}

function setLoading(isLoading) {
  $("#emptyState").classList.toggle("hidden", isLoading);
  $("#loadingState").classList.toggle("hidden", !isLoading);
  $("#results").classList.add("hidden");
  detectButton.disabled = isLoading;
  detectButton.innerHTML = isLoading ? "Analyzing <span>…</span>" : "Detect subscriptions <span>→</span>";
}

function renderResults(data) {
  const subscriptions = data.subscriptions;
  const annualTotal = subscriptions.reduce((sum, item) => sum + item.annualized_cost, 0);
  $("#annualTotal").textContent = formatMoney(annualTotal);
  $("#monthlyTotal").textContent = formatMoney(annualTotal / 12);
  $("#subscriptionTotal").textContent = subscriptions.length;
  $("#resultCount").textContent = `${subscriptions.length} found`;
  $("#emptyState").classList.add("hidden");
  $("#loadingState").classList.add("hidden");
  $("#results").classList.remove("hidden");

  const list = $("#subscriptionList");
  if (!subscriptions.length) {
    list.innerHTML = `<div class="no-results"><span>◌</span><strong>No stable recurring patterns</strong><p>Try adding more history — three or more similar charges make a stronger signal.</p></div>`;
    return;
  }
  list.innerHTML = subscriptions.map((subscription, index) => {
    const confidence = Math.round(subscription.confidence * 100);
    const dates = subscription.occurrences.map((item) => new Date(`${item.date}T12:00:00`))
      .sort((a, b) => a - b);
    const lastDate = dates[dates.length - 1]?.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    return `
      <article class="subscription-row" style="--delay: ${index * 60}ms">
        <div class="merchant-avatar">${subscription.merchant.charAt(0)}</div>
        <div class="subscription-main">
          <div class="subscription-title"><h3>${escapeHtml(subscription.merchant)}</h3><span class="confidence">${confidence}% match</span></div>
          <div class="subscription-meta"><span>${subscription.frequency}</span><span>·</span><span>${subscription.occurrences.length} charges</span><span>·</span><span>last ${lastDate}</span></div>
        </div>
        <div class="subscription-cost"><strong>${formatCharge(subscription.typical_amount)}</strong><span>${formatMoney(subscription.annualized_cost)} / yr</span></div>
        <button class="detail-button" type="button" aria-label="Show transaction history for ${escapeHtml(subscription.merchant)}" data-index="${index}">+</button>
        <div class="history" data-history="${index}">
          <div class="history-header"><span>TRANSACTION HISTORY</span><span>AMOUNT</span></div>
          ${subscription.occurrences.map((occurrence) => `<div class="history-row"><span>${new Date(`${occurrence.date}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span><strong>${formatCharge(occurrence.amount)}</strong></div>`).join("")}
        </div>
      </article>`;
  }).join("");

  list.querySelectorAll(".detail-button").forEach((button) => {
    button.addEventListener("click", () => {
      const history = list.querySelector(`[data-history="${button.dataset.index}"]`);
      history.classList.toggle("open");
      button.textContent = history.classList.contains("open") ? "−" : "+";
    });
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[character]));
}

async function detect() {
  let transactions;
  try {
    transactions = parseInput();
  } catch (error) {
    setInputStatus(error.message, true);
    jsonInput.focus();
    return;
  }
  setInputStatus(`${transactions.length} transactions ready`);
  setLoading(true);
  try {
    const response = await fetch("/api/detect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transactions }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not analyze transactions.");
    renderResults(data);
  } catch (error) {
    $("#loadingState").classList.add("hidden");
    $("#emptyState").classList.remove("hidden");
    setInputStatus(error.message, true);
  } finally {
    detectButton.disabled = false;
    detectButton.innerHTML = "Detect subscriptions <span>→</span>";
  }
}

$("#sampleButton").addEventListener("click", () => {
  jsonInput.value = JSON.stringify(SAMPLE_TRANSACTIONS, null, 2);
  setInputStatus(`${SAMPLE_TRANSACTIONS.length} transactions ready`);
  detect();
});

detectButton.addEventListener("click", detect);

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) readCsv(file);
});

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") fileInput.click();
});
["dragenter", "dragover"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.add("dragging");
}));
["dragleave", "drop"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragging");
}));
dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file) readCsv(file);
});

function readCsv(file) {
  const reader = new FileReader();
  reader.onload = () => {
    const rows = parseCsv(String(reader.result));
    if (rows.length < 2) {
      setInputStatus("CSV needs a header and at least one row", true);
      return;
    }
    const headers = rows.shift().map((header) => header.trim().toLowerCase());
    const merchantIndex = headers.indexOf("merchant") >= 0 ? headers.indexOf("merchant") : headers.indexOf("merchant_name");
    const dateIndex = headers.indexOf("date") >= 0 ? headers.indexOf("date") : headers.indexOf("txn_date");
    const amountIndex = headers.indexOf("amount");
    if (merchantIndex < 0 || dateIndex < 0 || amountIndex < 0) {
      setInputStatus("CSV needs merchant, amount, and date columns", true);
      return;
    }
    const transactions = rows.filter((values) => values.some(Boolean)).map((values) => {
      return { merchant: values[merchantIndex]?.trim(), amount: Number(values[amountIndex]), date: values[dateIndex]?.trim() };
    });
    jsonInput.value = JSON.stringify(transactions, null, 2);
    setInputStatus(`${transactions.length} transactions loaded from ${file.name}`);
  };
  reader.readAsText(file);
}

function parseCsv(contents) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < contents.length; index += 1) {
    const character = contents[index];
    const next = contents[index + 1];
    if (character === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (character === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && next === "\n") index += 1;
      row.push(cell);
      if (row.some((value) => value.trim())) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += character;
    }
  }
  if (cell || row.length) {
    row.push(cell);
    if (row.some((value) => value.trim())) rows.push(row);
  }
  return rows;
}