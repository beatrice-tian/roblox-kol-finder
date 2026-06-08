import {
  $,
  findCreatorByRank,
  formatViews,
  formatDate,
  loadReport,
  renderFullRecommendation,
  setupAvatar,
  sitePath,
} from "./shared.js";

function renderStats(container, creator) {
  const items = [
    ["潜力等级", creator.tier],
    ["榜单分层", creator.list_tier],
    ["粉丝数", creator.subscribers],
    ["平均播放", formatViews(creator.avg_views)],
    ["互动率", creator.engagement],
    ["稳定度", creator.consistency],
    ["爆款记录", creator.viral_hit || "—"],
    ["Shorts占比", creator.shorts || "—"],
    ["潜力分", creator.potential_score],
  ];

  container.innerHTML = items
    .map(
      ([label, value]) =>
        `<div class="detail-stat"><span class="detail-stat-label">${label}</span><span class="detail-stat-value">${value ?? "—"}</span></div>`
    )
    .join("");
}

async function main() {
  const params = new URLSearchParams(window.location.search);
  const rank = params.get("rank");
  const reportDate = params.get("date");

  if (!rank) {
    $("#detail-empty").hidden = false;
    $("#detail-empty").textContent = "缺少 rank 参数";
    return;
  }

  let data;
  try {
    data = await loadReport({ date: reportDate || null });
  } catch (err) {
    $("#detail-empty").hidden = false;
    $("#detail-empty").textContent = `加载失败：${err.message}`;
    return;
  }

  const creator = findCreatorByRank(data.creators || [], rank);
  if (!creator) {
    $("#detail-empty").hidden = false;
    return;
  }

  const backLink = $(".back-link");
  if (reportDate) {
    backLink.href = sitePath(`report.html?date=${reportDate}`);
    backLink.textContent = "← 返回该期报告";
  } else {
    backLink.href = sitePath("/");
    backLink.textContent = "← 返回情报流";
  }

  const root = $("#detail-root");
  root.hidden = false;

  document.title = `${creator.name} · 完整分析`;

  setupAvatar(root, creator);
  $("[data-name]", root).textContent = creator.name;
  $("[data-sub]", root).textContent = [
    `潜力 ${creator.tier}`,
    creator.list_tier,
    creator.subscribers ? `${creator.subscribers} 粉丝` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  renderFullRecommendation($("#detail-recommendation"), creator.recommendation);
  $("[data-scout-raw]", root).textContent = creator.scout_note || "—";
  $("[data-highlight]", root).textContent = creator.highlight || "—";
  renderStats($("[data-stats]", root), creator);

  const videoLink = $("[data-video-link]", root);
  videoLink.href = creator.video_url || "#";
  const thumb = $("[data-video-thumb]", root);
  if (creator.video_thumbnail) {
    thumb.src = creator.video_thumbnail;
    thumb.alt = creator.video_title || "";
  }
  $("[data-video-title]", root).textContent = creator.video_title || "—";
  const meta = [];
  if (creator.video_views) meta.push(`${formatViews(creator.video_views)} 播放`);
  if (creator.published_at) meta.push(formatDate(creator.published_at));
  $("[data-video-meta]", root).textContent = meta.join(" · ");

  $("[data-signal]", root).textContent = creator.signal || "";
}

main();
