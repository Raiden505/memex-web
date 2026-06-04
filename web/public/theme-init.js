(function () {
  try {
    var t = localStorage.getItem("theme");
    if (
      t === "dark" ||
      (t !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches)
    ) {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.setAttribute("data-theme", "light");
    }
  } catch (_) {}
})();
