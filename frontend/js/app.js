var App = (function () {
  var $container = null;
  var $sidebarNav = null;
  var $sidebarFooter = null;

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
    "today": "today",
    "watchlists": "watchlists",
    "watchlist-detail": "watchlistDetail",
    "jobs": "jobs",
    "reports": "reports",
    "report-detail": "reportDetail",
  };

  var SVG = {
    today: '<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
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
    renderNav();
    navigate();

    window.addEventListener("hashchange", navigate);
    var toast = cls("div", "toast", "");
    toast.id = "toast";
    document.body.appendChild(toast);

    var toggleBtn = document.getElementById("sidebarToggle");
    var sidebar = document.querySelector(".sidebar");
    var saved = localStorage.getItem("sidebar_collapsed");
    if (saved === "1") sidebar.classList.add("collapsed");
    toggleBtn.addEventListener("click", function () {
      sidebar.classList.toggle("collapsed");
      localStorage.setItem("sidebar_collapsed", sidebar.classList.contains("collapsed") ? "1" : "0");
    });
  }

  function navigate() {
    var hash = (location.hash || "#").replace("#", "");
    var parts = hash.split("/");
    var route = parts[0];
    var page = routes[route] || routes[""];
    showError("");
    if (page !== "login" && page !== "register" && !API.isLoggedIn()) {
      location.hash = "#login";
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
      navItem("#today", SVG.today, "Today", route === "today"),
      navItem("#watchlists", SVG.watchlists, "Watchlists", route === "watchlists" || route === "" || route === "watchlist-detail"),
      navItem("#reports", SVG.reports, "Reports", route === "reports" || route === "report-detail"),
      '<div class="nav-divider"></div>',
      navItem("#jobs", SVG.jobs, "任务状态", route === "jobs"),
    ].join("");

    $sidebarFooter.innerHTML = isAuth
      ? '<a href="#login" onclick="API.setToken(\'\');location.hash=\'#login\'">' + SVG.logout + '<span>Logout</span></a>'
      : [
          '<a href="#login"' + (route === "login" ? ' class="active"' : '') + '><span style="margin-left:28px">Login</span></a>',
          '<a href="#register"' + (route === "register" ? ' class="active"' : '') + '><span style="margin-left:28px">Register</span></a>',
        ].join("");
  }

  function showToast(msg) {
    var el = document.getElementById("toast");
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
  function formatScore(value) {
    if (value === undefined || value === null || value === "") return "";
    var n = Number(value);
    if (isNaN(n)) return String(value);
    return n.toFixed(2);
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
      '<div class="auth-full"><div class="auth-card"><h2>Login</h2><p class="auth-desc">Sign in to your Financial Agents account</p>',
      '<div class="form-grid">',
      '<div><label class="form-label">Email</label><input id="loginEmail" type="text" placeholder="name@example.com" /></div>',
      '<div><label class="form-label">Password</label><input id="loginPassword" type="password" placeholder="Enter password" /></div>',
      '<button class="btn primary block" style="margin-top:4px" onclick="App.doLogin()">Sign in</button>',
      '<p class="form-hint" style="text-align:center">No account? <a href="#register">Create one</a></p>',
      '</div></div></div>',
    ].join("");
  };

  window.doLogin = async function () {
    showError("");
    try {
      var data = await API.auth.login($("loginEmail").value, $("loginPassword").value);
      API.setToken(data.access_token);
      showToast("Signed in successfully");
      renderNav();
      location.hash = "#watchlists";
    } catch (e) { showError("Login failed: " + e.message); }
  };

  window.register = function () {
    $container.innerHTML = [
      '<div class="auth-full"><div class="auth-card"><h2>Register</h2><p class="auth-desc">Create a new Financial Agents account</p>',
      '<div class="form-grid">',
      '<div><label class="form-label">Email</label><input id="regEmail" type="text" placeholder="name@example.com" /></div>',
      '<div><label class="form-label">Password</label><input id="regPassword" type="password" placeholder="Create a password" /></div>',
      '<button class="btn primary block" style="margin-top:4px" onclick="App.doRegister()">Create account</button>',
      '<p class="form-hint" style="text-align:center">Already have an account? <a href="#login">Sign in</a></p>',
      '</div></div></div>',
    ].join("");
  };

  window.doRegister = async function () {
    showError("");
    try {
      await API.auth.register($("regEmail").value, $("regPassword").value);
      showToast("Account created. Please sign in.");
      location.hash = "#login";
    } catch (e) { showError("Registration failed: " + e.message); }
  };

  /* ── Watchlists List ── */
  window.watchlists = async function () {
    showError("");
    $container.innerHTML = pageHead("Watchlists", '<button class="btn primary" onclick="App.createWatchlist(this)">新建关注列表</button>') + '<div class="page-body"><div class="spinner"></div></div>';
    try {
      var wls = await API.watchlists.list();
      var rows = wls.map(function (w) {
        return '<tr><td><a href="#watchlist-detail/' + w.id + '">' + esc(w.name) + '</a></td><td style="color:var(--text-dim)">' + esc(fmtTime(w.created_at)) + '</td><td><button class="btn secondary sm" onclick="App.createJob(' + w.id + ', this)">生成今日报告</button></td></tr>';
      }).join("");

      var body = document.querySelector(".page-body");
      body.innerHTML = [
        '<div class="card"><div class="card-pad">',
        '<div class="form-grid" style="margin-bottom:18px">',
        '<div class="form-row"><input id="wlName" type="text" placeholder="Watchlist name" style="flex:1" onkeydown="if(event.key===\'Enter\') App.createWatchlist()" /><button class="btn primary" onclick="App.createWatchlist(this)">创建关注列表</button></div>',
        '<div class="form-hint">创建后会直接进入详情页，继续添加关注项。</div>',
        '</div>',
        wls.length
          ? '<div class="table-wrap"><table><thead><tr><th>Name</th><th>Created</th><th style="width:100px"></th></tr></thead><tbody>' + rows + '</tbody></table></div>'
          : '<div class="empty-state"><div class="empty-state-icon">📋</div><p>No watchlists yet</p><button class="btn primary sm" style="margin-top:4px" onclick="document.getElementById(\'wlName\').focus()">+ Create your first watchlist</button></div>',
        '</div></div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
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
    try {
      var items = _currentWlId === Number(wlId) && Array.isArray(_currentItems)
        ? _currentItems
        : await API.watchlists.items(wlId);
      if (!items || !items.length) {
        showError("请先添加至少一个关注项，再生成今日报告");
        enqueue(function () { location.hash = "#watchlist-detail/" + wlId; });
        return;
      }

      showToast("正在生成今日报告...");
      var job = await API.watchlists.createJob(wlId);
      if (!job.id) throw new Error("报告任务创建成功，但未返回任务 ID");
      createdJobId = job.id;

      job = await API.jobs.run(job.id);
      var st = job.status || "";
      if (st === "succeeded" && job.report_id) {
        showToast("今日报告已生成");
        enqueue(function () { location.hash = "#report-detail/" + job.report_id; });
      } else if (st === "failed" || st === "dead") {
        showError("报告生成失败，请检查新闻源或稍后重试" + (job.error_message ? "：" + job.error_message : ""));
      } else if (job.id) {
        showToast("报告正在生成，可稍后查看");
        enqueue(function () { location.hash = "#jobs"; });
      } else {
        showToast("报告任务状态：" + (st || "unknown"));
      }
    } catch (e) {
      if (createdJobId) {
        try {
          var latest = await API.jobs.get(createdJobId);
          if (latest && latest.error_message) {
            showError("报告生成失败，请检查新闻源或稍后重试：" + latest.error_message);
            return;
          }
        } catch (_) {}
      }
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
    showToast("Added bundle: " + bundleName);
    window.watchlistDetail();
  };

  window.addCategory = function (cat) {
    WATCHLIST_PRESETS.filter(function (p) { return p.category === cat; }).forEach(function (p) {
      if (!_isPresetAdded(p) && !_isPresetPending(p)) {
        _pendingAdds.push({ item_type: p.item_type, symbol: p.symbol, keyword: p.keyword || p.label, display_name: p.display_name || p.label, name: p.display_name || p.label });
      }
    });
    showToast("Added category: " + cat);
    window.watchlistDetail();
  };

  window.clearPending = function () { _pendingAdds = []; window.watchlistDetail(); };

  window.batchAddToWatchlist = async function () {
    showError("");
    if (!_pendingAdds.length) return showToast("No items to add");
    var success = 0, failed = 0;
    for (var i = 0; i < _pendingAdds.length; i++) {
      var item = _pendingAdds[i];
      try { await API.watchlists.addItem(_currentWlId, item); success++; }
      catch (e) { showToast("Failed: " + (item.display_name || item.keyword) + " - " + e.message); failed++; }
    }
    _pendingAdds = [];
    showToast(success ? "已添加 " + success + " 个关注项，可以生成今日报告" + (failed ? "，" + failed + " 个失败" : "") : "未添加关注项");
    window.watchlistDetail();
  };

  window.watchlistDetail = async function () {
    showError("");
    var parts = (location.hash || "#").replace("#watchlist-detail/", "").split("/");
    _currentWlId = Number(parts[0]);
    $container.innerHTML = pageHead("Watchlist Detail", '<button class="btn primary" onclick="App.createJob(' + _currentWlId + ', this)">生成今日报告</button>', "#watchlists") + '<div class="page-body"><div class="spinner"></div></div>';
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
            return '<div class="bundle-card" onclick="App.addBundle(\'' + esc(b.name) + '\')"><span class="bundle-icon">' + emojis[bi] + '</span><div class="bundle-title">' + esc(b.name) + '</div><div class="bundle-desc">' + esc(b.desc) + '</div><span class="bundle-count">' + count + ' items</span></div>';
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
          currentHtml = '<div class="empty-state" style="min-height:60px;font-size:13px">No items yet. Add from recommendations below or create custom ones.</div>';
        }

        var chips;
        if (presets.length) {
          chips = '<div class="preset-grid">' + _renderPresetChips(presets, !!search) + '</div>';
        } else if (cat === "自定义关注") {
          chips = "";
        } else {
          chips = '<div class="empty-state" style="min-height:60px;font-size:13px">No matching items.</div>';
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
            '<button class="btn primary sm" onclick="App.batchAddToWatchlist()">Batch Add</button>' +
            '<button class="btn ghost sm" onclick="App.clearPending()">Clear</button>' +
            '</div></div>';
        }

        var customForm = [
          '<div class="form-grid">',
          '<div class="form-row"><select id="addType" style="flex:1">' + ["ticker","company","topic","macro","commodity","custom"].map(function(t){return '<option value="'+t+'">'+_typeLabel(t)+'</option>';}).join("") + '</select>',
          '<input id="addSymbol" type="text" placeholder="Symbol e.g. NVDA" style="flex:1" /></div>',
          '<input id="addKeyword" type="text" placeholder="Search keyword (required) · e.g. NVIDIA / AI chips / gold" />',
          '<input id="addDisplay" type="text" placeholder="Display name · e.g. 英伟达 / AI 芯片 / 黄金" />',
          '<button class="btn primary block" onclick="App.doCustomAdd()">Add Item</button>',
          '</div>',
        ].join("");

        var body = document.querySelector(".page-body");
        body.innerHTML = [
          _currentItems.length
            ? '<div class="summary-bar">Monitoring <span class="num">' + _currentItems.length + '</span> items' +
              (tickerCount ? ' · Stocks <span class="num">' + tickerCount + '</span>' : '') +
              (topicCount ? ' · Topics <span class="num">' + topicCount + '</span>' : '') +
              (macroCount ? ' · Macro <span class="num">' + macroCount + '</span>' : '') +
              (commodityCount ? ' · Commodities <span class="num">' + commodityCount + '</span>' : '') +
              '</div>'
            : '',

          WATCHLIST_BUNDLES.length ? '<div class="section-title">Quick Start</div>' + bundlesHtml : '',

          pendingHtml,

          '<div style="margin-bottom:14px"><input id="presetSearch" type="text" placeholder="Search companies, topics, keywords · e.g. NVIDIA, AI chips, Fed, gold" oninput="App.searchPresets()" value="" /></div>',

          '<div class="wl-grid">',
          '<div class="wl-side">' + sidebarHtml + '</div>',
          '<div>',
          (cat !== "自定义关注" && !search && presets.length ? '<button class="btn secondary sm" style="margin-bottom:12px" onclick="App.addCategory(\'' + esc(cat) + '\')">Add all in this category (' + presets.length + ' items)</button>' : ""),
          chips,

          '<collapsible><div class="head" onclick="this.parentElement.classList.toggle(\'open\')">Currently Monitoring (' + _currentItems.length + ' items)</div><div class="body">' + currentHtml + '</div></collapsible>',
          '<collapsible><div class="head" onclick="this.parentElement.classList.toggle(\'open\')">Custom Item</div><div class="body"><p class="form-hint" style="margin-bottom:8px">Add items not found in the preset library.</p>' + customForm + '</div></collapsible>',

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

    } catch (e) { showError("Failed to load: " + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  window.doCustomAdd = async function () {
    showError("");
    var itemType = document.getElementById("addType").value;
    var symbol = document.getElementById("addSymbol").value.trim();
    var keyword = document.getElementById("addKeyword").value.trim();
    var display = document.getElementById("addDisplay").value.trim();
    if (!keyword) return showError("Search keyword is required");
    try {
      await API.watchlists.addItem(_currentWlId, {
        item_type: itemType, symbol: symbol, keyword: keyword, display_name: display, name: display || keyword,
      });
      showToast("Item added");
      window.watchlistDetail();
    } catch (e) { showError(e.message); }
  };

  /* ── Jobs ── */
  window.jobs = async function () {
    showError("");
    $container.innerHTML = pageHead("任务状态", '') + '<div class="page-body"><div class="spinner"></div></div>';
    try {
      var jobs = await API.jobs.list();
      var rows = jobs.map(function (j) {
        var isDaily = j.job_type === "daily";
        var stBadge = j.status === "succeeded" ? "good" : j.status === "failed" || j.status === "dead" ? "bad" : j.status === "running" ? "info" : "warn";
        return '<tr>' +
          '<td style="font-family:var(--font-mono);font-size:12px">#' + j.id + '</td>' +
          '<td>' + badge(j.status, stBadge) + '</td>' +
          '<td>' + esc(j.job_type) + (isDaily ? ' <span class="badge info">daily</span>' : '') + '</td>' +
          '<td style="color:var(--text-dim)">' + esc(j.scheduled_for || "-") + '</td>' +
          '<td>' + (j.attempt_count || 0) + '/' + (j.max_attempts || 3) + '</td>' +
          '<td style="color:var(--red);font-size:12px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(j.error_message || "") + '</td>' +
          '<td style="color:var(--text-dim);font-size:12px">' + esc(fmtTime(j.created_at)) + '</td>' +
          '<td>' +
            (j.status === "succeeded" && j.report_id ? '<a href="#report-detail/' + j.report_id + '" style="margin-right:8px">Report #' + j.report_id + '</a>' : "") +
            '<button class="btn secondary sm" onclick="App.runJob(' + j.id + ')">手动运行</button>' +
          '</td></tr>';
      }).join("");

      var body = document.querySelector(".page-body");
      body.innerHTML = [
        '<div class="notice info" style="margin-bottom:16px">这里用于查看报告生成任务状态。普通用户通常只需要在关注列表中点击生成今日报告。</div>',
        '<div class="card"><div class="card-pad">',
        jobs.length
          ? '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Status</th><th>Type</th><th>Scheduled</th><th>Attempts</th><th>Error</th><th>Created</th><th>Actions</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
          : '<div class="empty-state"><div class="empty-state-icon">⚡</div><p>No jobs yet</p><p style="color:var(--text-muted);font-size:12px">Create a watchlist, add items, then click 生成今日报告.</p><a class="btn secondary sm" style="margin-top:4px" href="#watchlists">Go to Watchlists</a></div>',
        '</div></div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  window.runJob = async function (jobId) {
    showError("");
    try {
      var job = await API.jobs.run(jobId);
      var st = job.status || "";
      if (st === "succeeded" && job.report_id) {
        showToast("Job #" + jobId + " completed! Report #" + job.report_id);
      } else if (st === "failed" || st === "dead") {
        showToast("Job #" + jobId + " " + st + ": " + (job.error_message || "unknown error"));
      } else if (st === "running") {
        showToast("Job #" + jobId + " is running. Refresh to check status.");
      } else {
        showToast("Job #" + jobId + " status: " + st);
      }
      enqueue(window.jobs);
    } catch (e) { showError(e.message); }
  };

  /* ── Today ── */
  window.today = async function () {
    showError("");
    $container.innerHTML = pageHead("Today", '') + '<div class="page-body"><div class="spinner"></div></div>';
    try {
      var reports = await API.reports.today();
      var rows = reports.map(function (r) {
        var cs = r.compliance_status || "safe";
        return '<tr><td><a href="#report-detail/' + r.id + '">' + esc(r.title || r.query) + '</a></td><td style="color:var(--text-dim)">#' + r.watchlist_id + '</td><td>' + esc(r.risk_level || "?") + '</td><td>' + badge(cs, cs === "unsafe" ? "bad" : cs === "warning" ? "warn" : "good") + '</td><td style="color:var(--text-dim);font-size:12px">' + esc(fmtTime(r.created_at)) + '</td><td><a class="btn secondary sm" href="#report-detail/' + r.id + '">View</a></td></tr>';
      }).join("");

      var body = document.querySelector(".page-body");
      body.innerHTML = [
        '<div class="card"><div class="card-pad">',
        reports.length
          ? '<div class="table-wrap"><table><thead><tr><th>Title</th><th>Watchlist</th><th>Risk</th><th>Compliance</th><th>Created</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>'
          : '<div class="empty-state"><div class="empty-state-icon">📅</div><p>No reports today</p><p style="color:var(--text-muted);font-size:12px">Create a watchlist, add items, then click 生成今日报告.</p><a class="btn secondary sm" style="margin-top:4px" href="#watchlists">Get started</a></div>',
        '</div></div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  /* ── Reports ── */
  window.reports = async function () {
    showError("");
    $container.innerHTML = pageHead("Reports", '<button class="btn secondary" onclick="window.reports()">Clear</button>') + '<div class="page-body"><div class="spinner"></div></div>';
    try {
      var reports = await API.reports.list();
      _renderReports(reports);
    } catch (e) { showError("Failed to load: " + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  window.filterReports = async function () {
    showError("");
    var wlId = $("filterWlId").value.trim();
    var ticker = $("filterTicker").value.trim();
    var date = $("filterDate").value;
    var limit = Number($("filterLimit").value) || 20;
    document.querySelector(".page-body").innerHTML = '<div class="spinner"></div>';
    try {
      var reports = await API.reports.list({
        watchlist_id: wlId || undefined,
        ticker: ticker || undefined,
        date: date || undefined,
        limit: limit,
      });
      _renderReports(reports);
    } catch (e) { showError("Filter failed: " + e.message); }
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
      '<input id="filterWlId" type="text" placeholder="Watchlist ID" style="flex:1" />',
      '<input id="filterTicker" type="text" placeholder="Ticker e.g. NVDA" style="flex:1" />',
      '<input id="filterDate" type="text" placeholder="Date YYYY-MM-DD" style="flex:1" />',
      '<input id="filterLimit" type="number" value="20" min="1" max="100" placeholder="Limit" style="width:80px;flex:none" />',
      '<button class="btn primary" onclick="App.filterReports()">Search</button>',
      '</div></div>',
      '</div></div>',

      '<div class="card"><div class="card-pad">',
      reports.length
        ? '<div class="table-wrap"><table><thead><tr><th>Title</th><th>Compliance</th><th>Risk</th><th>Created</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
        : '<div class="empty-state"><div class="empty-state-icon">📄</div><p>No reports found</p><p style="color:var(--text-muted);font-size:12px">Try adjusting the filter criteria or clear filters to see all reports.</p></div>',
      '</div></div>',
    ].join("");
  }

  /* ── Report Detail ── */
  window.reportDetail = async function () {
    showError("");
    var parts = (location.hash || "#").replace("#report-detail/", "").split("/");
    var reportId = Number(parts[0]);
    $container.innerHTML = pageHead("Report #" + reportId, '', "#reports") + '<div class="page-body"><div class="spinner"></div></div>';
    try {
      var report = await API.reports.get(reportId);
      var rp = report.report || report || {};
      var cs = rp.compliance_status || "safe";
      var disclaimer = report.disclaimer || rp.disclaimer || "";
      var items = await API.reports.items(reportId) || [];
      var reportText = rp.report || rp.summary || "No report available.";
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
        '<span><strong>Risk Level:</strong> ' + esc(rp.risk_level || "?") + '</span>',
        '<span><strong>Compliance:</strong> ' + badge(cs, cs === "unsafe" ? "bad" : cs === "warning" ? "warn" : "good") + '</span>',
        '<span><strong>Generated:</strong> ' + esc(fmtTime(generatedAt) || "-") + '</span>',
        '</div>',
        disclaimer ? '<div class="notice info" style="margin-bottom:14px">' + esc(disclaimer) + '</div>' : "",
        '<div class="report-box">' + formatReportText(reportText) + '</div>',
        '</div></div>',

        '<div class="section-title">生成链路摘要</div>',
        '<div class="card" style="margin-bottom:16px"><div class="card-pad"><div class="chain-summary-grid">' + chainHtml + '</div></div></div>',

        '<div class="section-title">Sources (' + items.length + ')</div>',
        items.length
          ? '<div class="source-list">' + items.map(renderSourceCard).join("") + '</div>'
          : '<div class="empty-state" style="min-height:80px">No structured sources found for this report.</div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); if (document.querySelector(".page-body")) document.querySelector(".page-body").innerHTML = ''; }
  };

  return {
    init: init,
    navigate: navigate,
    doLogin: window.doLogin,
    doRegister: window.doRegister,
    createWatchlist: window.createWatchlist,
    createJob: window.createJob,
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
