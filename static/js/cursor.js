// The cursor paints the page: a trailing green ring, a glow that follows it,
// gradient washes that shift as it crosses the screen, and a flashlight that
// brightens the hero's wall of course codes beneath it.
//
// Performance: glow, ring and washes move only with transform and opacity,
// which composite without repainting. The flashlight is the one repaint, and
// it is confined to the hero's code wall.
//
// Touch devices get a slow ambient drift instead. Reduced motion gets a still,
// centred background and none of this.
(function () {
  "use strict";

  if (!window.gsap) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  var glow = document.querySelector("[data-spotlight-glow]");
  var washB = document.querySelector("[data-spotlight-wash-b]");
  if (!glow || !washB) return;

  gsap.set(glow, { xPercent: -50, yPercent: -50, x: window.innerWidth / 2, y: window.innerHeight / 2 });

  var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  // ── Touch: nothing to follow, so the light drifts on its own ─────────────
  if (!finePointer) {
    gsap.to(glow, {
      x: window.innerWidth * 0.7,
      y: window.innerHeight * 0.35,
      duration: 9,
      ease: "sine.inOut",
      yoyo: true,
      repeat: -1,
    });
    gsap.to(washB, { opacity: 0.8, duration: 11, ease: "sine.inOut", yoyo: true, repeat: -1 });
    return;
  }

  // ── The green ring ───────────────────────────────────────────────────────
  var ring = document.createElement("div");
  ring.className = "cursor-follower";
  ring.setAttribute("aria-hidden", "true");
  document.body.appendChild(ring);

  var ringX = gsap.quickTo(ring, "x", { duration: 0.8, ease: "power3.out" });
  var ringY = gsap.quickTo(ring, "y", { duration: 0.8, ease: "power3.out" });

  // The glow trails further behind than the ring, so the light feels heavy.
  var glowX = gsap.quickTo(glow, "x", { duration: 2.2, ease: "power3.out" });
  var glowY = gsap.quickTo(glow, "y", { duration: 2.2, ease: "power3.out" });
  var washMix = gsap.quickTo(washB, "opacity", { duration: 2.4, ease: "power2.out" });

  // ── The flashlight over the hero's code wall ─────────────────────────────
  var wall = document.querySelector("[data-flashlight]");
  var light = { x: 50, y: 50, r: 0 };
  var paintWall = function () {
    wall.style.setProperty("--fx", light.x + "%");
    wall.style.setProperty("--fy", light.y + "%");
    wall.style.setProperty("--fr", light.r + "px");
  };

  window.addEventListener("pointermove", function (event) {
    var x = event.clientX;
    var y = event.clientY;

    gsap.to(ring, { opacity: 1, duration: 0.6, overwrite: "auto" });
    ringX(x - 16);
    ringY(y - 16);

    glowX(x);
    glowY(y);
    // Left edge shows the first gradient, right edge the second.
    washMix(Math.min(Math.max(x / window.innerWidth, 0), 1));

    if (wall) {
      var box = wall.getBoundingClientRect();
      var inside = y >= box.top && y <= box.bottom;
      gsap.to(light, {
        x: ((x - box.left) / box.width) * 100,
        y: ((y - box.top) / box.height) * 100,
        r: inside ? 260 : 0,
        duration: 1.2,
        ease: "power3.out",
        overwrite: "auto",
        onUpdate: paintWall,
      });
    }
  });

  document.addEventListener("pointerleave", function () {
    gsap.to(ring, { opacity: 0, duration: 0.6 });
  });

  // ── Engage: anything you can act on pulls the light in ───────────────────
  document.querySelectorAll("a, button, .pillar, [data-rambo]").forEach(function (el) {
    var isRambo = el.hasAttribute("data-rambo");
    el.addEventListener("pointerenter", function () {
      ring.classList.add("is-engaged");
      gsap.to(ring, { scale: isRambo ? 2.6 : 1.8, duration: 0.6, ease: "power3.out" });
      gsap.to(glow, { scale: isRambo ? 1.35 : 1.12, opacity: isRambo ? 0.6 : 0.45, duration: 1.4, ease: "power2.out" });
    });
    el.addEventListener("pointerleave", function () {
      ring.classList.remove("is-engaged");
      gsap.to(ring, { scale: 1, duration: 0.6, ease: "power3.out" });
      gsap.to(glow, { scale: 1, opacity: 0.35, duration: 1.6, ease: "power2.out" });
    });
  });

  // ── Buttons lean gently toward the pointer ───────────────────────────────
  document.querySelectorAll("[data-magnetic]").forEach(function (el) {
    el.addEventListener("pointermove", function (event) {
      var box = el.getBoundingClientRect();
      gsap.to(el, {
        x: (event.clientX - box.left - box.width / 2) * 0.18,
        y: (event.clientY - box.top - box.height / 2) * 0.3,
        duration: 0.8,
        ease: "power3.out",
      });
    });
    el.addEventListener("pointerleave", function () {
      gsap.to(el, { x: 0, y: 0, duration: 1.2, ease: "elastic.out(1, 0.5)" });
    });
  });
})();
