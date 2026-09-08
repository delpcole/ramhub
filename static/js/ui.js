// Small bits of behaviour that HTMX is not the right tool for.
// Anything that talks to the server should be an HTMX attribute instead.
(function () {
  "use strict";

  // Mobile navigation toggle.
  var toggle = document.querySelector("[data-menu-toggle]");
  var menu = document.getElementById("mobile-menu");
  if (!toggle || !menu) return;

  var iconOpen = toggle.querySelector("[data-menu-icon-open]");
  var iconClose = toggle.querySelector("[data-menu-icon-close]");

  function setOpen(open) {
    menu.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    if (iconOpen) iconOpen.hidden = open;
    if (iconClose) iconClose.hidden = !open;
  }

  toggle.addEventListener("click", function () {
    setOpen(menu.hidden);
  });

  // Escape closes the menu and returns focus to the toggle.
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !menu.hidden) {
      setOpen(false);
      toggle.focus();
    }
  });

  // Reset state if the viewport grows past the mobile breakpoint.
  window.matchMedia("(min-width: 768px)").addEventListener("change", function (event) {
    if (event.matches) setOpen(false);
  });
})();
