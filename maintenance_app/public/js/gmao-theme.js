
(function () {
  "use strict";

  var STORAGE_KEY = "gotech_gmao_theme";
  var THEMES = ["dark", "light"];

  function systemTheme() {
    try {
      return window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark";
    } catch (e) {
      return "dark";
    }
  }

  function savedTheme() {
    try {
      var value = localStorage.getItem(STORAGE_KEY);
      return THEMES.indexOf(value) !== -1 ? value : null;
    } catch (e) {
      return null;
    }
  }

  function currentTheme() {
    var value = document.documentElement.getAttribute("data-gmao-theme");
    return THEMES.indexOf(value) !== -1 ? value : null;
  }

  function setTheme(theme, persist) {
    if (THEMES.indexOf(theme) === -1) {
      theme = "dark";
    }

    document.documentElement.setAttribute("data-gmao-theme", theme);

    if (persist !== false) {
      try {
        localStorage.setItem(STORAGE_KEY, theme);
      } catch (e) {}
    }

    refreshToggle();

    try {
      window.dispatchEvent(
        new CustomEvent("gmao:theme-changed", {
          detail: { theme: theme }
        })
      );
    } catch (e) {}
  }

  function toggleTheme() {
    setTheme(currentTheme() === "light" ? "dark" : "light", true);
  }

  function refreshToggle() {
    var button = document.getElementById("gmao-theme-toggle");
    if (!button) return;

    var theme = currentTheme() || "dark";
    var icon = button.querySelector(".gmao-theme-toggle-icon");
    var label = button.querySelector(".gmao-theme-toggle-label");

    if (theme === "light") {
      if (icon) icon.textContent = "☀";
      if (label) label.textContent = "Light";
      button.title = "Switch to dark theme";
      button.setAttribute("aria-label", "Switch to dark theme");
    } else {
      if (icon) icon.textContent = "☾";
      if (label) label.textContent = "Dark";
      button.title = "Switch to light theme";
      button.setAttribute("aria-label", "Switch to light theme");
    }
  }

  function mountToggle() {
    var button = document.getElementById("gmao-theme-toggle");
    if (!button) return;

    button.addEventListener("click", toggleTheme);
    refreshToggle();
  }

  // Apply before page interaction to minimize theme flash.
  setTheme(savedTheme() || systemTheme(), false);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountToggle);
  } else {
    mountToggle();
  }

  window.GMAOTheme = {
    get: currentTheme,
    set: function (theme) { setTheme(theme, true); },
    toggle: toggleTheme
  };
})();
