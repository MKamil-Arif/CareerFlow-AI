/* Applies the saved (or system) colour theme before the page paints, so there is no flash. */
(function () {
  var theme = null;
  try { theme = localStorage.getItem("careerflow-theme"); } catch (e) { /* storage blocked */ }
  if (!theme && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) theme = "dark";
  document.documentElement.dataset.theme = theme === "dark" ? "dark" : "light";
})();
