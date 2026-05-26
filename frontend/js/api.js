var API = (function () {
  var _baseUrl = localStorage.getItem("mkt_base_url") || "http://127.0.0.1:8010";
  var _token = localStorage.getItem("mkt_token") || "";

  function setBaseUrl(url) { _baseUrl = url.replace(/\/$/, ""); localStorage.setItem("mkt_base_url", _baseUrl); }
  function getBaseUrl() { return _baseUrl; }

  function setToken(t) { _token = t; if (t) localStorage.setItem("mkt_token", t); else localStorage.removeItem("mkt_token"); }
  function getToken() { return _token; }
  function isLoggedIn() { return !!_token; }

  function headers() {
    var h = { "Content-Type": "application/json" };
    if (_token) h["Authorization"] = "Bearer " + _token;
    return h;
  }

  async function request(method, path, body) {
    var opts = { method: method, headers: headers() };
    if (body) opts.body = JSON.stringify(body);
    var res = await fetch(_baseUrl + path, opts);
    var data;
    try { data = await res.json(); } catch (_) { data = {}; }
    if (!res.ok) {
      var err = new Error(data.detail || (res.status + " " + res.statusText));
      err.status = res.status;
      throw err;
    }
    return data;
  }

  return {
    setBaseUrl: setBaseUrl, getBaseUrl: getBaseUrl,
    setToken: setToken, getToken: getToken, isLoggedIn: isLoggedIn,

    auth: {
      register: function (email, password) { return request("POST", "/api/auth/register", { email: email, password: password }); },
      login: function (email, password) { return request("POST", "/api/auth/login", { email: email, password: password }); },
      me: function () { return request("GET", "/api/auth/me"); },
    },

    watchlists: {
      list: function () { return request("GET", "/api/watchlists"); },
      create: function (name) { return request("POST", "/api/watchlists", { name: name }); },
      items: function (wlId) { return request("GET", "/api/watchlists/" + wlId + "/items"); },
      addItem: function (wlId, payload) { return request("POST", "/api/watchlists/" + wlId + "/items", payload); },
      createJob: function (wlId) { return request("POST", "/api/watchlists/" + wlId + "/report-jobs"); },
    },

    jobs: {
      list: function (opts) {
        var qs = [];
        if (opts && opts.watchlist_id) qs.push("watchlist_id=" + opts.watchlist_id);
        if (opts && opts.status) qs.push("status=" + opts.status);
        var path = "/api/report-jobs" + (qs.length ? "?" + qs.join("&") : "");
        return request("GET", path);
      },
      get: function (id) { return request("GET", "/api/report-jobs/" + id); },
      run: function (id) { return request("POST", "/api/report-jobs/" + id + "/run"); },
    },

    reports: {
      list: function (opts) {
        var qs = [];
        if (opts && opts.watchlist_id) qs.push("watchlist_id=" + opts.watchlist_id);
        if (opts && opts.ticker) qs.push("ticker=" + encodeURIComponent(opts.ticker));
        if (opts && opts.date) qs.push("date=" + opts.date);
        if (opts && opts.limit) qs.push("limit=" + opts.limit);
        var path = "/api/reports" + (qs.length ? "?" + qs.join("&") : "");
        return request("GET", path);
      },
      today: function (wlId) {
        var path = "/api/reports/today" + (wlId ? "?watchlist_id=" + wlId : "");
        return request("GET", path);
      },
      get: function (id) { return request("GET", "/api/reports/" + id); },
      items: function (id) { return request("GET", "/api/reports/" + id + "/items"); },
    },
  };
})();
