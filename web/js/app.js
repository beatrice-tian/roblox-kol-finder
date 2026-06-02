import {
  $,
  formatGeneratedAt,
  formatSubscribers,
  formatViews,
  formatDate,
  loadReport,
  setupAvatar,
  sitePath,
} from "./shared.js";

function renderBrief(brief) {
  $("#brief-title").textContent = brief?.title || "本周 Creator Scout Brief";
  const body = $("#brief-body");
  body.innerHTML = "";

  const paragraphs = brief?.paragraphs?.length
    ? brief.paragraphs
    : [brief?.headline, ...(brief?.track_insights || []), brief?.priority_contact].filter(
        Boolean
      );

  paragraphs.forEach((text) => {
    const p = document.createElement("p");
    p.textContent = text;
    body.appendChild(p);
  });

  const footnote = $("#brief-footnote");
  if (brief?.footnote) {
    footnote.textContent = brief.footnote;
    footnote.hidden = false;
  } else {
    footnote.hidden = true;
    footnote.textContent = "";
  }
}

function renderScoutStyle(container, lines) {
  container.innerHTML = "";
  const items = Array.isArray(lines) ? lines : [lines].filter(Boolean);
  if (!items.length) {
    container.textContent = "—";
    return;
  }
  items.forEach((line) => {
    const p = document.createElement("p");
    p.className = "scout-line";
    p.textContent = line;
    container.appendChild(p);
  });
}

function fillCard(card, creator) {
  setupAvatar(card, creator);

  $("[data-name]", card).textContent = creator.name || "—";

  const tierEl = $("[data-tier]", card);
  tierEl.textContent = creator.tier || "—";
  tierEl.dataset.tierLevel = creator.tier || "";

  $("[data-subs]", card).textContent = formatSubscribers(creator.subscribers);

  const verdict =
    creator.recommendation_verdict ||
    creator.recommendation?.slice(0, 120) ||
    "—";
  $("[data-verdict]", card).textContent = verdict;

  renderScoutStyle($("[data-scout]", card), creator.scout_style);

  $("[data-avg-views]", card).textContent = formatViews(creator.avg_views);
  $("[data-engagement]", card).textContent = creator.engagement || "—";
  $("[data-consistency]", card).textContent = creator.consistency || "—";

  const videoLink = $("[data-video-link]", card);
  videoLink.href = creator.video_url || "#";

  const thumb = $("[data-video-thumb]", card);
  if (creator.video_thumbnail) {
    thumb.src = creator.video_thumbnail;
    thumb.alt = creator.video_title || "代表视频";
    thumb.hidden = false;
  } else {
    thumb.hidden = true;
  }

  $("[data-video-title]", card).textContent = creator.video_title || "—";
  const metaParts = [];
  if (creator.video_views) metaParts.push(`${formatViews(creator.video_views)} 播放`);
  if (creator.published_at) metaParts.push(formatDate(creator.published_at));
  $("[data-video-meta]", card).textContent = metaParts.join(" · ") || "—";

  const detailLink = $("[data-detail-link]", card);
  detailLink.href = sitePath(`detail.html?rank=${creator.rank}`);
}

class CardCarousel {
  constructor(trackEl, carouselEl) {
    this.track = trackEl;
    this.carousel = carouselEl;
    this.cards = [];
    this.index = 0;
    this.onScroll = this.onScroll.bind(this);
    this.carousel.addEventListener("scroll", this.onScroll, { passive: true });
  }

  mount(creators) {
    const tpl = $("#card-template");
    this.track.innerHTML = "";
    this.cards = [];

    if (!creators.length) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "暂无 creator 数据，请先运行 pipeline 并生成 report.json";
      this.track.appendChild(empty);
      return;
    }

    creators.forEach((creator) => {
      const node = tpl.content.cloneNode(true);
      const card = node.querySelector(".creator-card");
      fillCard(card, creator);
      this.track.appendChild(node);
      this.cards.push(card);
    });

    requestAnimationFrame(() => this.goTo(0, false));
  }

  onScroll() {
    const w = this.carousel.clientWidth || 1;
    const i = Math.round(this.carousel.scrollLeft / w);
    if (i !== this.index && i >= 0 && i < this.cards.length) {
      this.index = i;
      this.emitChange();
    }
  }

  goTo(index, smooth = true) {
    if (!this.cards.length) return;
    this.index = Math.max(0, Math.min(index, this.cards.length - 1));
    this.cards[this.index].scrollIntoView({
      behavior: smooth ? "smooth" : "auto",
      block: "nearest",
      inline: "center",
    });
    this.emitChange();
  }

  next() {
    this.goTo(this.index + 1);
  }

  prev() {
    this.goTo(this.index - 1);
  }

  onChange(cb) {
    this._onChange = cb;
  }

  emitChange() {
    if (this._onChange) this._onChange(this.index, this.cards.length);
  }
}

function renderProgress(count, activeIndex, onSelect) {
  const wrap = $("#progress");
  wrap.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "progress-dot" + (i === activeIndex ? " is-active" : "");
    dot.setAttribute("aria-label", `第 ${i + 1} 位创作者`);
    dot.addEventListener("click", () => onSelect(i));
    wrap.appendChild(dot);
  }
}

function resetPageScroll() {
  if ("scrollRestoration" in history) {
    history.scrollRestoration = "manual";
  }
  window.scrollTo(0, 0);
}

async function main() {
  resetPageScroll();

  let data;
  try {
    data = await loadReport();
  } catch (err) {
    $("#brief-body").innerHTML =
      `<p class="empty-state">无法加载数据（${err.message}）。请运行：<code>python -m src.web.build</code></p>`;
    return;
  }

  $("#meta-generated").textContent = `更新 ${formatGeneratedAt(data.generated_at)}`;
  renderBrief(data.brief);

  const carousel = new CardCarousel($("#carousel-track"), $("#carousel"));
  carousel.mount(data.creators || []);
  resetPageScroll();
  requestAnimationFrame(resetPageScroll);

  const updateProgress = (index, total) => {
    renderProgress(total, index, (i) => carousel.goTo(i));
  };

  carousel.onChange(updateProgress);
  updateProgress(0, (data.creators || []).length);

  $("#nav-next").addEventListener("click", () => carousel.next());
  $("#nav-prev").addEventListener("click", () => carousel.prev());

  function carouselKeyboardActive() {
    const feed = $("#creators-feed");
    if (!feed) return false;
    const rect = feed.getBoundingClientRect();
    return rect.top < window.innerHeight * 0.5;
  }

  document.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    if (!carouselKeyboardActive() && !e.target.closest("#carousel")) return;
    e.preventDefault();
    if (e.key === "ArrowRight") carousel.next();
    if (e.key === "ArrowLeft") carousel.prev();
  });

  let touchStartX = 0;
  $("#carousel").addEventListener(
    "touchstart",
    (e) => {
      touchStartX = e.changedTouches[0].screenX;
    },
    { passive: true }
  );
  $("#carousel").addEventListener(
    "touchend",
    (e) => {
      const dx = e.changedTouches[0].screenX - touchStartX;
      if (Math.abs(dx) < 48) return;
      if (dx < 0) carousel.next();
      else carousel.prev();
    },
    { passive: true }
  );
}

main();
