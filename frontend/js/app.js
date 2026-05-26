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
    try { await API.watchlists.createJob(wlId); showToast("Job created"); } catch (e) { showError(e.message); }
  };

  window.watchlistDetail = async function () {
    showError("");
    var parts = (location.hash || "#").replace("#watchlist-detail/", "").split("/");
    var wlId = Number(parts[0]);
    $container.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    try {
      var items = await API.watchlists.items(wlId);
      var rows = items.map(function (item) {
        return '<tr><td>' + esc(item.item_type || "ticker") + '</td><td>' + esc(item.symbol || "") + '</td><td>' + esc(item.keyword || "") + '</td><td>' + esc(item.display_name || "") + '</td></tr>';
      }).join("");

      var typeOptions = ["ticker", "company", "topic", "macro", "commodity", "custom"]
        .map(function (t) { return '<option value="' + t + '">' + t + '</option>'; }).join("");

      $container.innerHTML = [
        '<div class="panel">',
        '<div class="panel-head"><h2>Watchlist Items</h2><a href="#watchlists">&larr; Back</a></div>',
        '<div class="form-grid" style="margin-bottom:14px">',
        '<select id="addType">' + typeOptions + '</select>',
        '<input id="addSymbol" type="text" placeholder="Symbol (for ticker)" />',
        '<input id="addKeyword" type="text" placeholder="Keyword (required)" />',
        '<input id="addDisplay" type="text" placeholder="Display name" />',
        '<button class="btn primary" onclick="App.addWatchlistItem(' + wlId + ')">Add Item</button>',
        '</div>',
        '<div style="margin-bottom:14px">',
        '<button class="btn secondary" onclick="App.createJob(' + wlId + ')">Create Report Job</button>',
        '</div>',
        items.length ? '<div class="table-wrap"><table><thead><tr><th>Type</th><th>Symbol</th><th>Keyword</th><th>Display</th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '<div class="empty">No items. Add one above.</div>',
        '</div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); }
  };

  window.addWatchlistItem = async function (wlId) {
    showError("");
    var itemType = $("addType").value;
    var symbol = $("addSymbol").value.trim();
    var keyword = $("addKeyword").value.trim();
    var display = $("addDisplay").value.trim();
    if (!keyword) return showError("Keyword is required");
    try {
      await API.watchlists.addItem(wlId, {
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
        return '<tr><td>' + j.id + '</td><td>' + esc(j.status) + '</td><td>' + esc(j.job_type) + '</td><td>' + esc(j.created_at || "") + '</td><td>' +
          (j.status === "succeeded" && j.report_id ? '<a href="#report-detail/' + j.report_id + '">View Report</a> ' : "") +
          '<button class="btn secondary" onclick="App.runJob(' + j.id + ')">Run</button></td></tr>';
      }).join("");
      $container.innerHTML = [
        '<div class="panel"><div class="panel-head"><h2>Report Jobs</h2></div>',
        jobs.length ? '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Status</th><th>Type</th><th>Created</th><th>Actions</th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '<div class="empty">No jobs.</div>',
        '</div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); }
  };

  window.runJob = async function (jobId) {
    showError("");
    try { await API.jobs.run(jobId); showToast("Job running"); enqueue(window.jobs); } catch (e) { showError(e.message); }
  };

  window.reports = async function () {
    showError("");
    $container.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    try {
      var reports = await API.reports.list();
      var rows = reports.map(function (r) {
        var cs = r.compliance_status || "safe";
        return '<tr><td><a href="#report-detail/' + r.id + '">' + esc(r.title || r.query) + '</a></td><td>' + badge(cs, cs === "unsafe" ? "bad" : cs === "warning" ? "warn" : "good") + '</td><td>' + esc(r.risk_level || "?") + '</td><td>' + esc(r.created_at || "") + '</td></tr>';
      }).join("");
      $container.innerHTML = [
        '<div class="panel"><div class="panel-head"><h2>Reports</h2></div>',
        reports.length ? '<div class="table-wrap"><table><thead><tr><th>Title</th><th>Compliance</th><th>Risk</th><th>Created</th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '<div class="empty">No reports yet. Create a watchlist and run a job.</div>',
        '</div>',
      ].join("");
    } catch (e) { showError("Failed to load: " + e.message); }
  };

  window.reportDetail = async function () {
    showError("");
    var parts = (location.hash || "#").replace("#report-detail/", "").split("/");
    var reportId = Number(parts[0]);
    $container.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    try {
      var report = await API.reports.get(reportId);
      var rp = report.report || {};
      var cs = rp.compliance_status || "safe";
      var items = await API.reports.items(reportId);
      var apiItems = items || [];

      $container.innerHTML = [
        '<div class="panel"><div class="panel-head"><h2>' + esc(rp.title || rp.query || "Report") + '</h2><a href="#reports">&larr; Reports</a></div>',
        cs === "unsafe" || cs === "warning"
          ? '<div class="notice">&#9888; Compliance: ' + esc(cs) + ' -- this report may contain flagged content.</div>'
          : "",
        '<div><strong>Risk Level:</strong> ' + esc(rp.risk_level || "?") + '</div>',
        '<div><strong>Compliance:</strong> ' + badge(cs, cs === "unsafe" ? "bad" : cs === "warning" ? "warn" : "good") + '</div>',
        report.disclaimer ? '<div class="notice" style="background:rgba(59,130,246,0.08);border-color:rgba(59,130,246,0.2);color:#bae6fd;margin-top:10px">' + esc(report.disclaimer) + '</div>' : "",
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
  };
})();

document.addEventListener("DOMContentLoaded", function () { App.init(); });
