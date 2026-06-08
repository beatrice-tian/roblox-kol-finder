/** 历史报告索引与单期数据（相对模块路径，适配 Vercel 静态根目录） */
export const REPORTS_INDEX_URL = new URL("../data/reports/index.json", import.meta.url).href;
export const LEGACY_REPORT_URL = new URL("../data/report.json", import.meta.url).href;

export function reportDataUrl(date) {
  return new URL(`../data/reports/${date}.json`, import.meta.url).href;
}

export const $ = (sel, root = document) => root.querySelector(sel);

export function formatSubscribers(value) {
  const n = Number(String(value).replace(/,/g, ""));
  if (!n || Number.isNaN(n)) return "—";

  if (n >= 100_000_000) {
    const yi = n / 100_000_000;
    const num = yi >= 10 ? yi.toFixed(0) : yi.toFixed(1).replace(/\.0$/, "");
    return `${num}亿粉丝`;
  }
  if (n >= 10_000) {
    const wan = n / 10_000;
    const num = wan >= 100 ? wan.toFixed(0) : wan.toFixed(1).replace(/\.0$/, "");
    return `${num}万粉丝`;
  }
  if (n >= 1_000) {
    const qian = n / 1_000;
    const num = qian >= 10 ? qian.toFixed(0) : qian.toFixed(1).replace(/\.0$/, "");
    return `${num}千粉丝`;
  }
  return `${n}粉丝`;
}

export function formatViews(value) {
  if (value == null || value === "") return "—";
  const n = Number(String(value).replace(/,/g, ""));
  if (Number.isNaN(n)) return String(value);
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

export function formatDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function formatGeneratedAt(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function avatarGradient(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  const hues = [235, 260, 200, 170, 310];
  const h = hues[Math.abs(hash) % hues.length];
  return `linear-gradient(135deg, hsl(${h} 55% 52%), hsl(${h + 24} 50% 62%))`;
}

export function initials(name) {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

export function setChannelLinks(root, url) {
  const href = url || "#";
  root.querySelectorAll(".channel-link").forEach((el) => {
    el.href = href;
  });
}

export function setupAvatar(root, creator) {
  const img = $("[data-avatar-img]", root);
  const fallback = $("[data-avatar-fallback]", root);
  const name = creator.name || "creator";

  fallback.textContent = initials(name);
  fallback.style.background = avatarGradient(name);
  if (img) img.alt = `${name} 头像`;

  if (creator.avatar_url && img) {
    img.src = creator.avatar_url;
    img.hidden = false;
    fallback.hidden = true;
    img.onerror = () => {
      img.hidden = true;
      fallback.hidden = false;
    };
  } else if (img) {
    img.hidden = true;
    fallback.hidden = false;
  }

  setChannelLinks(root, creator.channel_url);
}

export function parseRecommendationSections(text) {
  if (!text?.trim()) return [];

  let body = text.replace(/\|/g, "｜").trim();
  body = body.replace(/^值得关注[｜|]\s*/, "");

  const pipeChunks = body.split("｜").map((s) => s.trim()).filter(Boolean);
  if (pipeChunks.length > 1) {
    body = pipeChunks.join(" ");
  }

  const sections = [];
  const labels = ["玩家群体", "适合游戏", "潜力判断"];

  const push = (label, content) => {
    const b = content?.trim();
    if (b) sections.push({ label: label || "", body: b });
  };

  while (body.length) {
    let hit = null;
    for (const label of labels) {
      const idx = body.indexOf(` ${label}`);
      if (idx >= 0 && (hit === null || idx < hit.idx)) {
        hit = { idx, label };
      }
    }

    if (!hit) {
      const lead = body.match(/^(玩家群体|适合游戏|潜力判断)\s+([\s\S]+)/);
      if (lead) push(lead[1], lead[2]);
      else push("", body);
      break;
    }

    if (hit.idx > 0) push("", body.slice(0, hit.idx));

    body = body.slice(hit.idx).trim();
    if (body.startsWith(hit.label)) {
      body = body.slice(hit.label.length).trim();
    }

    let nextIdx = body.length;
    for (const label of labels) {
      const idx = body.indexOf(` ${label}`);
      if (idx > 0 && idx < nextIdx) nextIdx = idx;
    }

    push(hit.label, body.slice(0, nextIdx));
    body = body.slice(nextIdx).trim();
  }

  return sections;
}

export function renderFullRecommendation(container, text) {
  container.innerHTML = "";
  const sections = parseRecommendationSections(text);

  if (!sections.length) {
    const p = document.createElement("p");
    p.className = "detail-paragraph";
    p.textContent = text || "—";
    container.appendChild(p);
    return;
  }

  sections.forEach(({ label, body }) => {
    const block = document.createElement("div");
    block.className = "detail-rec-block";
    if (label) {
      const tag = document.createElement("span");
      tag.className = "detail-rec-label";
      tag.textContent = label;
      block.appendChild(tag);
    }
    const p = document.createElement("p");
    p.className = "detail-paragraph";
    p.textContent = body;
    block.appendChild(p);
    container.appendChild(block);
  });
}

async function fetchJson(url, label) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`无法加载 ${label}（${res.status} ${res.statusText}）`);
  }
  return res.json();
}

export async function loadReportsIndex() {
  try {
    return await fetchJson(REPORTS_INDEX_URL, "历史报告索引");
  } catch {
    return [];
  }
}

export async function loadReportByDate(date) {
  if (!date) {
    throw new Error("缺少报告日期");
  }
  return fetchJson(reportDataUrl(date), `${date} 报告`);
}

async function loadLegacyReport() {
  return fetchJson(
    LEGACY_REPORT_URL,
    "旧版 report.json（请运行 python -m src.web.build 生成历史归档）"
  );
}

/** @param {{ date?: string | null }} [options] 不传 date 时加载 index 中最新一期 */
export async function loadReport(options = {}) {
  const { date } = options;
  if (date) {
    return loadReportByDate(date);
  }

  const index = await loadReportsIndex();
  if (index.length) {
    const latest = [...index].sort((a, b) => b.date.localeCompare(a.date))[0];
    return loadReportByDate(latest.date);
  }

  return loadLegacyReport();
}

export function formatReportDate(date) {
  if (!date) return "—";
  try {
    const [y, m, d] = date.split("-").map(Number);
    const dt = new Date(y, m - 1, d);
    return dt.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return date;
  }
}

/** 站内根路径，避免在 /detail.html 下使用相对路径导致 404 */
export function sitePath(path) {
  return path.startsWith("/") ? path : `/${path}`;
}

export function findCreatorByRank(creators, rank) {
  const n = Number(rank);
  return creators.find((c) => c.rank === n) || null;
}
