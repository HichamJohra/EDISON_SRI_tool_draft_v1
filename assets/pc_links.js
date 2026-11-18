// Parallel-coordinates plots (class "pc-graph"): clicking a service code in an axis title opens its details in
// "2. Smart services". Plotly draws the axis titles as SVG text.axis-title; they can still be dragged to reorder.
document.addEventListener("click", function (e) {
    var t = e.target && e.target.closest ? e.target.closest("text.axis-title") : null;
    if (!t || !t.closest(".pc-graph")) { return; }
    var code = (t.textContent || "").trim();
    if (!/^[A-Z]{1,3}-\d+[a-z]?$/.test(code)) { return; }
    // Same navigation as dcc.Link (no page reload, session stores kept)
    window.history.pushState({}, "", "/services?code=" + encodeURIComponent(code));
    window.dispatchEvent(new CustomEvent("_dashprivate_pushstate"));
    window.scrollTo(0, 0);
});
