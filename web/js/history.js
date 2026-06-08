import { $, formatReportDate, loadReportsIndex, sitePath } from "./shared.js";

function renderHistoryList(entries) {
  const list = $("#history-list");
  const empty = $("#history-empty");
  list.innerHTML = "";

  if (!entries.length) {
    empty.hidden = false;
    return;
  }

  empty.hidden = true;
  const sorted = [...entries].sort((a, b) => b.date.localeCompare(a.date));

  sorted.forEach((entry) => {
    const item = document.createElement("li");
    item.className = "history-item";

    const date = document.createElement("span");
    date.className = "history-item-date";
    date.textContent = formatReportDate(entry.date);

    const title = document.createElement("span");
    title.className = "history-item-title";
    title.textContent = entry.title || "";

    const link = document.createElement("a");
    link.className = "history-item-link";
    link.href = sitePath(`report.html?date=${entry.date}`);
    link.textContent = "查看报告";

    item.append(date, title, link);
    list.appendChild(item);
  });
}

async function main() {
  try {
    const entries = await loadReportsIndex();
    renderHistoryList(entries);
  } catch (err) {
    $("#history-empty").hidden = false;
    $("#history-empty").textContent = `加载失败：${err.message}`;
  }
}

main();
