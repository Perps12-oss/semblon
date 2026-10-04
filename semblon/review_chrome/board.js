/* Cluster Review board — filters, sort, pagination, inspector. No identity math. */
(function () {
  "use strict";

  var PAGE_SIZE = 8;
  var CARD_THUMBS = 10;
  // Inspector shows every face in the group for comparison (card row stays capped).
  var INSPECTOR_THUMBS = 10000;

  function $(id) {
    return document.getElementById(id);
  }

  function parseBoard() {
    var el = $("semblon-board");
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (e) {
      return null;
    }
  }

  function fmt(n) {
    if (n === null || n === undefined || n === "") return "—";
    if (typeof n === "number") return n.toFixed(2);
    return String(n);
  }

  function fmtInt(n) {
    return String(n == null ? 0 : n);
  }

  function thumbHtml(t, cls) {
    cls = cls || "thumb";
    if (t && t.data_uri) {
      var img = '<img class="' + cls + '" src="' + t.data_uri + '" alt="' + esc(t.face_id || "") + '">';
      if (t.path_uri) {
        return '<a href="' + esc(t.path_uri) + '">' + img + "</a>";
      }
      return img;
    }
    return '<span class="thumb-missing" title="' + esc((t && t.face_id) || "") + '">file missing</span>';
  }

  function thumbRow(thumbs, limit) {
    thumbs = thumbs || [];
    var parts = [];
    var show = thumbs.slice(0, limit);
    for (var i = 0; i < show.length; i++) {
      parts.push(thumbHtml(show[i]));
    }
    var extra = thumbs.length - show.length;
    if (extra > 0) {
      parts.push('<span class="thumb-more">+' + extra + "</span>");
    }
    return parts.join("");
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function classifyRank(c) {
    if (c.classification === "review") return 0;
    if (c.classification === "check") return 1;
    if (c.classification === "good") return 2;
    return 3;
  }

  function sortClusters(list, mode) {
    var out = list.slice();
    if (mode === "largest") {
      out.sort(function (a, b) {
        return (b.face_count || 0) - (a.face_count || 0);
      });
    } else if (mode === "newest") {
      out.sort(function (a, b) {
        return String(b.cluster_id).localeCompare(String(a.cluster_id));
      });
    } else if (mode === "highest") {
      out.sort(function (a, b) {
        var am = a.min_intra;
        var bm = b.min_intra;
        if (am == null && bm == null) return 0;
        if (am == null) return 1;
        if (bm == null) return -1;
        return bm - am;
      });
    } else {
      out.sort(function (a, b) {
        var ra = classifyRank(a);
        var rb = classifyRank(b);
        if (ra !== rb) return ra - rb;
        var am = a.min_intra;
        var bm = b.min_intra;
        if (am == null && bm == null) return 0;
        if (am == null) return -1;
        if (bm == null) return 1;
        return am - bm;
      });
    }
    return out;
  }

  function sizeMatch(c, size) {
    if (size === "all") return true;
    var n = c.face_count || 0;
    if (size === "2-5") return n >= 2 && n <= 5;
    if (size === "6-10") return n >= 6 && n <= 10;
    if (size === "11-20") return n >= 11 && n <= 20;
    if (size === "21+") return n >= 21;
    return true;
  }

  function statusMatch(c, status) {
    if (status === "all") return true;
    if (status === "good") return c.classification === "good";
    if (status === "review") return c.classification === "review";
    if (status === "mixed") return c.classification === "review" || !!c.mixed_note;
    if (status === "low") {
      return c.classification === "review" && (c.min_intra == null || c.min_intra < 0.4);
    }
    return true;
  }

  var state = {
    board: null,
    page: 1,
    selectedId: null,
    selectedKind: null,
    nav: "clusters",
    status: "all",
    size: "all",
    sort: "priority",
    view: "all",
  };

  function filteredClusters() {
    var clusters = (state.board && state.board.clusters) || [];
    var out = [];
    for (var i = 0; i < clusters.length; i++) {
      var c = clusters[i];
      if (!statusMatch(c, state.status)) continue;
      if (!sizeMatch(c, state.size)) continue;
      if (state.view === "review" && c.classification !== "review") continue;
      if (state.view === "strong" && c.classification !== "good") continue;
      out.push(c);
    }
    return sortClusters(out, state.sort);
  }

  function clusterCard(c) {
    var cls = c.classification === "good" ? "good" : "review";
    var badge = cls === "good" ? "GOOD" : "REVIEW";
    var selected =
      state.selectedKind === "cluster" && state.selectedId === c.cluster_id
        ? " is-selected"
        : "";
    var meta =
      fmtInt(c.face_count) +
      " faces  ·  " +
      fmt(c.min_intra) +
      " worst pair  ·  Similarity range: " +
      fmt(c.sim_min) +
      " – " +
      fmt(c.sim_max);
    return (
      '<button type="button" class="cluster-card ' +
      cls +
      selected +
      '" data-kind="cluster" data-id="' +
      esc(c.cluster_id) +
      '">' +
      '<div class="card-top"><span class="card-title">Cluster ' +
      esc(c.display_index) +
      '</span><span class="badge ' +
      cls +
      '">' +
      badge +
      "</span></div>" +
      '<div class="card-meta">' +
      esc(meta) +
      "</div>" +
      '<div class="thumb-row">' +
      thumbRow(c.thumbs, CARD_THUMBS) +
      "</div></button>"
    );
  }

  function unassignedCard() {
    var u = (state.board && state.board.unassigned) || { face_count: 0, thumbs: [] };
    var selected =
      state.selectedKind === "unassigned" ? " is-selected" : "";
    return (
      '<button type="button" class="cluster-card unassigned' +
      selected +
      '" data-kind="unassigned" data-id="unassigned">' +
      '<div class="card-top"><span class="card-title">Unassigned</span></div>' +
      '<div class="card-meta">' +
      fmtInt(u.face_count) +
      " faces</div>" +
      '<div class="thumb-row">' +
      thumbRow(u.thumbs, CARD_THUMBS) +
      "</div></button>"
    );
  }

  function rejectedCard() {
    var r = (state.board && state.board.rejected) || { face_count: 0, thumbs: [] };
    if (!r.face_count) {
      return '<p class="none-line">none</p>';
    }
    var selected = state.selectedKind === "rejected" ? " is-selected" : "";
    return (
      '<button type="button" class="cluster-card' +
      selected +
      '" data-kind="rejected" data-id="rejected">' +
      '<div class="card-top"><span class="card-title">Rejected</span></div>' +
      '<div class="card-meta">' +
      fmtInt(r.face_count) +
      " faces · low_quality held out of clusters</div>" +
      '<div class="thumb-row">' +
      thumbRow(r.thumbs, CARD_THUMBS) +
      "</div></button>"
    );
  }

  function renderPagination(totalCards) {
    var el = $("pagination");
    var pages = Math.max(1, Math.ceil(totalCards / PAGE_SIZE));
    if (state.page > pages) state.page = pages;
    if (totalCards <= PAGE_SIZE) {
      el.innerHTML = "";
      return;
    }
    var html = "";
    html +=
      '<button type="button" class="page-btn" data-page="prev"' +
      (state.page <= 1 ? " disabled" : "") +
      ">‹</button>";
    for (var p = 1; p <= pages && p <= 8; p++) {
      html +=
        '<button type="button" class="page-btn' +
        (p === state.page ? " is-active" : "") +
        '" data-page="' +
        p +
        '">' +
        p +
        "</button>";
    }
    html +=
      '<button type="button" class="page-btn" data-page="next"' +
      (state.page >= pages ? " disabled" : "") +
      ">›</button>";
    el.innerHTML = html;
  }

  function renderBoard() {
    var root = $("board-root");
    if (!root || !state.board) return;
    var clusters = filteredClusters();
    var view = state.view;
    var showReview = view === "all" || view === "review";
    var showStrong = view === "all" || view === "strong";
    var showUnassigned = view === "all" || view === "unassigned";
    var showRejected = view === "rejected" || state.nav === "rejected";

    if (state.nav === "unassigned") {
      showReview = false;
      showStrong = false;
      showUnassigned = true;
      showRejected = false;
    } else if (state.nav === "rejected") {
      showReview = false;
      showStrong = false;
      showUnassigned = false;
      showRejected = true;
    } else if (state.nav === "worst") {
      showReview = true;
      showStrong = true;
      showUnassigned = false;
      showRejected = false;
      clusters = sortClusters(clusters, "priority");
    }

    var review = clusters.filter(function (c) {
      return c.classification === "review";
    });
    var strong = clusters.filter(function (c) {
      return c.classification === "good";
    });

    var cards = [];
    if (showReview) {
      for (var i = 0; i < review.length; i++) cards.push({ type: "cluster", item: review[i], section: "review" });
    }
    if (showStrong) {
      for (var j = 0; j < strong.length; j++) cards.push({ type: "cluster", item: strong[j], section: "strong" });
    }
    if (showUnassigned) {
      cards.push({ type: "unassigned", item: null, section: "unassigned" });
    }
    if (showRejected) {
      cards.push({ type: "rejected", item: null, section: "rejected" });
    }

    var start = (state.page - 1) * PAGE_SIZE;
    var pageCards = cards.slice(start, start + PAGE_SIZE);
    renderPagination(cards.length);

    function sectionHtml(id, title, cls, copy, body) {
      return (
        '<section class="priority-group ' +
        cls +
        '" id="' +
        id +
        '"><div class="group-head"><h2>' +
        title +
        "</h2><p>" +
        copy +
        '</p></div><div class="card-grid">' +
        body +
        "</div></section>"
      );
    }

    var html = "";
    var reviewBody = "";
    var strongBody = "";
    var unBody = "";
    var rejBody = "";
    var sawReview = false;
    var sawStrong = false;
    var sawUn = false;
    var sawRej = false;

    for (var k = 0; k < pageCards.length; k++) {
      var card = pageCards[k];
      if (card.type === "cluster" && card.section === "review") {
        reviewBody += clusterCard(card.item);
        sawReview = true;
      } else if (card.type === "cluster" && card.section === "strong") {
        strongBody += clusterCard(card.item);
        sawStrong = true;
      } else if (card.type === "unassigned") {
        unBody += unassignedCard();
        sawUn = true;
      } else if (card.type === "rejected") {
        rejBody += rejectedCard();
        sawRej = true;
      }
    }

    if (showReview) {
      html += sectionHtml(
        "review",
        "REVIEW REQUIRED (HIGHEST PRIORITY)",
        "review",
        "These clusters have low confidence, mixed faces or unusual similarity scores.",
        reviewBody || '<p class="none-line">none</p>'
      );
    }
    if (showStrong) {
      html += sectionHtml(
        "strong",
        "STRONG CLUSTERS",
        "strong",
        "These clusters look consistent. No immediate action needed. Still not persons until named after review.",
        strongBody || '<p class="none-line">none</p>'
      );
    }
    if (showUnassigned) {
      html += sectionHtml(
        "unassigned",
        "UNASSIGNED (" + fmtInt((state.board.unassigned && state.board.unassigned.face_count) || 0) + ")",
        "unassigned",
        "Faces that didn’t meet the clustering threshold. Video faces are observations (held out of clustering), not persons.",
        unBody || '<p class="none-line">none</p>'
      );
    }
    if (showRejected) {
      html += sectionHtml(
        "rejected",
        "REJECTED (" + fmtInt((state.board.rejected && state.board.rejected.face_count) || 0) + ")",
        "rejected",
        "rejected / low_quality stay held-out. Not clustered.",
        rejBody || '<p class="none-line">none</p>'
      );
    }

    // Keep DECISIONS anchor for forensic readers / tests.
    var decisions = state.board.decisions || [];
    html +=
      '<section id="decisions" class="priority-group rejected"><div class="group-head"><h2>DECISIONS (' +
      decisions.length +
      ')</h2><p>Human review. Merge does not create a person. rejected / low_quality stay held-out.</p></div>';
    if (!decisions.length) {
      html += '<p class="none-line">none</p>';
    } else {
      html += "<ol>";
      for (var d = 0; d < decisions.length; d++) {
        var dec = decisions[d];
        html +=
          "<li><strong>" +
          esc(dec.kind) +
          "</strong> " +
          esc(dec.cluster_id || dec.face_id || "") +
          ' <span class="card-meta">' +
          esc(dec.created_at || "") +
          "</span></li>";
      }
      html += "</ol>";
    }
    html += "</section>";

    root.innerHTML = html;
    void sawReview;
    void sawStrong;
    void sawUn;
    void sawRej;
  }

  function findCluster(id) {
    var clusters = (state.board && state.board.clusters) || [];
    for (var i = 0; i < clusters.length; i++) {
      if (clusters[i].cluster_id === id) return clusters[i];
    }
    return null;
  }

  function renderInspector() {
    var empty = $("inspector-empty");
    var body = $("inspector-body");
    var panel = $("inspector");
    if (!state.selectedId) {
      empty.classList.remove("hidden");
      body.classList.add("hidden");
      panel.classList.add("is-collapsed");
      return;
    }
    panel.classList.remove("is-collapsed");
    empty.classList.add("hidden");
    body.classList.remove("hidden");

    if (state.selectedKind === "cluster") {
      var c = findCluster(state.selectedId);
      if (!c) {
        state.selectedId = null;
        renderInspector();
        return;
      }
      var cls = c.classification === "good" ? "good" : "review";
      var badge = cls === "good" ? "GOOD" : "REVIEW";
      var disabled = document.body.getAttribute("data-mode") === "snapshot" ? " disabled" : "";
      var tip =
        document.body.getAttribute("data-mode") === "snapshot"
          ? ' title="Open Semblon Home to decide"'
          : "";
      var alert = "";
      if (c.min_intra == null || c.min_intra < 0.5) {
        alert =
          '<div class="mixed-alert"><strong>⚠ Possible mixed identities</strong><p>The worst pair has a similarity score of ' +
          fmt(c.min_intra) +
          ", which is below the usual threshold. These may be different people.</p></div>";
      }
      var wp = c.worst_pair_thumbs || [];
      var scoreCls = c.min_intra == null || c.min_intra < 0.5 ? "bad" : "ok";
      var nameLabel = c.named ? "Rename person" : "Name person";
      body.innerHTML =
        '<div class="inspector-head"><h2>Cluster ' +
        esc(c.display_index) +
        ' <span class="badge ' +
        cls +
        '">' +
        badge +
        '</span></h2><button type="button" class="btn-close" id="inspector-close" aria-label="Close">×</button></div>' +
        '<div class="inspector-meta">' +
        fmtInt(c.face_count) +
        " faces · Δ " +
        fmt(c.min_intra) +
        " worst pair · Similarity range: " +
        fmt(c.sim_min) +
        " – " +
        fmt(c.sim_max) +
        "</div>" +
        '<div class="face-grid">' +
        thumbRow(c.thumbs, INSPECTOR_THUMBS) +
        "</div>" +
        alert +
        '<div class="worst-pair"><h3>Worst pair (most dissimilar)</h3><div class="worst-row">' +
        (wp[0] ? thumbHtml(wp[0]) : '<span class="thumb-missing">—</span>') +
        (wp[1] ? thumbHtml(wp[1]) : '<span class="thumb-missing">—</span>') +
        '<div class="sim-block"><span class="label">Similarity</span><span class="score ' +
        scoreCls +
        '">' +
        fmt(c.min_intra) +
        "</span></div></div></div>" +
        '<p class="decision-prompt">Are these the same person?</p>' +
        '<div class="decision-row">' +
        '<button type="button" class="btn-same" data-op="same"' +
        disabled +
        tip +
        ">Same person</button>" +
        '<button type="button" class="btn-diff" data-op="different"' +
        disabled +
        tip +
        ">Different people</button></div>" +
        '<div class="quick-actions"><h3>Quick actions</h3>' +
        '<button type="button" class="btn-action" data-op="merge"' +
        disabled +
        tip +
        ">Merge with…</button>" +
        '<button type="button" class="btn-action" data-op="split"' +
        disabled +
        tip +
        ">Split cluster</button>" +
        '<button type="button" class="btn-action" data-op="name"' +
        disabled +
        tip +
        ">" +
        nameLabel +
        "</button></div>" +
        '<div class="details"><h3>Cluster details</h3><dl>' +
        "<dt>Cluster ID</dt><dd title=\"" +
        esc(c.cluster_id) +
        '">' +
        esc(c.display_index) +
        "</dd>" +
        "<dt>Status</dt><dd><span class=\"badge " +
        cls +
        '">' +
        badge +
        '</span><span class="not-person">Not a person yet</span></dd>' +
        "<dt>Faces</dt><dd>" +
        fmtInt(c.face_count) +
        "</dd>" +
        "<dt>Worst pair</dt><dd>" +
        fmt(c.min_intra) +
        "</dd>" +
        "<dt>Similarity range</dt><dd>" +
        fmt(c.sim_min) +
        " – " +
        fmt(c.sim_max) +
        "</dd>" +
        "<dt>Created</dt><dd>" +
        esc(c.created_at || state.board.run_started_at || "—") +
        "</dd></dl></div>" +
        '<button type="button" class="all-faces-link" data-op="all-faces">All faces in this cluster <span>›</span></button>';
      return;
    }

    if (state.selectedKind === "unassigned") {
      var u = state.board.unassigned || { face_count: 0, thumbs: [], tracks: [] };
      var disabledU = document.body.getAttribute("data-mode") === "snapshot" ? " disabled" : "";
      var tipU =
        document.body.getAttribute("data-mode") === "snapshot"
          ? ' title="Open Semblon Home to decide"'
          : "";
      var trackNote = "";
      if (u.tracks && u.tracks.length) {
        trackNote =
          '<p class="inspector-meta">Derived tracks: ' +
          u.tracks.length +
          ". Track id ≠ person id. untracked stays valid.</p>";
      }
      body.innerHTML =
        '<div class="inspector-head"><h2>Unassigned</h2><button type="button" class="btn-close" id="inspector-close">×</button></div>' +
        '<div class="inspector-meta">' +
        fmtInt(u.face_count) +
        " faces · not a person</div>" +
        trackNote +
        '<div class="face-grid">' +
        thumbRow(u.thumbs, INSPECTOR_THUMBS) +
        "</div>" +
        '<div class="quick-actions"><h3>Quick actions</h3>' +
        '<button type="button" class="btn-action" data-op="name-face"' +
        disabledU +
        tipU +
        ">Name person</button>" +
        '<button type="button" class="btn-action" data-op="ignore"' +
        disabledU +
        tipU +
        ">Ignore</button>" +
        '<button type="button" class="btn-action" data-op="rule-out"' +
        disabledU +
        tipU +
        ">Rule out</button></div>";
      return;
    }

    body.innerHTML =
      '<div class="inspector-head"><h2>Rejected</h2><button type="button" class="btn-close" id="inspector-close">×</button></div>' +
      '<div class="inspector-meta">Held out of clustering. not a person.</div>' +
      '<div class="face-grid">' +
      thumbRow((state.board.rejected && state.board.rejected.thumbs) || [], INSPECTOR_THUMBS) +
      "</div>";
  }

  function fillStats() {
    var s = (state.board && state.board.stats) || {};
    $("stat-photos").textContent = fmtInt(s.photos_processed);
    $("stat-faces").textContent = fmtInt(s.faces_detected);
    $("stat-clusters").textContent = fmtInt(s.clusters);
    $("stat-unassigned").textContent = fmtInt(s.unassigned);
    $("stat-rejected").textContent = fmtInt(s.rejected);
    $("n-clusters").textContent = fmtInt(s.clusters);
    $("n-good").textContent = fmtInt(s.good);
    $("n-review").textContent = fmtInt(s.review);
    $("n-mixed").textContent = fmtInt(s.mixed);
    $("n-low").textContent = fmtInt(s.low_confidence);

    var details = $("run-details");
    details.innerHTML =
      "<dl>" +
      "<dt>run_id</dt><dd>" +
      esc(state.board.run_id) +
      "</dd>" +
      "<dt>pack_id</dt><dd>" +
      esc(state.board.pack_id) +
      "</dd>" +
      "<dt>arch / execution</dt><dd>" +
      esc(state.board.arch || "—") +
      " / " +
      esc(state.board.execution || "—") +
      "</dd>" +
      "<dt>timings</dt><dd>" +
      esc(state.board.timings || "—") +
      "</dd>" +
      "<dt>identity</dt><dd>cluster → review → person → name. Clusters are not persons. STRONG means min_intra ≥ 0.50 (hypothesis).</dd>" +
      "</dl>";
  }

  function selectItem(kind, id) {
    state.selectedKind = kind;
    state.selectedId = id;
    renderBoard();
    renderInspector();
  }

  function bind() {
    document.querySelectorAll(".nav-item").forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.querySelectorAll(".nav-item").forEach(function (b) {
          b.classList.remove("is-active");
        });
        btn.classList.add("is-active");
        state.nav = btn.getAttribute("data-nav");
        state.page = 1;
        var titles = {
          overview: "Overview",
          clusters: "Clusters",
          unassigned: "Unassigned",
          rejected: "Rejected",
          worst: "Worst Pairs",
          stats: "Stats"
        };
        var pt = $("page-title");
        if (pt) pt.textContent = titles[state.nav] || "Clusters";
        if (state.nav === "stats" || state.nav === "overview") {
          $("run-details").classList.add("is-open");
        } else {
          $("run-details").classList.remove("is-open");
        }
        if (state.nav === "worst") {
          var worst = sortClusters((state.board && state.board.clusters) || [], "priority")[0];
          if (worst) selectItem("cluster", worst.cluster_id);
        }
        if (state.nav === "unassigned") selectItem("unassigned", "unassigned");
        if (state.nav === "rejected") selectItem("rejected", "rejected");
        renderBoard();
      });
    });

    document.querySelectorAll('input[name="status"]').forEach(function (el) {
      el.addEventListener("change", function () {
        state.status = el.value;
        state.page = 1;
        renderBoard();
      });
    });
    document.querySelectorAll('input[name="size"]').forEach(function (el) {
      el.addEventListener("change", function () {
        state.size = el.value;
        state.page = 1;
        renderBoard();
      });
    });
    $("sort-by").addEventListener("change", function () {
      state.sort = $("sort-by").value;
      state.page = 1;
      renderBoard();
    });
    $("view-filter").addEventListener("change", function () {
      state.view = $("view-filter").value;
      state.page = 1;
      renderBoard();
    });

    $("board-root").addEventListener("click", function (ev) {
      var card = ev.target.closest("[data-kind]");
      if (!card) return;
      selectItem(card.getAttribute("data-kind"), card.getAttribute("data-id"));
    });

    $("pagination").addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-page]");
      if (!btn || btn.disabled) return;
      var p = btn.getAttribute("data-page");
      if (p === "prev") state.page = Math.max(1, state.page - 1);
      else if (p === "next") state.page += 1;
      else state.page = parseInt(p, 10) || 1;
      renderBoard();
    });

    $("inspector").addEventListener("click", function (ev) {
      if (ev.target.id === "inspector-close") {
        state.selectedId = null;
        state.selectedKind = null;
        renderBoard();
        renderInspector();
        return;
      }
      var opBtn = ev.target.closest("[data-op]");
      if (!opBtn) return;
      if (document.body.getAttribute("data-mode") === "snapshot") return;
      if (window.semblonApply) {
        window.semblonApply({
          op: opBtn.getAttribute("data-op"),
          payload: {
            kind: state.selectedKind,
            id: state.selectedId,
            cluster_id: state.selectedKind === "cluster" ? state.selectedId : null,
          },
        });
      }
    });

    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
        state.selectedId = null;
        state.selectedKind = null;
        renderBoard();
        renderInspector();
      }
      if (ev.key === "j" || ev.key === "k") {
        var list = filteredClusters();
        if (!list.length) return;
        var idx = 0;
        for (var i = 0; i < list.length; i++) {
          if (list[i].cluster_id === state.selectedId) {
            idx = i;
            break;
          }
        }
        if (ev.key === "j") idx = Math.min(list.length - 1, idx + 1);
        else idx = Math.max(0, idx - 1);
        selectItem("cluster", list[idx].cluster_id);
      }
      if (ev.key === "Enter" && state.selectedId) renderInspector();
      if (document.body.getAttribute("data-mode") === "live") {
        if (ev.key === "s" && state.selectedKind === "cluster" && window.semblonApply) {
          window.semblonApply({ op: "same", payload: { cluster_id: state.selectedId } });
        }
        if (ev.key === "d" && state.selectedKind === "cluster" && window.semblonApply) {
          window.semblonApply({ op: "different", payload: { cluster_id: state.selectedId } });
        }
      }
    });
  }

  function boot() {
    state.board = parseBoard();
    if (!state.board) return;
    fillStats();
    bind();
    var focus =
      (document.body && document.body.getAttribute("data-focus-cluster")) ||
      (state.board && state.board.focus_cluster_id) ||
      "";
    if (focus) {
      selectItem("cluster", focus);
    } else {
      renderBoard();
      renderInspector();
    }
  }

  window.semblonReviewBoard = {
    reload: function (board) {
      state.board = board;
      var el = $("semblon-board");
      if (el) el.textContent = JSON.stringify(board);
      fillStats();
      renderBoard();
      renderInspector();
    },
    getState: function () {
      return state;
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
