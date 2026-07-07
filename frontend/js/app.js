var App = (function () {
  var $container = null;
  var $sidebarNav = null;
  var $sidebarFooter = null;
  var _progressTimer = null;
  var _progressStartedAt = 0;
  var _jobRefreshTimer = null;

  function enqueue(cb) { setTimeout(cb, 10); }
  var $ = function (id) { return document.getElementById(id); };
  var cls = function (tag, className, html) {
    var el = document.createElement(tag);
    if (className) el.className = className;
    if (html !== undefined) el.innerHTML = String(html);
    return el;
  };

  var routes = {
    "": "watchlists",
    "login": "login",
    "register": "register",
    "opportunities": "opportunities",
    "today": "today",
    "watchlists": "watchlists",
    "watchlist-detail": "watchlistDetail",
    "jobs": "jobs",
    "reports": "reports",
    "report-detail": "reportDetail",
  };

  var SVG = {
    today: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    opportunities: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/><circle cx="7" cy="17" r="2"/><circle cx="13" cy="11" r="2"/><circle cx="19" cy="5" r="2"/></svg>',
    watchlists: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="4" cy="6" r="1.2" fill="currentColor" stroke="none"/><circle cx="4" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="4" cy="18" r="1.2" fill="currentColor" stroke="none"/></svg>',
    reports: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
    jobs: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8" fill="currentColor" stroke="none"/></svg>',
    logout: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',
  };

  function init() {
    var savedUrl = localStorage.getItem("mkt_base_url");
    if (savedUrl) API.setBaseUrl(savedUrl);
    $container = document.getElementById("mainContent");
    $sidebarNav = document.getElementById("sidebarNav");
    $sidebarFooter = document.getElementById("sidebarFooter");
    window.addEventListener("hashchange", navigate);
    window.addEventListener("mkt:unauthorized", function () {
      showToast("登录已过期，请重新登录", "warn");
      renderNav();
      location.hash = "#login";
    });
    renderNav();
    navigate();
    var toast = cls("div", "toast", "");
    toast.id = "toast";
    document.body.appendChild(toast);
    var progress = cls("div", "progress-overlay", "");
    progress.id = "progressOverlay";
    document.body.appendChild(progress);

    var toggleBtn = document.getElementById("sidebarToggle");
    var sidebar = document.querySelector(".sidebar");
    var saved = localStorage.getItem("sidebar_collapsed");
    if (saved === "1") sidebar.classList.add("collapsed");
    toggleBtn.addEventListener("click", function () {
      sidebar.classList.toggle("collapsed");
      localStorage.setItem("sidebar_collapsed", sidebar.classList.contains("collapsed") ? "1" : "0");
    });
    document.addEventListener("click", function (event) {
      var head = event.target.closest && event.target.closest("collapsible .head");
      if (head) head.parentElement.classList.toggle("open");
    });
  }

  function navigate() {
    clearTimeout(_jobRefreshTimer);
    var hash = (location.hash || "#").replace("#", "");
    var parts = hash.split("/");
    var route = parts[0];
    var page = routes[route] || routes[""];
    document.body.classList.toggle("auth-mode", page === "login" || page === "register");
    showError("");
    if (page !== "login" && page !== "register" && !API.isLoggedIn()) {
      location.hash = "#login";
      enqueue(navigate);
      return;
    }
    renderNav();
    $container.classList.remove("page-fade");
    void $container.offsetWidth;
    $container.classList.add("page-fade");
    window[page]();
  }

  function navItem(href, icon, label, isActive) {
    return '<a href="' + href + '"' + (isActive ? ' class="active"' : '') + '>' + icon + '<span>' + label + '</span></a>';
  }

  function renderNav() {
    var isAuth = API.isLoggedIn();
    var hash = (location.hash || "#").replace("#", "");
    var route = hash.split("/")[0];

    $sidebarNav.innerHTML = [
      navItem("#opportunities", SVG.opportunities, "机会扫描", route === "opportunities"),
      navItem("#today", SVG.today, "今日报告", route === "today"),
      navItem("#watchlists", SVG.watchlists, "关注列表", route === "watchlists" || route === "" || route === "watchlist-detail"),
      navItem("#reports", SVG.reports, "历史报告", route === "reports" || route === "report-detail"),
      '<div class="nav-divider"></div>',
      navItem("#jobs", SVG.jobs, "生成记录", route === "jobs"),
    ].join("");

    $sidebarFooter.innerHTML = isAuth
      ? '<a href="#login" onclick="API.setToken(\'\');location.hash=\'#login\'">' + SVG.logout + '<span>退出登录</span></a>'
      : [
          '<a href="#login"' + (route === "login" ? ' class="active"' : '') + '><span style="margin-left:28px">登录</span></a>',
          '<a href="#register"' + (route === "register" ? ' class="active"' : '') + '><span style="margin-left:28px">注册</span></a>',
        ].join("");
  }

  function showToast(msg, type) {
    var el = document.getElementById("toast");
    el.className = "toast" + (type ? " " + type : "");
    el.textContent = msg;
    el.style.display = "block";
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function () { el.style.display = "none"; }, 3000);
  }

  function showError(msg) {
    var el = document.getElementById("errorBox");
    if (!msg) { el.style.display = "none"; return; }
    el.textContent = msg;
    el.style.display = "block";
  }

  function setBusyButton(btn, text) {
    if (!btn) return function () {};
    var oldText = btn.textContent;
    var oldDisabled = btn.disabled;
    btn.disabled = true;
    btn.textContent = text;
    return function () {
      btn.disabled = oldDisabled;
      btn.textContent = oldText;
    };
  }

  function loadingView() {
    return '<div class="card"><div class="card-pad"><div class="skeleton-stack">' +
      '<div class="skeleton-line short"></div>' +
      '<div class="skeleton-card"></div>' +
      '<div class="skeleton-card"></div>' +
      '<div class="skeleton-line mid"></div>' +
      '</div></div></div>';
  }

  function showProgress(title, detail, steps, actionHtml) {
    var el = document.getElementById("progressOverlay");
    if (!el) return;
    _progressStartedAt = Date.now();
    el.innerHTML = [
      '<div class="progress-panel">',
      '<div class="progress-top">',
      '<div><div class="progress-title">' + esc(title) + '</div><div id="progressDetail" class="progress-detail">' + esc(detail || "") + '</div></div>',
      '<div id="progressTime" class="progress-time">00:00</div>',
      '</div>',
      '<div id="progressSteps" class="progress-steps">' + steps.map(function (step, idx) {
        return '<div class="progress-step" data-step="' + idx + '"><span class="progress-dot"></span><span>' + esc(step) + '</span></div>';
      }).join("") + '</div>',
      '<div class="progress-actions">' + (actionHtml === undefined ? '<a class="btn ghost sm" href="#jobs" onclick="App.hideProgress()">查看任务</a>' : actionHtml) + '</div>',
      '</div>',
    ].join("");
    el.style.display = "flex";
    updateProgress(0, detail || "");
    clearInterval(_progressTimer);
    _progressTimer = setInterval(function () {
      var target = document.getElementById("progressTime");
      if (!target) return;
      var seconds = Math.floor((Date.now() - _progressStartedAt) / 1000);
      target.textContent = String(Math.floor(seconds / 60)).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
    }, 1000);
  }

  function updateProgress(activeIndex, detail) {
    var detailEl = document.getElementById("progressDetail");
    if (detailEl && detail !== undefined) detailEl.textContent = detail;
    var steps = document.querySelectorAll(".progress-step");
    steps.forEach(function (step, idx) {
      step.classList.toggle("done", idx < activeIndex);
      step.classList.toggle("active", idx === activeIndex);
    });
  }

  function hideProgress() {
    var el = document.getElementById("progressOverlay");
    if (el) el.style.display = "none";
    clearInterval(_progressTimer);
    _progressTimer = null;
  }

  async function pollJobUntilSettled(jobId) {
    var delay = 1600;
    for (var i = 0; i < 45; i++) {
      await new Promise(function (resolve) { setTimeout(resolve, delay); });
      var latest = await API.jobs.get(jobId);
      var st = latest.status || "";
      if (st === "succeeded" || st === "failed" || st === "dead" || st === "cancelled") return latest;
      delay = Math.min(3500, delay + 250);
    }
    return API.jobs.get(jobId);
  }

  function badge(text, type) {
    return '<span class="badge ' + (type || "neutral") + '">' + esc(text) + '</span>';
  }
  function esc(s) { return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function escAttr(s) { return esc(s).replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }
  function h(c, t) { return "<" + c + ">" + esc(t) + "</" + c + ">"; }
  function linkify(s) {
    return esc(s).replace(/(https?:\/\/[^\s)]+)/g, function (url) {
      return '<a href="' + escAttr(url) + '" target="_blank" rel="noopener">' + esc(url) + '</a>';
    });
  }
  function fmtTime(value) {
    if (!value) return "";
    var text = String(value).trim();
    var normalized = text;
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(text)) {
      normalized = text.replace(" ", "T") + "Z";
    }
    var d = new Date(normalized);
    if (isNaN(d.getTime())) return text;
    return d.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }
  function formatReportText(text) {
    var lines = String(text || "").split(/\r?\n/);
    var html = [];
    var inList = false;
    function closeList() {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
    }
    lines.forEach(function (raw) {
      var line = raw.trim();
      if (!line) {
        closeList();
        html.push('<div class="report-spacer"></div>');
        return;
      }
      if (/^#{1,3}\s+/.test(line)) {
        closeList();
        html.push('<div class="report-heading">' + esc(line.replace(/^#{1,3}\s+/, "")) + '</div>');
      } else if (/^([一二三四五六七八九十]+[、.]|\d+[.、])\s*/.test(line)) {
        closeList();
        html.push('<div class="report-heading">' + esc(line) + '</div>');
      } else if (/^[-*]\s+/.test(line)) {
        if (!inList) {
          html.push("<ul>");
          inList = true;
        }
        html.push("<li>" + linkify(line.replace(/^[-*]\s+/, "")) + "</li>");
      } else {
        closeList();
        html.push("<p>" + linkify(line) + "</p>");
      }
    });
    closeList();
    return html.join("");
  }
  function sourceHost(url) {
    if (!url) return "";
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch (_) {
      return "";
    }
  }
  function riskBadgeType(risk) {
    var text = String(risk || "").toLowerCase();
    if (text.indexOf("high") >= 0 || text.indexOf("red") >= 0) return "bad";
    if (text.indexOf("medium") >= 0 || text.indexOf("warning") >= 0) return "warn";
    if (text.indexOf("low") >= 0 || text.indexOf("safe") >= 0) return "good";
    return "neutral";
  }
  function opportunityBadgeType(item) {
    var text = String((item && (item.signal_type || item.recommendation_type)) || "").toLowerCase();
    var risk = String((item && item.risk_level) || "").toLowerCase();
    if (text.indexOf("风险") >= 0 || risk === "high") return "bad";
    if (text.indexOf("谨慎") >= 0 || risk === "medium") return "warn";
    if (text.indexOf("market_signal") >= 0 || text.indexOf("观察") >= 0) return "good";
    return "info";
  }
  function _jobStatusText(status) {
    var map = {
      pending: "等待中",
      running: "生成中",
      succeeded: "已完成",
      failed: "失败",
      dead: "已停止",
    };
    return map[status] || status || "-";
  }
  function formatScore(value) {
    if (value === undefined || value === null || value === "") return "";
    var n = Number(value);
    if (isNaN(n)) return String(value);
    return n.toFixed(2);
  }
  function formatPct(value) {
    if (value === undefined || value === null || value === "") return "-";
    var n = Number(value);
    if (isNaN(n)) return String(value);
    return Math.round(n * 100) + "%";
  }
  function tickerName(symbol) {
    var s = String(symbol || "").toUpperCase();
    var p = (window.WATCHLIST_PRESETS || []).find(function (item) {
      return String(item.symbol || "").toUpperCase() === s;
    });
    return p ? (p.display_name || p.label || s) : s;
  }
  function cleanSourceText(value) {
    var text = String(value || "")
      .replace(/^#{1,6}\s*/gm, "")
      .replace(/[*`_>]/g, "")
      .replace(/^\s*[-+]\s+/gm, "")
      .replace(/^\s*\d+[.)、]\s+/gm, "")
      .split(/\r?\n/)
      .map(function (line) { return line.trim(); })
      .filter(function (line) {
        return line && !/^生成时间[:：]/.test(line) && !/^Generated[:：]/i.test(line);
      })
      .join(" ");
    return text.replace(/\s+/g, " ").trim();
  }
  function metaPill(label, value) {
    if (value === undefined || value === null || value === "") return "";
    return '<span class="source-pill"><span>' + esc(label) + '</span><strong>' + esc(value) + '</strong></span>';
  }
  function renderSourceCard(item, idx) {
    var url = item.source_url || "";
    var host = sourceHost(url);
    var sourceName = item.source_name || host || "source";
    var title = item.title || "Untitled";
    var titleHtml = url
      ? '<a href="' + escAttr(url) + '" target="_blank" rel="noopener">' + esc(title) + '</a>'
      : esc(title);
    var score = formatScore(item.relevance_score);
    var published = fmtTime(item.published_at) || item.published_at || "";
    var sourceLine = url
      ? '<a href="' + escAttr(url) + '" target="_blank" rel="noopener">' + esc(sourceName) + '</a>'
      : '<span>' + esc(sourceName) + '</span>';
    var urlLine = host ? '<span class="source-domain">' + esc(host) + '</span>' : "";
    var topicLine = [
      metaPill("Tickers", item.tickers),
      metaPill("Topics", item.topics),
      score ? metaPill("Score", score) : "",
    ].filter(Boolean).join("");

    return '<article class="source-card">' +
      '<div class="source-index">' + String(idx + 1).padStart(2, "0") + '</div>' +
      '<div class="source-content">' +
        '<div class="source-topline">' +
          '<div class="source-origin">' + sourceLine + urlLine + '</div>' +
          '<div class="source-badges">' +
            (item.risk_level ? badge(item.risk_level, riskBadgeType(item.risk_level)) : "") +
            (published ? '<span class="badge neutral">' + esc(published) + '</span>' : "") +
          '</div>' +
        '</div>' +
        '<h3 class="source-title">' + titleHtml + '</h3>' +
        (item.summary ? '<div class="source-block"><div class="source-block-label">摘要</div><p>' + esc(cleanSourceText(item.summary)) + '</p></div>' : '') +
        (item.impact_analysis ? '<div class="source-block"><div class="source-block-label">影响分析</div><p>' + esc(cleanSourceText(item.impact_analysis)) + '</p></div>' : '') +
        (topicLine ? '<div class="source-meta">' + topicLine + '</div>' : '') +
      '</div>' +
    '</article>';
  }

  function renderMarketSignalCard(signal, idx) {
    var tickers = (signal.related_tickers || []).join(", ") || "-";
    var articles = signal.supporting_articles || [];
    var articleHtml = articles.length
      ? articles.map(function (a, articleIdx) {
          var url = a.url || "";
          var title = a.title || "Untitled article";
          var source = a.source || sourceHost(url) || "unknown source";
          var titleHtml = url
            ? '<a href="' + escAttr(url) + '" target="_blank" rel="noopener">' + esc(title) + '</a>'
            : esc(title);
          return '<div class="source-block">' +
            '<div class="source-block-label">相关来源 ' + (articleIdx + 1) + '</div>' +
            '<p>' + titleHtml + '</p>' +
            '<div class="source-meta">' +
              metaPill("Source", source) +
              metaPill("Published", fmtTime(a.published_at) || a.published_at || "-") +
              metaPill("Score", formatScore(a.relevance_score)) +
            '</div>' +
            (a.reason ? '<p style="margin-top:6px">' + esc(a.reason) + '</p>' : '') +
          '</div>';
        }).join("")
      : '<div class="source-block"><div class="source-block-label">相关来源</div><p>暂无可展开来源，需人工复核。</p></div>';

    return '<article class="source-card">' +
      '<div class="source-index">' + String(idx + 1).padStart(2, "0") + '</div>' +
      '<div class="source-content">' +
        '<div class="source-topline">' +
          '<div class="source-origin"><strong>' + esc(signal.title || ("市场观察信号 " + (idx + 1))) + '</strong></div>' +
          '<div class="source-badges">' +
            badge(signal.risk_level || "unknown", riskBadgeType(signal.risk_level)) +
            badge("confidence " + formatScore(signal.confidence), "info") +
          '</div>' +
        '</div>' +
        '<div class="source-meta">' +
          metaPill("Tickers", tickers) +
          metaPill("Event", signal.event_type || "unknown") +
          metaPill("Type", signal.signal_type || "market_signal") +
        '</div>' +
        '<div class="source-block"><div class="source-block-label">证据摘要</div><p>' + esc(signal.evidence_summary || signal.summary || "") + '</p></div>' +
        '<div class="source-block"><div class="source-block-label">关联理由</div><p>' + esc(signal.entity_linking_reason || "-") + '</p></div>' +
        '<div class="source-block"><div class="source-block-label">风险原因</div><p>' + esc(signal.risk_reason || "-") + '</p></div>' +
        '<div class="source-block"><div class="source-block-label">不确定性说明</div><p>' + esc(signal.uncertainty || "-") + '</p></div>' +
        '<collapsible><div class="head">展开证据链（' + articles.length + '）</div><div class="body">' + articleHtml + '</div></collapsible>' +
      '</div>' +
    '</article>';
  }

  function pageHead(title, rightHtml, backHref) {
    var back = backHref ? '<a class="page-back" href="' + backHref + '">&larr;</a>' : '';
    return '<div class="page-head"><div class="page-head-left">' + back + '<h1 class="page-title">' + title + '</h1></div>' +
      (rightHtml ? '<div class="page-head-right">' + rightHtml + '</div>' : '') + '</div>';
  }

  /* helpers for wl detail */
  var _pendingAdds = [];
  var _currentWlId = 0;
  var _currentItems = [];

  function _isPresetAdded(p) {
    return _currentItems.some(function (item) {
      var kw = (item.keyword || "").toLowerCase();
      var sym = (item.symbol || "").toUpperCase();
      var pk = (p.keyword || "").toLowerCase();
      var ps = (p.symbol || "").toUpperCase();
      return pk && kw === pk || (ps && sym === ps);
    });
  }

  function _isPresetPending(p) {
    return _pendingAdds.some(function (pp) { return pp.keyword === p.keyword && pp.item_type === p.item_type; });
  }

  function _typeLabel(t) {
    var m = { ticker: "股票代码", company: "公司", topic: "主题", macro: "宏观", commodity: "商品", custom: "自定义" };
    return m[t] || t;
  }

  function _typeBadge(t) {
    return t === "ticker" ? "info" : t === "macro" ? "warn" : t === "commodity" ? "good" : "neutral";
  }

  function _renderPresetChips(presets, showCategory) {
    return presets.map(function (p) {
      var isAdded = _isPresetAdded(p);
      var isPending = _isPresetPending(p);
      var clsName = isAdded ? " added" : isPending ? " pending" : "";
      var action = isAdded ? "已添加" : isPending ? "待添加" : "+ 添加";
      var onclick = isAdded ? "" : ('onclick="App.togglePreset(\'' + esc(p.item_type) + '\',\'' + esc(p.symbol) + '\',\'' + esc(p.keyword || p.label) + '\',\'' + esc(p.display_name || p.label) + '\')"');
      var catIdx = WATCHLIST_CATEGORIES.indexOf(p.category);
      return '<div class="preset-card wl-cat-' + catIdx + clsName + '" ' + onclick + '>' +
        '<div class="card-row"><span class="badge ' + _typeBadge(p.item_type) + '">' + _typeLabel(p.item_type) + '</span></div>' +
        '<div class="card-title">' + esc(p.display_name || p.label) + '</div>' +
        (p.symbol ? '<div class="card-code">' + esc(p.symbol) + '</div>' : '') +
        '<div class="card-meta">' +
          '<span>' + (showCategory ? esc(p.category) + ' · ' : '') + esc(p.keyword !== p.label ? (p.keyword || "").substring(0, 24) : "") + '</span>' +
          '<span class="card-action">' + action + '</span>' +
        '</div></div>';
    }).join("");
  }

  /* ── Pages ── */

  window.login = function () {
    $container.innerHTML = [
      '<div class="auth-full"><div class="auth-card"><div class="auth-kicker">Financial Agents</div><h2>登录</h2><p class="auth-desc">进入后创建关注列表，选择你关心的股票、行业或宏观主题。</p>',
      '<div class="form-grid">',
      '<div><label class="form-label">邮箱</label><input id="loginEmail" type="text" placeholder="name@example.com" /></div>',
      '<div><label class="form-label">密码</label><input id="loginPassword" type="password" placeholder="输入密码" /></div>',
      '<button class="btn primary block" style="margin-top:4px" onclick="App.doLogin()">登录</button>',
      '<p class="form-hint" style="text-align:center">还没有账号？<a href="#register">创建账号</a></p>',
      '</div></div></div>',
    ].join("");
  };

  window.doLogin = async function () {
    showError("");
    try {
      var data = await API.auth.login($("loginEmail").value, $("loginPassword").value);
      API.setToken(data.access_token);
      showToast("登录成功", "good");
      renderNav();
      location.hash = "#watchlists";
    } catch (e) { showError("登录失败：" + e.message); }
  };

  window.register = function () {
    $container.innerHTML = [
      '<div class="auth-full"><div class="auth-card"><div class="auth-kicker">Financial Agents</div><h2>创建账号</h2><p class="auth-desc">只需要邮箱和密码。进入后可以先从预设关注项开始。</p>',
      '<div class="form-grid">',
      '<div><label class="form-label">邮箱</label><input id="regEmail" type="text" placeholder="name@example.com" /></div>',
      '<div><label class="form-label">密码</label><input id="regPassword" type="password" placeholder="至少 8 位" /></div>',
      '<button class="btn primary block" style="margin-top:4px" onclick="App.doRegister()">创建账号</button>',
      '<p class="form-hint" style="text-align:center">已有账号？<a href="#login">去登录</a></p>',
      '</div></div></div>',
    ].join("");
  };

  window.doRegister = async function () {
    showError("");
    try {
      await API.auth.register($("regEmail").value, $("regPassword").value);
      showToast("账号已创建，请登录", "good");
      location.hash = "#login";
    } catch (e) { showError("注册失败：" + e.message); }
  };

  /* ── Watchlists List ── */
  window.watchlists = async function () {
    showError("");
    $container.innerHTML = pageHead("关注列表", '<button class="btn primary" onclick="App.createWatchlist(this)">新建关注列表</button>') + '<div class="page-body">' + loadingView() + '</div>';
    try {
      var wls = await API.watchlists.list();
      var rows = wls.map(function (w) {
        return '<tr><td><a href="#watchlist-detail/' + w.id + '">' + esc(w.name) + '</a></td><td style="color:var(--text-dim)">' + esc(fmtTime(w.created_at)) + '</td><td><button class="btn secondary sm" onclick="App.createJob(' + w.id + ', this)">生成今日报告</button></td></tr>';
      }).join("");

      var body = document.querySelector(".page-body");
      body.innerHTML = [
        '<div class="card"><div class="card-pad">',
        '<div class="form-grid" style="margin-bottom:18px">',
        '<div class="form-row"><input id="wlName" type="text" placeholder="例如：AI 芯片观察、我的美股组合、宏观与黄金" style="flex:1" onkeydown="if(event.key===\'Enter\') App.createWatchlist()" /><button class="btn primary" onclick="App.createWatchlist(this)">创建关注列表</button></div>',
        '<div class="form-hint">先给关注列表起个名字，再从预设里添加股票、行业或宏观主题。</div>',
        '</div>',
        wls.length
          ? '<div class="table-wrap"><table><thead><tr><th>名称</th><th>创建时间</th><th style="width:120px"></th></tr></thead><tbody>' + rows + '</tbody></table></div>'
          : '<div class="empty-state"><div class="empty-state-icon">📋</div><p>还没有关注列表</p><p style="color:var(--text-muted);font-size:12px">从一个主题开始，比如“AI 芯片观察”。</p><button class="btn primary sm" style="margin-top:4px" onclick="document.getElementById(\'wlName\').focus()">创建第一个关注列表</button></div>',
        '</div></div>',
      ].join("");
    } catch (e) { showError("加载失败：" + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  window.createWatchlist = async function (btn) {
    showError("");
    var name = $("wlName").value.trim();
    if (!name) return showError("Name is required");
    var restore = setBusyButton(btn, "创建中...");
    try {
      var wl = await API.watchlists.create(name);
      showToast("关注列表已创建");
      if (wl && wl.id) location.hash = "#watchlist-detail/" + wl.id;
      else window.watchlists();
    } catch (e) {
      showError(e.message);
    } finally {
      restore();
    }
  };

  window.createJob = async function (wlId, btn) {
    showError("");
    var createdJobId = null;
    var restore = setBusyButton(btn, "生成中...");
    var steps = ["检查关注列表", "创建报告任务", "分析新闻与风险", "生成报告"];
    try {
      showProgress("正在生成今日报告", "正在检查关注项", steps);
      var items = _currentWlId === Number(wlId) && Array.isArray(_currentItems)
        ? _currentItems
        : await API.watchlists.items(wlId);
      if (!items || !items.length) {
        hideProgress();
        showError("请先添加至少一个关注项，再生成今日报告");
        enqueue(function () { location.hash = "#watchlist-detail/" + wlId; });
        return;
      }

      updateProgress(1, "已找到 " + items.length + " 个关注项，正在创建任务");
      var job = await API.watchlists.createJob(wlId);
      if (!job.id) throw new Error("报告任务创建成功，但未返回任务 ID");
      createdJobId = job.id;

      updateProgress(2, "任务 #" + job.id + " 已创建，正在分析新闻源");
      job = await API.jobs.run(job.id);
      if (job && job.status === "running") {
        updateProgress(2, "任务仍在运行，正在自动刷新状态");
        job = await pollJobUntilSettled(job.id);
      }
      var st = job.status || "";
      if (st === "succeeded" && job.report_id) {
        updateProgress(3, "报告已生成，正在打开详情");
        showToast("今日报告已生成", "good");
        setTimeout(hideProgress, 500);
        enqueue(function () { location.hash = "#report-detail/" + job.report_id; });
      } else if (st === "failed" || st === "dead") {
        hideProgress();
        showError("报告生成失败，请检查新闻源或稍后重试" + (job.error_message ? "：" + job.error_message : ""));
      } else if (job.id) {
        updateProgress(2, "报告仍在生成，可在任务状态页继续查看");
        showToast("报告正在生成，可稍后查看", "warn");
        setTimeout(hideProgress, 600);
        enqueue(function () { location.hash = "#jobs"; });
      } else {
        hideProgress();
        showToast("报告任务状态：" + (st || "unknown"), "warn");
      }
    } catch (e) {
      if (createdJobId) {
        try {
          var latest = await API.jobs.get(createdJobId);
          if (latest && latest.error_message) {
            hideProgress();
            showError("报告生成失败，请检查新闻源或稍后重试：" + latest.error_message);
            return;
          }
        } catch (_) {}
      }
      hideProgress();
      showError("报告生成失败，请检查新闻源或稍后重试" + (e.message ? "：" + e.message : ""));
    } finally {
      restore();
    }
  };

  /* ── Watchlist Detail ── */
  window.togglePreset = function (itemType, symbol, keyword, displayName) {
    var idx = _pendingAdds.findIndex(function (pp) { return pp.keyword === keyword && pp.item_type === itemType; });
    if (idx >= 0) { _pendingAdds.splice(idx, 1); }
    else { _pendingAdds.push({ item_type: itemType, symbol: symbol, keyword: keyword, display_name: displayName, name: displayName || keyword }); }
    window.watchlistDetail();
  };

  window.addBundle = function (bundleName) {
    var bundle = WATCHLIST_BUNDLES.find(function (b) { return b.name === bundleName; });
    if (!bundle) return;
    bundle.keys.forEach(function (k) {
      var p = WATCHLIST_PRESETS.find(function (pp) { return pp.keyword === k || pp.label === k || pp.symbol === k || pp.display_name === k; });
      if (p && !_isPresetAdded(p) && !_isPresetPending(p)) {
        _pendingAdds.push({ item_type: p.item_type, symbol: p.symbol, keyword: p.keyword || p.label, display_name: p.display_name || p.label, name: p.display_name || p.label });
      }
    });
    showToast("已选中组合：" + bundleName, "good");
    window.watchlistDetail();
  };

  window.addCategory = function (cat) {
    WATCHLIST_PRESETS.filter(function (p) { return p.category === cat; }).forEach(function (p) {
      if (!_isPresetAdded(p) && !_isPresetPending(p)) {
        _pendingAdds.push({ item_type: p.item_type, symbol: p.symbol, keyword: p.keyword || p.label, display_name: p.display_name || p.label, name: p.display_name || p.label });
      }
    });
    showToast("已选中分类：" + cat, "good");
    window.watchlistDetail();
  };

  window.clearPending = function () { _pendingAdds = []; window.watchlistDetail(); };

  window.batchAddToWatchlist = async function () {
    showError("");
    if (!_pendingAdds.length) return showToast("还没有选中关注项", "warn");
    var success = 0, failed = 0;
    for (var i = 0; i < _pendingAdds.length; i++) {
      var item = _pendingAdds[i];
      try { await API.watchlists.addItem(_currentWlId, item); success++; }
        catch (e) { showToast("添加失败：" + (item.display_name || item.keyword) + " - " + e.message, "bad"); failed++; }
    }
    _pendingAdds = [];
    showToast(success ? "已添加 " + success + " 个关注项，可以生成今日报告" + (failed ? "，" + failed + " 个失败" : "") : "未添加关注项");
    window.watchlistDetail();
  };

  window.watchlistDetail = async function () {
    showError("");
    var parts = (location.hash || "#").replace("#watchlist-detail/", "").split("/");
    _currentWlId = Number(parts[0]);
    $container.innerHTML = pageHead("关注列表详情", '<button class="btn primary" onclick="App.createJob(' + _currentWlId + ', this)">生成今日报告</button>', "#watchlists") + '<div class="page-body">' + loadingView() + '</div>';
    try {
      _currentItems = await API.watchlists.items(_currentWlId);

      function render(search, cat) {
        var presets = WATCHLIST_PRESETS;
        if (search) {
          var q = search.toLowerCase();
          presets = presets.filter(function (p) {
            return (p.category + " " + p.label + " " + p.keyword + " " + p.display_name + " " + p.symbol).toLowerCase().indexOf(q) >= 0;
          });
        } else if (cat && cat !== "自定义关注") {
          presets = presets.filter(function (p) { return p.category === cat; });
        } else if (cat === "自定义关注") {
          presets = [];
        }

        var tickerCount = _currentItems.filter(function (i) { return i.item_type === "ticker"; }).length;
        var topicCount = _currentItems.filter(function (i) { return !["ticker","commodity","macro"].includes(i.item_type || "ticker"); }).length;
        var macroCount = _currentItems.filter(function (i) { return i.item_type === "macro"; }).length;
        var commodityCount = _currentItems.filter(function (i) { return i.item_type === "commodity"; }).length;

        var dotColors = ["blue", "purple", "amber", "green", "teal", "blue", "red", "amber", "purple", "teal"];
        var sidebarHtml = WATCHLIST_CATEGORIES.map(function (c, ci) {
          return '<div class="wl-side-btn' + (!search && cat === c ? " active" : "") + '" onclick="App.catClick(\'' + esc(c) + '\')"><span class="wl-side-dot ' + dotColors[ci] + '"></span>' + esc(c) + '</div>';
        }).join("");

        var emojis = ["📊", "🧠", "💰", "⛽", "🛡️"];
        var bundlesHtml = WATCHLIST_BUNDLES.length ? (
          '<div class="hero-bundles">' +
          WATCHLIST_BUNDLES.map(function (b, bi) {
            var count = b.keys.filter(function (k) {
              var p = WATCHLIST_PRESETS.find(function (pp) { return pp.keyword === k || pp.label === k || pp.symbol === k || pp.display_name === k; });
              return p && !_isPresetAdded(p);
            }).length;
            return '<div class="bundle-card" onclick="App.addBundle(\'' + esc(b.name) + '\')"><span class="bundle-icon">' + emojis[bi] + '</span><div class="bundle-title">' + esc(b.name) + '</div><div class="bundle-desc">' + esc(b.desc) + '</div><span class="bundle-count">' + count + ' 项可添加</span></div>';
          }).join("") + '</div>'
        ) : '';

        var currentHtml;
        if (_currentItems.length) {
          currentHtml = '<div class="item-row">' +
            _currentItems.map(function (item) {
              return '<span class="item-tag"><span class="badge ' + _typeBadge(item.item_type) + '">' + _typeLabel(item.item_type) + '</span> ' +
                esc(item.display_name || item.keyword || item.symbol) +
                (item.symbol ? ' <span style="color:var(--text-dim)">' + esc(item.symbol) + '</span>' : '') + '</span>';
            }).join("") + '</div>';
        } else {
          currentHtml = '<div class="empty-state" style="min-height:60px;font-size:13px">还没有关注项。可以从上方推荐组合或下方分类里添加。</div>';
        }

        var chips;
        if (presets.length) {
          chips = '<div class="preset-grid">' + _renderPresetChips(presets, !!search) + '</div>';
        } else if (cat === "自定义关注") {
          chips = "";
        } else {
          chips = '<div class="empty-state" style="min-height:60px;font-size:13px">没有匹配的关注项，可以换个关键词试试。</div>';
        }

        var pendingHtml = "";
        if (_pendingAdds.length) {
          pendingHtml = '<div class="pending-bar"><div>' +
            _pendingAdds.map(function (pp) {
              return '<span class="pending-tag"><span class="badge ' + _typeBadge(pp.item_type) + '">' + _typeLabel(pp.item_type) + '</span> ' +
                esc(pp.display_name || pp.keyword) +
                ' <span class="x" onclick="App.togglePreset(\'' + esc(pp.item_type) + '\',\'' + esc(pp.symbol) + '\',\'' + esc(pp.keyword) + '\',\'' + esc(pp.display_name) + '\')">&times;</span></span>';
            }).join("") +
            '</div><div style="display:flex;gap:8px;flex-shrink:0">' +
            '<button class="btn primary sm" onclick="App.batchAddToWatchlist()">添加选中项</button>' +
            '<button class="btn ghost sm" onclick="App.clearPending()">清空</button>' +
            '</div></div>';
        }

        var customForm = [
          '<div class="form-grid">',
          '<div class="form-row"><select id="addType" style="flex:1">' + ["ticker","company","topic","macro","commodity","custom"].map(function(t){return '<option value="'+t+'">'+_typeLabel(t)+'</option>';}).join("") + '</select>',
          '<input id="addSymbol" type="text" placeholder="股票代码，例如 NVDA" style="flex:1" /></div>',
          '<input id="addKeyword" type="text" placeholder="搜索关键词（必填），例如 NVIDIA / AI chips / gold" />',
          '<input id="addDisplay" type="text" placeholder="显示名称，例如 英伟达 / AI 芯片 / 黄金" />',
          '<button class="btn primary block" onclick="App.doCustomAdd()">添加关注项</button>',
          '</div>',
        ].join("");

        var body = document.querySelector(".page-body");
        body.innerHTML = [
          _currentItems.length
            ? '<div class="summary-bar">已关注 <span class="num">' + _currentItems.length + '</span> 项' +
              (tickerCount ? ' · 股票 <span class="num">' + tickerCount + '</span>' : '') +
              (topicCount ? ' · 主题 <span class="num">' + topicCount + '</span>' : '') +
              (macroCount ? ' · 宏观 <span class="num">' + macroCount + '</span>' : '') +
              (commodityCount ? ' · 商品 <span class="num">' + commodityCount + '</span>' : '') +
              '</div>'
            : '',

          WATCHLIST_BUNDLES.length ? '<div class="section-title">推荐组合</div>' + bundlesHtml : '',

          pendingHtml,

          '<div style="margin-bottom:14px"><input id="presetSearch" type="text" placeholder="搜索股票、公司、主题，例如 NVIDIA、AI chips、Fed、gold" oninput="App.searchPresets()" value="" /></div>',

          '<div class="wl-grid">',
          '<div class="wl-side">' + sidebarHtml + '</div>',
          '<div>',
          (cat !== "自定义关注" && !search && presets.length ? '<button class="btn secondary sm" style="margin-bottom:12px" onclick="App.addCategory(\'' + esc(cat) + '\')">添加本分类全部 ' + presets.length + ' 项</button>' : ""),
          chips,

          '<collapsible><div class="head" onclick="this.parentElement.classList.toggle(\'open\')">已关注 ' + _currentItems.length + ' 项</div><div class="body">' + currentHtml + '</div></collapsible>',
          '<collapsible><div class="head" onclick="this.parentElement.classList.toggle(\'open\')">添加自定义关注项</div><div class="body"><p class="form-hint" style="margin-bottom:8px">预设里找不到时，可以手动添加关键词。</p>' + customForm + '</div></collapsible>',

          '</div></div>',
        ].join("");
      }

      render("", WATCHLIST_CATEGORIES[0]);

      window.searchPresets = function () {
        var q = (document.getElementById("presetSearch") || {}).value || "";
        render(q, "");
      };

      window.catClick = function (cat) {
        var inp = document.getElementById("presetSearch");
        if (inp) inp.value = "";
        render("", cat);
      };

    } catch (e) { showError("加载失败：" + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  window.doCustomAdd = async function () {
    showError("");
    var itemType = document.getElementById("addType").value;
    var symbol = document.getElementById("addSymbol").value.trim();
    var keyword = document.getElementById("addKeyword").value.trim();
    var display = document.getElementById("addDisplay").value.trim();
    if (!keyword) return showError("请填写搜索关键词");
    try {
      await API.watchlists.addItem(_currentWlId, {
        item_type: itemType, symbol: symbol, keyword: keyword, display_name: display, name: display || keyword,
      });
      showToast("关注项已添加", "good");
      window.watchlistDetail();
    } catch (e) { showError(e.message); }
  };

  /* ── Jobs ── */
  window.jobs = async function () {
    showError("");
    clearTimeout(_jobRefreshTimer);
    $container.innerHTML = pageHead("生成记录", '<button class="btn secondary" onclick="App.jobs()">刷新</button>') + '<div class="page-body">' + loadingView() + '</div>';
    try {
      var jobs = await API.jobs.list();
      var hasRunning = jobs.some(function (j) { return j.status === "running" || j.status === "pending"; });
      var rows = jobs.map(function (j) {
        var isDaily = j.job_type === "daily";
        var stBadge = j.status === "succeeded" ? "good" : j.status === "failed" || j.status === "dead" ? "bad" : j.status === "running" ? "info" : "warn";
        return '<tr>' +
          '<td style="font-family:var(--font-mono);font-size:12px">#' + j.id + '</td>' +
          '<td>' + badge(_jobStatusText(j.status), stBadge) + '</td>' +
          '<td>' + (isDaily ? '每日自动' : '手动生成') + '</td>' +
          '<td style="color:var(--text-dim)">' + esc(j.scheduled_for || "-") + '</td>' +
          '<td>' + (j.attempt_count || 0) + '/' + (j.max_attempts || 3) + '</td>' +
          '<td style="color:var(--red);font-size:12px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(j.error_message || "") + '</td>' +
          '<td style="color:var(--text-dim);font-size:12px">' + esc(fmtTime(j.created_at)) + '</td>' +
          '<td>' +
            (j.status === "succeeded" && j.report_id ? '<a href="#report-detail/' + j.report_id + '" style="margin-right:8px">查看报告</a>' : "") +
            '<button class="btn secondary sm" onclick="App.runJob(' + j.id + ')">手动运行</button>' +
          '</td></tr>';
      }).join("");

      var body = document.querySelector(".page-body");
      body.innerHTML = [
        hasRunning
          ? '<div class="notice info" style="margin-bottom:16px">有报告任务正在处理中，本页会自动刷新。</div>'
          : '<div class="notice info" style="margin-bottom:16px">最近的报告生成任务都在这里。</div>',
        '<div class="card"><div class="card-pad">',
        jobs.length
          ? '<div class="table-wrap"><table><thead><tr><th>ID</th><th>状态</th><th>类型</th><th>计划时间</th><th>尝试次数</th><th>错误</th><th>创建时间</th><th>操作</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
          : '<div class="empty-state"><div class="empty-state-icon">⚡</div><p>还没有生成记录</p><p style="color:var(--text-muted);font-size:12px">先创建关注列表并添加关注项，然后点击“生成今日报告”。</p><a class="btn secondary sm" style="margin-top:4px" href="#watchlists">去创建关注列表</a></div>',
        '</div></div>',
      ].join("");
      if (hasRunning) {
        _jobRefreshTimer = setTimeout(function () {
          if ((location.hash || "#").replace("#", "").split("/")[0] === "jobs") window.jobs();
        }, 3500);
      }
    } catch (e) { showError("加载失败：" + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  window.runJob = async function (jobId, btn) {
    showError("");
    var restore = setBusyButton(btn, "运行中...");
    try {
      showProgress("正在运行报告任务", "任务 #" + jobId + " 正在启动", ["启动任务", "分析新闻与风险", "保存报告"]);
      var job = await API.jobs.run(jobId);
      if (job && job.status === "running") {
        updateProgress(1, "任务正在运行，自动刷新状态");
        job = await pollJobUntilSettled(jobId);
      }
      var st = job.status || "";
      if (st === "succeeded" && job.report_id) {
        updateProgress(2, "报告已保存");
        showToast("任务已完成，报告 #" + job.report_id, "good");
        setTimeout(hideProgress, 500);
      } else if (st === "failed" || st === "dead") {
        hideProgress();
        showToast("任务失败：" + (job.error_message || "unknown error"), "bad");
      } else if (st === "running") {
        showToast("任务仍在运行，本页会继续刷新。", "warn");
      } else {
        hideProgress();
        showToast("任务状态：" + st, "warn");
      }
      enqueue(window.jobs);
    } catch (e) {
      hideProgress();
      showError(e.message);
    } finally {
      restore();
    }
  };

  /* ── Opportunities ── */
  window.opportunities = function () {
    showError("");
    $container.innerHTML = pageHead("机会扫描", '<button class="btn primary" onclick="App.runOpportunityScan(this)">开始扫描</button>') + [
      '<div class="page-body">',
      '<div class="opportunity-start">',
      '<div>',
      '<div class="opportunity-kicker">Market Opportunity Radar</div>',
      '<h2>先看最新金融新闻，再识别关联股票</h2>',
      '<p>不按固定股票列表筛选。系统会先按新闻新鲜度扫描市场消息，再从金融相关事件里找出可研究的股票候选。</p>',
      '</div>',
      '<button class="btn primary" onclick="App.runOpportunityScan(this)">扫描今日机会</button>',
      '</div>',
      '<div id="opportunityResult">',
      '<div class="empty-state"><p>点击“扫描今日机会”后，这里会显示候选榜单。</p></div>',
      '</div>',
      '</div>',
    ].join("");
  };

  window.runOpportunityScan = async function (btn) {
    showError("");
    var restore = setBusyButton(btn, "扫描中...");
    try {
      showProgress("正在扫描今日机会", "正在收集最新金融新闻", ["收集新闻", "按新鲜度排序", "识别关联股票", "生成候选榜"], "");
      updateProgress(1, "正在按发布时间和来源质量排序");
      var result = await API.opportunities.scan({ limit: 180, max_items: 10 });
      updateProgress(3, "候选榜单已生成");
      renderOpportunityResult(result);
      showToast("机会扫描已完成", "good");
      setTimeout(hideProgress, 500);
    } catch (e) {
      hideProgress();
      showError("机会扫描失败：" + e.message);
    } finally {
      restore();
    }
  };

  function renderOpportunityResult(result) {
    var signals = result.market_signals || [];
    var recommendations = result.recommendations || [];
    var trends = result.trends || [];
    var trendByTicker = {};
    trends.forEach(function (t) { trendByTicker[String(t.ticker || "").toUpperCase()] = t; });
    if (!signals.length && recommendations.length) {
      signals = recommendations.map(function (rec, idx) {
        return {
          signal_id: "legacy-" + idx,
          title: (rec.ticker || "候选") + " 市场观察信号",
          summary: rec.rationale || "",
          risk_level: rec.risk_level,
          confidence: rec.confidence,
          related_tickers: rec.ticker ? [rec.ticker] : [],
          evidence_summary: rec.rationale || "",
          risk_reason: (rec.risk_flags || []).join("；") || "暂无突出风险标记",
          uncertainty: "该条目来自 legacy recommendations 字段，证据链可能不完整。",
          supporting_articles: [],
          signal_type: "market_signal"
        };
      });
    }

    var stats = [
      ["候选新闻", result.candidate_news_count || 0],
      ["近 72 小时", result.filtered_news_count || 0],
      ["已分析", result.analyzed_news_count || result.total_news || 0],
      ["市场观察信号", signals.length],
    ].map(function (row) {
      return '<div class="opportunity-stat"><span>' + esc(row[0]) + '</span><strong>' + esc(row[1]) + '</strong></div>';
    }).join("");

    var cards = signals.map(function (signal, idx) {
      var ticker = String((signal.related_tickers || [])[0] || "").toUpperCase();
      var trend = trendByTicker[ticker] || {};
      var articles = signal.supporting_articles || [];
      return '<article class="opportunity-card">' +
        '<div class="opportunity-rank">' + String(idx + 1).padStart(2, "0") + '</div>' +
        '<div class="opportunity-main">' +
          '<div class="opportunity-topline">' +
            '<div><h3>' + esc(ticker || "SIGNAL") + '<span>' + esc(ticker ? tickerName(ticker) : "市场观察信号") + '</span></h3></div>' +
            '<div class="source-badges">' +
              badge("市场观察信号", opportunityBadgeType(signal)) +
              badge(signal.risk_level || trend.risk_level || "unknown", riskBadgeType(signal.risk_level || trend.risk_level)) +
            '</div>' +
          '</div>' +
          '<p class="opportunity-rationale">' + esc(signal.summary || signal.evidence_summary || "近期新闻出现可跟踪的市场观察信号，可继续作为研究参考。") + '</p>' +
          '<div class="opportunity-metrics">' +
            metaPill("置信度", formatPct(signal.confidence)) +
            metaPill("事件类型", signal.event_type || "-") +
            metaPill("风险", signal.risk_level || trend.risk_level || "-") +
            metaPill("证据数", articles.length) +
            metaPill("新闻数", trend.news_count || "-") +
          '</div>' +
          '<div class="opportunity-points"><strong>证据摘要</strong><span>' + esc(signal.evidence_summary || "-") + '</span></div>' +
          '<div class="opportunity-points risk"><strong>不确定性</strong><span>' + esc(signal.uncertainty || "-") + '</span></div>' +
        '</div>' +
      '</article>';
    }).join("");

    var target = document.getElementById("opportunityResult");
    if (!target) return;
    target.innerHTML = [
      '<div class="opportunity-toolbar">',
      '<div class="opportunity-stats">' + stats + '</div>',
      result.report_id ? '<a class="btn secondary" href="#report-detail/' + result.report_id + '">查看完整报告</a>' : '',
      '</div>',
      '<div class="notice info" style="margin-bottom:16px">市场观察信号仅用于信息整理和研究参考，不构成投资建议。</div>',
      signals.length
        ? '<div class="opportunity-list">' + cards + '</div>'
        : '<div class="empty-state"><p>本次没有形成足够明确的市场观察信号。</p><p style="color:var(--text-muted);font-size:12px">可以稍后再扫，或先用关注列表分析指定主题。</p></div>',
    ].join("");
  }

  /* ── Today ── */
  window.today = async function () {
    showError("");
    $container.innerHTML = pageHead("今日报告", '') + '<div class="page-body">' + loadingView() + '</div>';
    try {
      var reports = await API.reports.today();
      var rows = reports.map(function (r) {
        var cs = r.compliance_status || "safe";
        return '<tr><td><a href="#report-detail/' + r.id + '">' + esc(r.title || r.query) + '</a></td><td style="color:var(--text-dim)">#' + r.watchlist_id + '</td><td>' + esc(r.risk_level || "?") + '</td><td>' + badge(cs, cs === "unsafe" ? "bad" : cs === "warning" ? "warn" : "good") + '</td><td style="color:var(--text-dim);font-size:12px">' + esc(fmtTime(r.created_at)) + '</td><td><a class="btn secondary sm" href="#report-detail/' + r.id + '">查看</a></td></tr>';
      }).join("");

      var body = document.querySelector(".page-body");
      body.innerHTML = [
        '<div class="card"><div class="card-pad">',
        reports.length
          ? '<div class="table-wrap"><table><thead><tr><th>标题</th><th>关注列表</th><th>风险</th><th>合规</th><th>创建时间</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>'
          : '<div class="empty-state"><div class="empty-state-icon">📅</div><p>今天还没有报告</p><p style="color:var(--text-muted);font-size:12px">先创建关注列表并添加关注项，然后点击“生成今日报告”。</p><a class="btn secondary sm" style="margin-top:4px" href="#watchlists">开始创建</a></div>',
        '</div></div>',
      ].join("");
    } catch (e) { showError("加载失败：" + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  /* ── Reports ── */
  window.reports = async function () {
    showError("");
    $container.innerHTML = pageHead("历史报告", '<button class="btn secondary" onclick="window.reports()">清空筛选</button>') + '<div class="page-body">' + loadingView() + '</div>';
    try {
      var reports = await API.reports.list();
      _renderReports(reports);
    } catch (e) { showError("加载失败：" + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  window.filterReports = async function () {
    showError("");
    var wlId = $("filterWlId").value.trim();
    var ticker = $("filterTicker").value.trim();
    var date = $("filterDate").value;
    var limit = Number($("filterLimit").value) || 20;
    document.querySelector(".page-body").innerHTML = loadingView();
    try {
      var reports = await API.reports.list({
        watchlist_id: wlId || undefined,
        ticker: ticker || undefined,
        date: date || undefined,
        limit: limit,
      });
      _renderReports(reports);
    } catch (e) { showError("筛选失败：" + e.message); }
  };

  function _renderReports(reports) {
    var rows = reports.map(function (r) {
      var cs = r.compliance_status || "safe";
      return '<tr><td><a href="#report-detail/' + r.id + '">' + esc(r.title || r.query) + '</a></td><td>' + badge(cs, cs === "unsafe" ? "bad" : cs === "warning" ? "warn" : "good") + '</td><td>' + esc(r.risk_level || "?") + '</td><td style="color:var(--text-dim);font-size:12px">' + esc(fmtTime(r.created_at)) + '</td></tr>';
    }).join("");

    var body = document.querySelector(".page-body");
    body.innerHTML = [
      '<div class="card" style="margin-bottom:16px"><div class="card-pad">',
      '<div class="form-grid">',
      '<div class="form-row">',
      '<input id="filterWlId" type="text" placeholder="关注列表 ID" style="flex:1" />',
      '<input id="filterTicker" type="text" placeholder="股票代码，例如 NVDA" style="flex:1" />',
      '<input id="filterDate" type="text" placeholder="日期 YYYY-MM-DD" style="flex:1" />',
      '<input id="filterLimit" type="number" value="20" min="1" max="100" placeholder="数量" style="width:80px;flex:none" />',
      '<button class="btn primary" onclick="App.filterReports()">搜索</button>',
      '</div></div>',
      '</div></div>',

      '<div class="card"><div class="card-pad">',
      reports.length
        ? '<div class="table-wrap"><table><thead><tr><th>标题</th><th>合规</th><th>风险</th><th>创建时间</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
        : '<div class="empty-state"><div class="empty-state-icon">📄</div><p>没有找到报告</p><p style="color:var(--text-muted);font-size:12px">可以调整筛选条件，或清空筛选查看全部报告。</p></div>',
      '</div></div>',
    ].join("");
  }

  /* ── Report Detail ── */
  window.reportDetail = async function () {
    showError("");
    var parts = (location.hash || "#").replace("#report-detail/", "").split("/");
    var reportId = Number(parts[0]);
    $container.innerHTML = pageHead("报告 #" + reportId, '', "#reports") + '<div class="page-body">' + loadingView() + '</div>';
    try {
      var report = await API.reports.get(reportId);
      var rp = report.report || report || {};
      var cs = rp.compliance_status || "safe";
      var disclaimer = report.disclaimer || rp.disclaimer || "";
      var items = await API.reports.items(reportId) || [];
      var marketSignals = rp.market_signals || [];
      var reportText = rp.report || rp.summary || "暂无报告内容。";
      var generatedAt = rp.generated_at || rp.created_at;
      var dash = function (v) {
        return v === undefined || v === null || v === ""
          ? "-"
          : String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      };
      var chainRisk = rp.risk_level || rp.overall_risk_level;
      var chainHtml = [
        ["candidate_news_count", rp.candidate_news_count],
        ["filtered_news_count", rp.filtered_news_count],
        ["analyzed_news_count", rp.analyzed_news_count],
        ["risk_level / overall_risk_level", chainRisk],
        ["compliance_status", rp.compliance_status],
        ["market_signal 数量", marketSignals.length],
        ["trace_id", rp.trace_id],
        ["generated_at", fmtTime(generatedAt)],
        ["source item 数量", items.length],
      ].map(function (row) {
        return '<div class="chain-summary-item"><span>' + esc(row[0]) + '</span><strong>' + dash(row[1]) + '</strong></div>';
      }).join("");

      var body = document.querySelector(".page-body");
      body.innerHTML = [
        cs === "unsafe" || cs === "warning"
          ? '<div class="notice" style="margin-bottom:16px">&#9888; Compliance: ' + esc(cs) + ' — this report may contain flagged content.</div>'
          : "",

        '<div class="card" style="margin-bottom:16px"><div class="card-pad">',
        '<div class="report-meta">',
        '<span><strong>风险等级：</strong> ' + esc(rp.risk_level || "?") + '</span>',
        '<span><strong>合规状态：</strong> ' + badge(cs, cs === "unsafe" ? "bad" : cs === "warning" ? "warn" : "good") + '</span>',
        '<span><strong>生成时间：</strong> ' + esc(fmtTime(generatedAt) || "-") + '</span>',
        '</div>',
        disclaimer ? '<div class="notice info" style="margin-bottom:14px">' + esc(disclaimer) + '</div>' : "",
        '<div class="report-box">' + formatReportText(reportText) + '</div>',
        '</div></div>',

        '<div class="section-title">生成摘要</div>',
        '<div class="card" style="margin-bottom:16px"><div class="card-pad"><div class="chain-summary-grid">' + chainHtml + '</div></div></div>',

        '<div class="section-title">市场观察信号（' + marketSignals.length + '）</div>',
        marketSignals.length
          ? '<div class="source-list" style="margin-bottom:16px">' + marketSignals.map(renderMarketSignalCard).join("") + '</div>'
          : '<div class="empty-state" style="min-height:80px">这份报告没有结构化 market_signals。</div>',

        '<div class="section-title">新闻来源（' + items.length + '）</div>',
        items.length
          ? '<div class="source-list">' + items.map(renderSourceCard).join("") + '</div>'
          : '<div class="empty-state" style="min-height:80px">这份报告没有结构化新闻来源。</div>',
      ].join("");
    } catch (e) { showError("加载失败：" + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  return {
    init: init,
    navigate: navigate,
    hideProgress: hideProgress,
    doLogin: window.doLogin,
    doRegister: window.doRegister,
    createWatchlist: window.createWatchlist,
    createJob: window.createJob,
    runOpportunityScan: window.runOpportunityScan,
    jobs: window.jobs,
    runJob: window.runJob,
    togglePreset: window.togglePreset,
    addBundle: window.addBundle,
    addCategory: window.addCategory,
    clearPending: window.clearPending,
    batchAddToWatchlist: window.batchAddToWatchlist,
    searchPresets: window.searchPresets,
    catClick: window.catClick,
    filterReports: window.filterReports,
  };
})();

document.addEventListener("DOMContentLoaded", function () { App.init(); });
