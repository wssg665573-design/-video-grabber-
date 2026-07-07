// VideoGrab 前端逻辑（原生 JS，零依赖）
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const state = {
    platforms: [],
    results: [],
    selected: new Set(),
    busy: false,
  };

  const fmt = {
    size(bytes) {
      if (!bytes && bytes !== 0) return "未知大小";
      const units = ["B", "KB", "MB", "GB"];
      let i = 0, n = bytes;
      while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
      return n.toFixed(n >= 10 || i === 0 ? 0 : 1) + " " + units[i];
    },
    duration(seconds) {
      if (!seconds && seconds !== 0) return "";
      const m = Math.floor(seconds / 60), s = Math.floor(seconds % 60);
      return `${m}:${s.toString().padStart(2, "0")}`;
    },
    short(text, max) {
      max = max || 80;
      if (!text) return "";
      return text.length > max ? text.slice(0, max) + "…" : text;
    },
  };

  function toast(message, kind) {
    kind = kind || "info";
    const palette = { info: "bg-ink-700 text-white", success: "bg-emerald-500 text-white", error: "bg-rose-500 text-white" };
    const node = document.createElement("div");
    node.className = `toast px-4 py-2 rounded-xl shadow-2xl shadow-black/40 ${palette[kind] || palette.info}`;
    node.textContent = message;
    $("#toast").appendChild(node);
    setTimeout(() => { node.style.opacity = "0"; node.style.transition = "opacity .3s"; }, 2400);
    setTimeout(() => node.remove(), 2800);
  }

  async function api(path, options) {
    const resp = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, options || {}));
    if (!resp.ok) {
      let detail = resp.status + " " + resp.statusText;
      try { const j = await resp.json(); if (j.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch (_) {}
      throw new Error(detail);
    }
    return resp;
  }

  async function loadPlatforms() {
    try {
      const resp = await api("/api/platforms");
      state.platforms = await resp.json();
      renderPlatforms();
    } catch (e) {
      $("#api-status").className = "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-500/10 text-rose-300";
      $("#api-status").innerHTML = "<span class=\"w-1.5 h-1.5 rounded-full bg-rose-400\"></span> 服务异常";
    }
  }

  function renderPlatforms() {
    const host = $("#platforms");
    host.innerHTML = "";
    state.platforms.forEach((p) => {
      const card = document.createElement("div");
      card.className = "card border border-white/5 bg-ink-800/50 rounded-xl p-3 flex items-center gap-3";
      card.innerHTML = `
        <div class="w-9 h-9 rounded-lg grid place-items-center text-lg" style="background:${p.color}22;color:${p.color}">${p.icon}</div>
        <div>
          <div class="text-sm text-white font-medium">${p.name}</div>
          <div class="text-xs text-ink-400">${p.id}</div>
        </div>`;
      host.appendChild(card);
    });
  }

  function updateCounter() {
    const urls = $("#url-input").value.split(/\s+/).filter(Boolean);
    $("#counter").textContent = `${urls.length} / 20`;
    $("#counter").classList.toggle("text-rose-400", urls.length > 20);
  }

  function renderResults() {
    const host = $("#results");
    host.innerHTML = "";
    if (!state.results.length) { host.classList.add("hidden"); return; }
    host.classList.remove("hidden");
    state.results.forEach((item, idx) => {
      const platform = state.platforms.find((p) => p.id === item.platform) || state.platforms[state.platforms.length - 1];
      const isWide = item.width && item.height && item.width > item.height;
      const card = document.createElement("div");
      card.className = "card bg-ink-800/60 border border-white/5 rounded-2xl overflow-hidden flex flex-col";
      const cover = item.cover || item.thumbnail;
      const errorBox = item.ok ? "" : `<div class=\"p-4 text-rose-300 text-sm\">⚠️ ${item.error || "解析失败"}</div>`;
      const coverBox = cover
        ? `<div class=\"relative\"><img src=\"${cover}\" alt=\"\" class=\"${isWide ? "video-thumb-wide" : "video-thumb"}\" referrerpolicy=\"no-referrer\" />${item.duration ? `<span class=\"absolute bottom-2 right-2 px-2 py-0.5 rounded-md bg-black/70 text-white text-xs\">${fmt.duration(item.duration)}</span>` : ""}</div>`
        : `<div class=\"skeleton ${isWide ? "video-thumb-wide" : "video-thumb"}\"></div>`;
      const actionBtn = item.ok
        ? `<button data-action=\"download\" data-idx=\"${idx}\" class=\"flex-1 px-3 py-2 rounded-lg bg-brand-500 hover:bg-brand-400 text-white text-sm font-medium\">下载</button>`
        : `<button data-action=\"retry\" data-idx=\"${idx}\" class=\"flex-1 px-3 py-2 rounded-lg bg-ink-700 hover:bg-ink-600 text-white text-sm font-medium\">重试</button>`;
      card.innerHTML = `
        ${coverBox}
        <div class=\"p-4 flex-1 flex flex-col gap-2\">
          <div class=\"flex items-center gap-2 text-xs\">
            <span class=\"badge-dot\" style=\"background:${platform.color}\"></span>
            <span class=\"text-ink-300\">${platform.name}</span>
            <span class=\"text-ink-500\">·</span>
            <span class=\"text-ink-400 truncate\">${item.author || ""}</span>
          </div>
          <div class=\"text-sm text-white font-medium line-clamp-2\">${fmt.short(item.title, 60) || "无标题"}</div>
          <div class=\"text-xs text-ink-400\">${fmt.size(item.size)} ${item.width ? "· " + item.width + "x" + item.height : ""}</div>
          ${errorBox}
          <div class=\"mt-auto pt-2 flex items-center gap-2\">
            <label class=\"inline-flex items-center gap-1 text-xs text-ink-400 cursor-pointer\">
              <input type=\"checkbox\" data-idx=\"${idx}\" class=\"select-item accent-brand-500\" ${state.selected.has(idx) ? "checked" : ""} />选中
            </label>
            ${actionBtn}
            <button data-action=\"copy\" data-idx=\"${idx}\" class=\"px-3 py-2 rounded-lg border border-white/10 hover:border-white/30 text-ink-300 text-sm\">复制链接</button>
          </div>
        </div>`;
      host.appendChild(card);
    });
    updateBatchBar();
  }

  function updateBatchBar() {
    const bar = $("#batch-bar");
    const okCount = state.results.filter((r) => r.ok).length;
    if (state.selected.size > 0 && okCount > 0) {
      bar.classList.remove("hidden");
      $("#selected-count").textContent = String(state.selected.size);
    } else {
      bar.classList.add("hidden");
    }
  }

  async function parse() {
    if (state.busy) return;
    const urls = $("#url-input").value.split(/\s+/).filter(Boolean);
    if (!urls.length) { toast("请先粘贴链接", "error"); return; }
    if (urls.length > 20) { toast("单次最多 20 条链接", "error"); return; }
    state.busy = true;
    state.selected.clear();
    const btn = $("#btn-parse");
    btn.disabled = true;
    btn.classList.add("opacity-60");
    $("#results").innerHTML = "";
    Array.from({ length: urls.length }).forEach(() => {
      const sk = document.createElement("div");
      sk.className = "card bg-ink-800/60 border border-white/5 rounded-2xl overflow-hidden";
      sk.innerHTML = `<div class=\"skeleton video-thumb\"></div><div class=\"p-4 space-y-2\"><div class=\"skeleton h-3 rounded w-1/3\"></div><div class=\"skeleton h-4 rounded w-3/4\"></div><div class=\"skeleton h-3 rounded w-1/2\"></div></div>`;
      $("#results").appendChild(sk);
    });
    $("#results").classList.remove("hidden");
    try {
      const resp = await api("/api/parse", { method: "POST", body: JSON.stringify({ urls }) });
      const data = await resp.json();
      state.results = data.results || [];
      const success = state.results.filter((r) => r.ok).length;
      toast(`解析完成：${success}/${state.results.length}`, success ? "success" : "error");
      renderResults();
    } catch (e) {
      toast("解析失败：" + e.message, "error");
    } finally {
      state.busy = false;
      btn.disabled = false;
      btn.classList.remove("opacity-60");
    }
  }

  async function downloadSingle(item) {
    if (!item.ok) return;
    toast("开始下载：" + fmt.short(item.title, 24), "info");
    const url = `/api/download?url=${encodeURIComponent(item.url)}`;
    const a = document.createElement("a");
    a.href = url;
    a.download = (item.title || "video") + "." + (item.ext || "mp4");
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function downloadBatch() {
    const items = Array.from(state.selected).map((i) => state.results[i]).filter((r) => r && r.ok);
    if (!items.length) { toast("请先勾选要下载的视频", "error"); return; }
    toast("打包中：" + items.length + " 个视频", "info");
    try {
      const resp = await api("/api/batch-download", { method: "POST", body: JSON.stringify({ items }) });
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "videos.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast("打包完成，已开始下载", "success");
    } catch (e) {
      toast("打包失败：" + e.message, "error");
    }
  }

  function bind() {
    $("#url-input").addEventListener("input", updateCounter);
    $("#btn-parse").addEventListener("click", parse);
    $("#btn-clear").addEventListener("click", () => { $("#url-input").value = ""; updateCounter(); });
    $("#btn-paste").addEventListener("click", async () => {
      try { const text = await navigator.clipboard.readText(); $("#url-input").value = text; updateCounter(); toast("已粘贴", "success"); } catch (e) { toast("剪贴板权限被拒绝", "error"); }
    });
    $("#results").addEventListener("click", (e) => {
      const t = e.target.closest("[data-action]");
      if (!t) return;
      const idx = Number(t.dataset.idx);
      const item = state.results[idx];
      if (!item) return;
      if (t.dataset.action === "download") downloadSingle(item);
      else if (t.dataset.action === "retry") parse();
      else if (t.dataset.action === "copy") {
        const link = item.video_url || item.url;
        navigator.clipboard.writeText(link).then(() => toast("链接已复制", "success"));
      }
    });
    $("#results").addEventListener("change", (e) => {
      if (e.target.classList.contains("select-item")) {
        const idx = Number(e.target.dataset.idx);
        if (e.target.checked) state.selected.add(idx); else state.selected.delete(idx);
        updateBatchBar();
      }
    });
    $("#btn-select-all").addEventListener("click", () => {
      state.results.forEach((r, i) => { if (r.ok) state.selected.add(i); });
      $$(".select-item").forEach((cb) => { cb.checked = true; });
      updateBatchBar();
    });
    $("#btn-deselect-all").addEventListener("click", () => {
      state.selected.clear();
      $$(".select-item").forEach((cb) => { cb.checked = false; });
      updateBatchBar();
    });
    $("#btn-download-selected").addEventListener("click", downloadBatch);
    $("#year").textContent = String(new Date().getFullYear());
    updateCounter();
  }

  document.addEventListener("DOMContentLoaded", () => { bind(); loadPlatforms(); });
})();
