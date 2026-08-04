(() => {
  const listEl = document.querySelector("[data-news-list]");
  const metaEl = document.querySelector("[data-news-updated]");
  if (!listEl) return;

  const limitAttr = listEl.getAttribute("data-limit");
  const limit = limitAttr ? Number(limitAttr) : null;

  function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function formatUpdated(iso) {
    if (!iso) return "最終更新日：未取得";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return `最終更新日：${iso}`;
    return `最終更新日：${d.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" })}（JST）`;
  }

  fetch("data/news.json", { cache: "no-store" })
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((payload) => {
      if (metaEl) metaEl.textContent = formatUpdated(payload.updatedAt);
      const items = Array.isArray(payload.items) ? payload.items : [];
      const shown = limit ? items.slice(0, limit) : items;
      if (!shown.length) {
        listEl.innerHTML = '<li class="empty">いま表示できる情報がありません。収集が走り次第、ここに並びます。</li>';
        return;
      }
      listEl.innerHTML = shown
        .map((it) => {
          const when = formatDate(it.startsAt || it.fetchedAt);
          const summary = it.summary
            ? `<p class="news-summary">${escapeHtml(it.summary)}</p>`
            : "";
          return `<li>
            <span class="news-source">${escapeHtml(it.source || "")}</span>
            <a class="title" href="${escapeAttr(it.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(it.title)}</a>
            ${summary}
            <div class="news-date">${escapeHtml(when)}</div>
          </li>`;
        })
        .join("");
    })
    .catch(() => {
      if (metaEl) metaEl.textContent = "最終更新日：取得に失敗しました";
      listEl.innerHTML =
        '<li class="empty">最新情報の読み込みに失敗しました。しばらくしてから再度お試しください。</li>';
    });

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }
})();
