var App = (function () {
  var $container = null;
  var $nav = null;

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

  function init() {
    var savedUrl = localStorage.getItem("mkt_base_url");
    if (savedUrl) API.setBaseUrl(savedUrl);
    $container = document.getElementById("mainContent");
    $nav = document.getElementById("navBar");
    renderNav();
    navigate();

    window.addEventListener("hashchange", navigate);
    var toast = cls("div", "toast", "");
    toast.id = "toast";
    document.body.appendChild(toast);
  }

  function navigate() {
    var hash = (location.hash || "#").replace("#", "");
    var parts = hash.split("/");
    var route = parts[0];
    var page = routes[route] || routes[""];
    showError("");
    if (page === "login" || page === "register") {
      renderNav();
    } else if (!API.isLoggedIn()) {
      location.hash = "#login";
      return;
    }
    renderNav();
    window[page]();
  }

  function renderNav() {
    var isAuth = API.isLoggedIn();
    var hash = (location.hash || "#").replace("#", "");
    $nav.innerHTML = [
      '<a href="#" class="brand">Financial Agents</a>',
      isAuth ? '<a href="#today" class="' + (hash === "today" ? "active" : "") + '">Today</a>' : "",
      isAuth ? '<a href="#watchlists" class="' + (hash === "watchlists" || hash === "" ? "active" : "") + '">Watchlists</a>' : "",
      isAuth ? '<a href="#reports" class="' + (hash === "reports" ? "active" : "") + '">Reports</a>' : "",
      isAuth ? '<a href="#jobs" class="' + (hash === "jobs" ? "active" : "") + '">Jobs</a>' : "",
      '<span style="flex:1"></span>',
      isAuth
        ? '<a href="#login" onclick="API.setToken(\'\');location.hash=\'#login\'">Logout</a>'
        : '<a href="#login" class="' + (hash === "login" ? "active" : "") + '">Login</a>',
      !isAuth ? '<a href="#register" class="' + (hash === "register" ? "active" : "") + '">Register</a>' : "",
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

  function badge(text, type) {
    return '<span class="badge ' + (type || "neutral") + '">' + esc(text) + '</span>';
  }
  function esc(s) { return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function h(c, t) { return "<" + c + ">" + esc(t) + "</" + c + ">"; }

  /* ── Pages ── */

  window.login = function () {
    $container.innerHTML = [
      '<div class="panel auth-panel"><h2>Login</h2>',
      '<div class="form-grid">',
      '<input id="loginEmail" type="text" placeholder="Email" />',
      '<input id="loginPassword" type="password" placeholder="Password" />',
      '<button class="btn primary block" onclick="App.doLogin()">Login</button>',
      '<p class="hint">No account? <a href="#register">Register</a></p>',
      '</div></div>',
    ].join("");
  };

  window.doLogin = async function () {
    showError("");
    try {
      var data = await API.auth.login($("loginEmail").value, $("loginPassword").value);
      API.setToken(data.access_token);
      showToast("Logged in");
      renderNav();
      location.hash = "#watchlists";
    } catch (e) { showError("Login failed: " + e.message); }
  };

  window.register = function () {
    $container.innerHTML = [
      '<div class="panel auth-panel"><h2>Register</h2>',
      '<div class="form-grid">',
      '<input id="regEmail" type="text" placeholder="Email" />',
      '<input id="regPassword" type="password" placeholder="Password" />',
      '<button class="btn primary block" onclick="App.doRegister()">Register</button>',
      '<p class="hint">Have an account? <a href="#login">Login</a></p>',
      '</div></div>',
    ].join("");
  };

  window.doRegister = async function () {
    showError("");
    try {
      await API.auth.register($("regEmail").value, $("regPassword").value);
      showToast("Registered. Please login.");
      location.hash = "#login";
    } catch (e) { showError("Register failed: " + e.message); }
  };

  window.watchlists = async function () {
    showError("");
    $container.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    try {
      var wls = await API.watchlists.list();
      var rows = wls.map(function (w) {
        return '<tr><td><a href="#watchlist-detail/' + w.id + '">' + esc(w.name) + '</a></td><td>' + esc(w.created_at || "") + '</td><td><button class="btn secondary" onclick="App.createJob(' + w.id + ')">Create Job</button></td></tr>';
      }).join("");
      $container.innerHTML = [
        '<div class="panel"><div class="panel-head"><h2>Watchlists</h2></div>',
        '<div class="form-grid" style="margin-bottom:14px">',
        '<input id="wlName" type="text" placeholder="Watchlist name" />',
        '<button class="btn primary" onclick="App.createWatchlist()">Create Watchlist</button>',
        '</div>',
        wls.length ? '<div class="table-wrap"><table><thead><tr><th>Name</th><th>Created</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '<div class="empty">No watchlists. Create one above.</div>',
        '</div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); }
  };

  window.createWatchlist = async function () {
    showError("");
    var name = $("wlName").value.trim();
    if (!name) return showError("Name required");
    try { await API.watchlists.create(name); showToast("Created"); window.watchlists(); } catch (e) { showError(e.message); }
  };

  window.createJob = async function (wlId) {
    showError("");
    try {
      var job = await API.watchlists.createJob(wlId);
      showToast("Job #" + (job.id || "?") + " created (" + (job.status || "pending") + "). Go to Jobs page to run it.");
      enqueue(function () { location.hash = "#jobs"; });
    } catch (e) { showError(e.message); }
  };

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

  function _renderPresetChips(presets) {
    return presets.map(function (p) {
      var isAdded = _isPresetAdded(p);
      var isPending = _isPresetPending(p);
      var cls = isAdded ? " added" : isPending ? " pending" : "";
      var label = isAdded ? "已添加" : isPending ? "待添加" : "选择";
      var onclick = isAdded ? "" : ('onclick="App.togglePreset(\'' + esc(p.item_type) + '\',\'' + esc(p.symbol) + '\',\'' + esc(p.keyword || p.label) + '\',\'' + esc(p.display_name || p.label) + '\')"');
      return '<span class="preset-chip' + cls + '" ' + onclick + '>' +
        '<span class="badge ' + (_typeBadge(p.item_type)) + '">' + esc(p.item_type) + '</span>' +
        esc(p.label) + ' <small>' + escape(label) + '</small></span>';
    }).join("");
  }

  function _typeBadge(t) {
    return t === "ticker" ? "info" : t === "macro" ? "warn" : t === "commodity" ? "good" : "neutral";
  }

  window.togglePreset = function (itemType, symbol, keyword, displayName) {
    var idx = _pendingAdds.findIndex(function (pp) { return pp.keyword === keyword && pp.item_type === itemType; });
    if (idx >= 0) {
      _pendingAdds.splice(idx, 1);
    } else {
      _pendingAdds.push({ item_type: itemType, symbol: symbol, keyword: keyword, display_name: displayName, name: displayName || keyword });
    }
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
    var success = 0;
    var failed = 0;
    for (var i = 0; i < _pendingAdds.length; i++) {
      var item = _pendingAdds[i];
      try {
        await API.watchlists.addItem(_currentWlId, item);
        success++;
      } catch (e) {
        showToast("Failed: " + (item.display_name || item.keyword) + " - " + e.message);
        failed++;
      }
    }
    _pendingAdds = [];
    showToast("Added " + success + " item(s)" + (failed ? ", " + failed + " failed" : ""));
    window.watchlistDetail();
  };

  window.watchlistDetail = async function () {
    showError("");
    var parts = (location.hash || "#").replace("#watchlist-detail/", "").split("/");
    _currentWlId = Number(parts[0]);
    $container.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    try {
      _currentItems = await API.watchlists.items(_currentWlId);
      var searchTerm = "";
      var curCat = WATCHLIST_CATEGORIES[0];

      function render(search, cat) {
        var presets = WATCHLIST_PRESETS;
        if (search) {
          var q = search.toLowerCase();
          presets = presets.filter(function (p) {
            return (p.label + " " + p.keyword + " " + p.display_name + " " + p.symbol + " " + p.category).toLowerCase().indexOf(q) >= 0;
          });
        } else if (cat && cat !== "自定义关注") {
          presets = presets.filter(function (p) { return p.category === cat; });
        } else if (cat === "自定义关注") {
          presets = [];
        }

        var itemsRows = _currentItems.map(function (item) {
          return '<tr><td>' + esc(item.item_type || "ticker") + '</td><td>' + esc(item.symbol || "") + '</td><td>' + esc(item.keyword || "") + '</td><td>' + esc(item.display_name || "") + '</td></tr>';
        }).join("");

        var tabs = WATCHLIST_CATEGORIES.map(function (c) {
          return '<span class="cat-tab' + (!search && cat === c ? " active" : "") + '" onclick="App.catClick(\'' + esc(c) + '\')">' + esc(c) + '</span>';
        }).join("");

        var chips;
        if (presets.length) {
          chips = '<div class="preset-grid">' + _renderPresetChips(presets) + '</div>';
        } else if (cat === "自定义关注") {
          chips = "";
        } else {
          chips = '<div class="empty" style="min-height:60px">No matching presets</div>';
        }

        var bundlesHtml = WATCHLIST_BUNDLES.map(function (b) {
          return '<div class="bundle-card" onclick="App.addBundle(\'' + esc(b.name) + '\')"><strong>' + esc(b.name) + '</strong><br><small style="color:var(--muted)">' + b.keys.join(", ") + '</small></div>';
        }).join("");

        var pendingHtml = "";
        if (_pendingAdds.length) {
          pendingHtml = '<div class="pending-bar"><div>' +
            _pendingAdds.map(function (pp) {
              return '<span class="pending-chip">' + esc(pp.display_name || pp.keyword) +
                ' <span class="remove" onclick="App.togglePreset(\'' + esc(pp.item_type) + '\',\'' + esc(pp.symbol) + '\',\'' + esc(pp.keyword) + '\',\'' + esc(pp.display_name) + '\')">x</span></span>';
            }).join("") +
            '</div><div style="display:flex;gap:8px">' +
            '<button class="btn primary" onclick="App.batchAddToWatchlist()">批量添加到关注列表</button>' +
            '<button class="btn secondary" onclick="App.clearPending()">清空待添加</button>' +
            '</div></div>';
        }

        $container.innerHTML = [
          '<div class="panel">',
          '<div class="panel-head"><h2>Watchlist Items</h2><a href="#watchlists">&larr; Back</a></div>',

          '<h3 style="margin:14px 0 6px">推荐组合</h3>',
          '<div class="bundle-grid">' + bundlesHtml + '</div>',

          '<h3 style="margin:14px 0 6px">选择新闻追踪板块</h3>',
          '<p class="hint" style="margin-bottom:10px">选择你关心的公司、行业、宏观政策和商品市场。系统会根据这些关注项自动抓取相关新闻并生成市场脉冲报告。</p>',
          '<input id="presetSearch" type="text" placeholder="搜索公司、主题、宏观关键词，例如 NVIDIA、AI 芯片、美联储、黄金" style="margin-bottom:10px" oninput="App.searchPresets()" value="' + esc(searchTerm) + '" />',
          '<div class="cat-tabs">' + tabs + '</div>',

          cat !== "自定义关注" && !search
            ? ('<button class="btn secondary" style="margin-bottom:10px" onclick="App.addCategory(\'' + esc(cat) + '\')">添加本板块全部</button>')
            : "",

          chips,

          cat === "自定义关注"
            ? ('<div class="form-grid" style="margin-bottom:14px">' +
               '<select id="addType">' + ["ticker","company","topic","macro","commodity","custom"].map(function(t){return '<option value="'+t+'">'+t+'</option>';}).join("") + '</select>' +
               '<input id="addSymbol" type="text" placeholder="Symbol (for ticker)" />' +
               '<input id="addKeyword" type="text" placeholder="Keyword (required)" />' +
               '<input id="addDisplay" type="text" placeholder="Display name" />' +
               '<button class="btn primary" onclick="App.addWatchlistItem()">Add Item</button>' +
               '</div>')
            : "",

          pendingHtml,

          '<div style="margin:14px 0">',
          '<button class="btn secondary" onclick="App.createJob(' + _currentWlId + ')">Create Report Job</button>',
          '</div>',

          _currentItems.length
            ? '<div class="table-wrap"><table><thead><tr><th>Type</th><th>Symbol</th><th>Keyword</th><th>Display</th></tr></thead><tbody>' + itemsRows + '</tbody></table></div>'
            : '<div class="empty">No items yet. Use above presets or add manually.</div>',
          '</div>',
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

    } catch (e) { showError("Failed to load: " + e.message); }
  };

  window.addWatchlistItem = async function () {
    showError("");
    var itemType = document.getElementById("addType").value;
    var symbol = document.getElementById("addSymbol").value.trim();
    var keyword = document.getElementById("addKeyword").value.trim();
    var display = document.getElementById("addDisplay").value.trim();
    if (!keyword) return showError("Keyword is required");
    try {
      await API.watchlists.addItem(_currentWlId, {
        item_type: itemType, symbol: symbol, keyword: keyword, display_name: display, name: display || keyword,
      });
      showToast("Item added");
      window.watchlistDetail();
    } catch (e) { showError(e.message); }
  };

  window.jobs = async function () {
    showError("");
    $container.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    try {
      var jobs = await API.jobs.list();
      var rows = jobs.map(function (j) {
        var isDaily = j.job_type === "daily";
        return '<tr>' +
          '<td>' + j.id + '</td>' +
          '<td>' + esc(j.status) + '</td>' +
          '<td>' + esc(j.job_type) + (isDaily ? ' <span class="badge info">daily</span>' : '') + '</td>' +
          '<td>' + esc(j.scheduled_for || "-") + '</td>' +
          '<td>' + (j.attempt_count || 0) + '/' + (j.max_attempts || 3) + '</td>' +
          '<td style="color:var(--red);font-size:12px">' + esc(j.error_message || "").substring(0, 50) + '</td>' +
          '<td>' + esc(j.created_at || "") + '</td>' +
          '<td>' +
            (j.status === "succeeded" && j.report_id ? '<a href="#report-detail/' + j.report_id + '">Report #' + j.report_id + '</a> ' : "") +
            '<button class="btn secondary" onclick="App.runJob(' + j.id + ')">Run</button>' +
          '</td></tr>';
      }).join("");
      $container.innerHTML = [
        '<div class="panel"><div class="panel-head"><h2>Report Jobs</h2></div>',
        jobs.length ? '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Status</th><th>Type</th><th>Scheduled</th><th>Attempts</th><th>Error</th><th>Created</th><th>Actions</th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '<div class="empty">No jobs.</div>',
        '</div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); }
  };

  window.runJob = async function (jobId) {
    showError("");
    try {
      var job = await API.jobs.run(jobId);
      var st = job.status || "";
      if (st === "succeeded" && job.report_id) {
        showToast("Job #" + jobId + " succeeded! Report #" + job.report_id + ". Click View Report.");
      } else if (st === "failed" || st === "dead") {
        showToast("Job #" + jobId + " " + st + ": " + (job.error_message || "unknown error"));
      } else if (st === "running") {
        showToast("Job #" + jobId + " is running. Refresh Jobs page to check status.");
      } else {
        showToast("Job #" + jobId + " status: " + st);
      }
      enqueue(window.jobs);
    } catch (e) { showError(e.message); }
  };

  window.today = async function () {
    showError("");
    $container.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    try {
      var reports = await API.reports.today();
      var rows = reports.map(function (r) {
        var cs = r.compliance_status || "safe";
        return '<tr><td><a href="#report-detail/' + r.id + '">' + esc(r.title || r.query) + '</a></td><td>' + esc(r.watchlist_id || "?") + '</td><td>' + esc(r.risk_level || "?") + '</td><td>' + badge(cs, cs === "unsafe" ? "bad" : cs === "warning" ? "warn" : "good") + '</td><td>' + esc(r.created_at || "") + '</td><td><a class="btn secondary" href="#report-detail/' + r.id + '">View</a></td></tr>';
      }).join("");
      $container.innerHTML = [
        '<div class="panel"><div class="panel-head"><h2>Today\'s Reports</h2></div>',
        reports.length
          ? '<div class="table-wrap"><table><thead><tr><th>Title</th><th>WL ID</th><th>Risk</th><th>Compliance</th><th>Created</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>'
          : '<div class="empty">No reports generated today yet. Create a watchlist, add items, create a job, and run it.</div>',
        '</div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); }
  };

  window.reports = async function () {
    showError("");
    $container.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    try {
      var reports = await API.reports.list();
      _renderReports(reports);
    } catch (e) { showError("Failed to load: " + e.message); }
  };

  window.filterReports = async function () {
    showError("");
    var wlId = $("filterWlId").value.trim();
    var ticker = $("filterTicker").value.trim();
    var date = $("filterDate").value;
    var limit = Number($("filterLimit").value) || 20;
    $container.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
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
      return '<tr><td><a href="#report-detail/' + r.id + '">' + esc(r.title || r.query) + '</a></td><td>' + badge(cs, cs === "unsafe" ? "bad" : cs === "warning" ? "warn" : "good") + '</td><td>' + esc(r.risk_level || "?") + '</td><td>' + esc(r.created_at || "") + '</td></tr>';
    }).join("");
    $container.innerHTML = [
      '<div class="panel"><div class="panel-head"><h2>Reports</h2><button class="btn secondary" onclick="window.reports()">Clear Filters</button></div>',
      '<div class="form-grid" style="margin-bottom:14px">',
      '<input id="filterWlId" type="text" placeholder="Watchlist ID" />',
      '<input id="filterTicker" type="text" placeholder="Ticker (e.g. NVDA)" />',
      '<input id="filterDate" type="text" placeholder="Date (YYYY-MM-DD)" />',
      '<input id="filterLimit" type="number" value="20" min="1" max="100" placeholder="Limit" />',
      '<button class="btn primary" onclick="App.filterReports()">Search</button>',
      '</div>',
      reports.length ? '<div class="table-wrap"><table><thead><tr><th>Title</th><th>Compliance</th><th>Risk</th><th>Created</th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '<div class="empty">No reports. Try adjusting filters.</div>',
      '</div>',
    ].join("");
  }

  window.reportDetail = async function () {
    showError("");
    var parts = (location.hash || "#").replace("#report-detail/", "").split("/");
    var reportId = Number(parts[0]);
    $container.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    try {
      var report = await API.reports.get(reportId);
      var rp = report.report || report || {};
      var cs = rp.compliance_status || "safe";
      var disclaimer = report.disclaimer || rp.disclaimer || "";
      var items = await API.reports.items(reportId);
      var apiItems = items || [];

      $container.innerHTML = [
        '<div class="panel"><div class="panel-head"><h2>' + esc(rp.title || rp.query || "Report") + '</h2><a href="#reports">&larr; Reports</a></div>',
        cs === "unsafe" || cs === "warning"
          ? '<div class="notice">&#9888; Compliance: ' + esc(cs) + ' -- this report may contain flagged content.</div>'
          : "",
        '<div><strong>Risk Level:</strong> ' + esc(rp.risk_level || "?") + '</div>',
        '<div><strong>Compliance:</strong> ' + badge(cs, cs === "unsafe" ? "bad" : cs === "warning" ? "warn" : "good") + '</div>',
        disclaimer ? '<div class="notice" style="background:rgba(59,130,246,0.08);border-color:rgba(59,130,246,0.2);color:#bae6fd;margin-top:10px">' + esc(disclaimer) + '</div>' : "",
        '<div class="report-box" style="margin-top:12px">' + esc(rp.summary || rp.report || "No summary.") + '</div>',
        '<h3 style="margin-top:18px">Sources</h3>',
        apiItems.length
          ? apiItems.map(function (item) {
              return '<div class="panel" style="margin-bottom:10px;padding:12px">' +
                h("strong", item.title || "Untitled") +
                (item.source_url ? ' <a href="' + esc(item.source_url) + '" target="_blank" rel="noopener">' + esc(item.source_name || "source") + '</a>' : ' <span>' + esc(item.source_name || "") + '</span>') +
                '<div style="margin-top:4px;color:var(--muted);font-size:13px">' + esc(item.summary || "") + '</div>' +
                (item.impact_analysis ? '<div style="margin-top:4px;font-size:13px">' + esc(item.impact_analysis) + '</div>' : "") +
                '<div style="margin-top:4px;font-size:12px;color:var(--muted-2)">risk: ' + esc(item.risk_level || "?") + ' | published: ' + esc(item.published_at || "?") + ' | score: ' + esc(item.relevance_score || "?") + '</div>' +
                '</div>';
            }).join("")
          : '<div class="empty">No structured news sources available.</div>',
        '</div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); }
  };

  return {
    init: init,
    navigate: navigate,
    doLogin: window.doLogin,
    doRegister: window.doRegister,
    createWatchlist: window.createWatchlist,
    createJob: window.createJob,
    addWatchlistItem: window.addWatchlistItem,
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
