// Print / Save as PDF: fit every Plotly graph to the printed page width, then restore after printing.
(function () {
    function graphs() { return Array.prototype.slice.call(document.querySelectorAll(".js-plotly-plot")); }
    window.edisonBeforePrint = function () {
        if (!window.Plotly) { return; }
        graphs().forEach(function (g) {
            if (g.closest(".pc-scroll")) { return; }  // wide parallel plots keep their size
            g.dataset.printWidth = (g._fullLayout && g._fullLayout.width) || "";
            window.Plotly.relayout(g, { width: Math.min(g.parentElement.clientWidth || 680, 680) });
        });
    };
    window.edisonAfterPrint = function () {
        if (!window.Plotly) { return; }
        graphs().forEach(function (g) {
            if (g.dataset.printWidth) { window.Plotly.relayout(g, { width: Number(g.dataset.printWidth) }); }
        });
    };
    window.addEventListener("beforeprint", window.edisonBeforePrint);
    window.addEventListener("afterprint", window.edisonAfterPrint);
})();
