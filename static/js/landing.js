// Landing page motion: Lenis smooth scroll driving GSAP ScrollTrigger.
//
// Rules this file keeps:
//   * Slow and smooth — long durations, one shared cinematic ease.
//   * Reduced motion gets NO smooth scroll, parallax, or reveals. Content is
//     shown immediately and the page scrolls natively.
//   * Nothing is required: if this script never runs, the page is complete.
//   * The system cursor is never hidden; the follower is decoration only.
(function () {
  "use strict";

  var root = document.documentElement;
  if (!window.gsap || !window.ScrollTrigger || !window.Lenis) {
    root.classList.remove("motion-ready");
    return;
  }

  gsap.registerPlugin(ScrollTrigger);

  var EASE = "expo.out"; // matches --ease-cinematic
  var SLOW = 1.6;

  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion) {
    root.classList.remove("motion-ready");
    window.__landingReady = true;
    return;
  }

  // ── Smooth scroll, driven by GSAP's ticker so ScrollTrigger stays in sync ──
  var lenis = new Lenis({
    lerp: 0.075, // lower = slower, silkier catch-up (library default is 0.1)
    smoothWheel: true,
  });
  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add(function (time) {
    lenis.raf(time * 1000);
  });
  gsap.ticker.lagSmoothing(0);

  // In-page anchor links scroll through Lenis too.
  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    link.addEventListener("click", function (event) {
      var target = document.querySelector(link.getAttribute("href"));
      if (target) {
        event.preventDefault();
        lenis.scrollTo(target, { duration: 1.8 });
      }
    });
  });

  // ── Hero: headline rises out of its mask, then the rest fades in ─────────
  var hero = document.querySelector("[data-hero]");
  if (hero) {
    var intro = gsap.timeline({ defaults: { ease: EASE } });
    intro
      .to(hero.querySelectorAll("[data-line]"), { yPercent: 0, y: 0, duration: 1.8, stagger: 0.14 }, 0.2)
      .to(hero.querySelectorAll("[data-reveal]"), { opacity: 1, duration: 2.2, stagger: 0.12 }, 0.7)
      .fromTo(
        hero.querySelector("[data-cue-line]"),
        { scaleY: 0 },
        { scaleY: 1, duration: 1.4, repeat: -1, repeatDelay: 0.6, ease: "power2.inOut" },
        1.6
      );

    // The headline drifts up and dims as you leave the hero.
    gsap.to(hero.querySelector(".landing-inner"), {
      yPercent: -18,
      opacity: 0.15,
      ease: "none",
      scrollTrigger: { trigger: hero, start: "top top", end: "bottom top", scrub: 1.2 },
    });
  }

  // ── Parallax: each layer moves at its own depth ──────────────────────────
  // data-parallax="0.3" moves 30% of the section height; negative drifts the
  // other way. Scrub > 0 adds inertia so layers glide rather than snap.
  document.querySelectorAll("[data-parallax]").forEach(function (layer) {
    var depth = parseFloat(layer.getAttribute("data-parallax")) || 0;
    var section = layer.closest("section") || layer;
    gsap.fromTo(
      layer,
      { yPercent: depth * 40 },
      {
        yPercent: depth * -40,
        ease: "none",
        scrollTrigger: { trigger: section, start: "top bottom", end: "bottom top", scrub: 1.5 },
      }
    );
  });

  // ── Reveals outside the hero ─────────────────────────────────────────────
  gsap.utils.toArray("[data-reveal]").forEach(function (el) {
    if (hero && hero.contains(el)) return;
    gsap.fromTo(
      el,
      { opacity: 0, y: 48 },
      {
        opacity: 1,
        y: 0,
        duration: SLOW,
        ease: EASE,
        scrollTrigger: { trigger: el, start: "top 88%", once: true },
      }
    );
  });

  gsap.utils.toArray("section").forEach(function (section) {
    if (section === hero) return;
    var lines = section.querySelectorAll("[data-line]");
    if (!lines.length) return;
    gsap.to(lines, {
      yPercent: 0,
      y: 0,
      duration: 1.8,
      stagger: 0.14,
      ease: EASE,
      scrollTrigger: { trigger: section, start: "top 70%", once: true },
    });
  });

  // ── Numbers count up once, to their real values ──────────────────────────
  document.querySelectorAll("[data-count]").forEach(function (el) {
    var target = parseInt(el.getAttribute("data-count"), 10) || 0;
    var counter = { value: 0 };
    el.textContent = "0";
    gsap.to(counter, {
      value: target,
      duration: 2.4,
      ease: "power3.out",
      scrollTrigger: { trigger: el, start: "top 85%", once: true },
      onUpdate: function () {
        el.textContent = Math.round(counter.value).toLocaleString();
      },
    });
  });

  // ── Image expansion: the course page grows to fill the screen ────────────
  var stage = document.querySelector("[data-expand]");
  if (stage) {
    var panel = stage.querySelector("[data-expand-panel]");
    var expandScroll = { trigger: stage, start: "top top", end: "bottom bottom", scrub: 1.4 };
    gsap.fromTo(
      panel,
      { scale: 0.62, borderRadius: "24px" },
      { scale: 1, borderRadius: "10px", ease: "none", scrollTrigger: expandScroll }
    );
    // Opacity, not filter: it composites instead of repainting every frame.
    gsap.fromTo(
      stage.querySelector("[data-expand-dim]"),
      { opacity: 0.45 },
      { opacity: 0, ease: "none", scrollTrigger: expandScroll }
    );
    gsap.fromTo(
      stage.querySelector("[data-expand-content]"),
      { y: 60, opacity: 0.4 },
      {
        y: 0,
        opacity: 1,
        ease: "none",
        scrollTrigger: { trigger: stage, start: "top top", end: "60% bottom", scrub: 1.4 },
      }
    );
  }

  // ── Cursor and hover (precise pointers only) ─────────────────────────────
  if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
    var follower = document.createElement("div");
    follower.className = "cursor-follower";
    follower.setAttribute("aria-hidden", "true");
    document.body.appendChild(follower);

    var moveX = gsap.quickTo(follower, "x", { duration: 0.8, ease: "power3.out" });
    var moveY = gsap.quickTo(follower, "y", { duration: 0.8, ease: "power3.out" });

    window.addEventListener("pointermove", function (event) {
      gsap.to(follower, { opacity: 0.9, duration: 0.6, overwrite: "auto" });
      moveX(event.clientX - 16);
      moveY(event.clientY - 16);
    });
    document.addEventListener("pointerleave", function () {
      gsap.to(follower, { opacity: 0, duration: 0.6 });
    });

    document.querySelectorAll("a, button, .pillar").forEach(function (el) {
      el.addEventListener("pointerenter", function () {
        gsap.to(follower, { scale: 1.8, duration: 0.6, ease: "power3.out" });
      });
      el.addEventListener("pointerleave", function () {
        gsap.to(follower, { scale: 1, duration: 0.6, ease: "power3.out" });
      });
    });

    // Buttons lean gently toward the pointer.
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
  }

  window.__landingReady = true;
  window.addEventListener("load", function () {
    ScrollTrigger.refresh();
  });
})();
