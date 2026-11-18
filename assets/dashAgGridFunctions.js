// Custom functions for dash-ag-grid (loaded automatically by Dash from /assets).
var dagfuncs = (window.dashAgGridFunctions = window.dashAgGridFunctions || {});

// Objectives & constraints table: a dropdown editor for rows with fixed options (SRI class, yes/no),
// a text editor otherwise.
dagfuncs.valueEditor = function (params) {
  if (params.data && params.data.options) {
    return { component: "agSelectCellEditor", params: { values: params.data.options } };
  }
  return { component: "agTextCellEditor" };
};
