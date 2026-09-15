// Rambo, the RamHub mascot.
//
//   * Horns draw on as his section scrolls into view.
//   * Eyes follow the cursor; his head and horns tilt toward it at different
//     depths, so he reads as three-dimensional.
//   * He blinks, and breathes, now and then.
//   * Click, tap, Enter or Space gives him a nudge: a slow headbutt, and a new
//     line in his speech bubble. Every line comes from services.rambo_lines()
//     and is true of the live database.
//
// The nudge works with reduced motion too — the line still changes — it just
// doesn't animate. Nothing about Rambo is required to use the page.
(function () {
  "use strict";

  var rambo = document.querySelector("[data-rambo]");
  var bubble = document.querySelector("[data-rambo-bubble]");
  if (!rambo || !bubble) return;

  var linesEl = document.getElementById("rambo-lines");
  var lines = linesEl ? JSON.parse(linesEl.textContent) : [bubble.textContent];
  var lineIndex = 0;

  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var animated = !!window.gsap && !reducedMotion;

  function nextLine() {
    lineIndex = (lineIndex + 1) % lines.length;
    return lines[lineIndex];
  }

  // Without motion, a nudge is just the next line.
  if (!animated) {
    rambo.addEventListener("click", function () {
      bubble.textContent = nextLine();
    });
    return;
  }

  var EASE = "expo.out";
  var body = rambo.querySelector("[data-rambo-body]");
  var head = rambo.querySelector("[data-rambo-head]");
  var horns = rambo.querySelector("[data-rambo-horns]");
  var brow = rambo.querySelector("[data-rambo-brow]");
  var pupils = rambo.querySelectorAll("[data-rambo-pupil]");
  var lids = rambo.querySelectorAll("[data-rambo-lid]");
  var section = document.querySelector("[data-rambo-section]") || rambo;

  // ── Horns draw on with scroll ────────────────────────────────────────────
  if (window.ScrollTrigger) {
    gsap.to(rambo.querySelectorAll("[data-rambo-horn]"), {
      strokeDashoffset: 0,
      ease: "none",
      stagger: 0.04,
      scrollTrigger: { trigger: section, start: "top 80%", end: "center center", scrub: 1.5 },
    });
    gsap.fromTo(
      bubble,
      { opacity: 0, y: 16, scale: 0.92 },
      {
        opacity: 1,
        y: 0,
        scale: 1,
        duration: 1.4,
        ease: EASE,
        scrollTrigger: { trigger: section, start: "center 75%", once: true },
      }
    );
  }

  // ── Breathing: a slow idle so he never looks frozen ──────────────────────
  gsap.to(body, { y: -6, duration: 3.4, ease: "sine.inOut", yoyo: true, repeat: -1 });

  // ── Blinking, at uneven intervals ────────────────────────────────────────
  (function blink() {
    gsap
      .timeline({ delay: gsap.utils.random(2.5, 6) , onComplete: blink })
      .to(lids, { scaleY: 1, duration: 0.09, ease: "power2.in" })
      .to(lids, { scaleY: 0, duration: 0.16, ease: "power2.out" });
  })();

  // ── Eyes and head follow the cursor ──────────────────────────────────────
  if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
    var pupilX = Array.prototype.map.call(pupils, function (p) {
      return gsap.quickTo(p, "x", { duration: 0.6, ease: "power3.out" });
    });
    var pupilY = Array.prototype.map.call(pupils, function (p) {
      return gsap.quickTo(p, "y", { duration: 0.6, ease: "power3.out" });
    });
    var headTilt = gsap.quickTo(head, "rotation", { duration: 1.6, ease: "power3.out" });
    var headShift = gsap.quickTo(head, "x", { duration: 1.6, ease: "power3.out" });
    var hornTilt = gsap.quickTo(horns, "rotation", { duration: 2, ease: "power3.out" });
    var hornShift = gsap.quickTo(horns, "x", { duration: 2, ease: "power3.out" });

    window.addEventListener("pointermove", function (event) {
      var box = rambo.getBoundingClientRect();
      if (box.bottom < 0 || box.top > window.innerHeight) return; // offscreen: idle

      var dx = event.clientX - (box.left + box.width / 2);
      var dy = event.clientY - (box.top + box.height * 0.5);
      var distance = Math.hypot(dx, dy) || 1;
      var reach = Math.min(distance / 180, 1); // pupils hit the edge by ~180px away

      pupilX.forEach(function (to) { to((dx / distance) * 4.5 * reach); });
      pupilY.forEach(function (to) { to((dy / distance) * 4.5 * reach); });

      // Horns sit further back than the face, so they move more.
      var lean = gsap.utils.clamp(-1, 1, dx / (window.innerWidth / 2));
      headTilt(lean * 6);
      headShift(lean * 6);
      hornTilt(lean * 9);
      hornShift(lean * 12);
    });
  }

  // ── The nudge ────────────────────────────────────────────────────────────
  var nudging = false;
  rambo.addEventListener("click", function () {
    if (nudging) return;
    nudging = true;

    var line = nextLine();
    gsap
      .timeline({
        defaults: { ease: EASE },
        onComplete: function () {
          nudging = false;
        },
      })
      // Wind up...
      .to(body, { rotation: -4, y: 6, scale: 0.97, duration: 0.45, ease: "power2.in" }, 0)
      .to(brow, { y: -5, duration: 0.45 }, 0)
      // ...headbutt...
      .to(body, { rotation: 3, y: -10, scale: 1.05, duration: 0.5, ease: "back.out(2.4)" }, 0.45)
      .to(horns, { rotation: "+=6", duration: 0.5, ease: "back.out(3)" }, 0.45)
      // ...and settle, slowly.
      .to(body, { rotation: 0, y: 0, scale: 1, duration: 1.6, ease: "elastic.out(1, 0.45)" }, 0.95)
      .to(horns, { rotation: 0, duration: 1.8, ease: "elastic.out(1, 0.4)" }, 0.95)
      .to(brow, { y: 0, duration: 1 }, 0.95)
      // The bubble swaps its line at the moment of impact.
      .to(bubble, { opacity: 0, y: 6, scale: 0.94, duration: 0.3, ease: "power2.in" }, 0.2)
      .add(function () {
        bubble.textContent = line;
      }, 0.5)
      .to(bubble, { opacity: 1, y: 0, scale: 1, duration: 1, ease: "back.out(2)" }, 0.55);
  });
})();
