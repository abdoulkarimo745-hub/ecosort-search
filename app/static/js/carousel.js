/* EcoSort-Search — carousel du hero (pages recherche & guide).
 * Fondu automatique toutes les 5 s entre les diapositives ; les points en
 * bas permettent d'aller directement à une image. S'il n'y a pas de
 * carousel sur la page (ex. page classify), le script ne fait rien.
 * Respecte prefers-reduced-motion : pas de défilement automatique. */
(function () {
  "use strict";

  var INTERVAL_MS = 5000;

  var slides = document.querySelectorAll(".hero-slide");
  var dots = document.querySelectorAll(".carousel-dot");
  if (slides.length < 2) return;

  var current = 0;
  var timer = null;

  function show(index) {
    slides[current].classList.remove("is-active");
    if (dots[current]) dots[current].classList.remove("is-active");
    current = (index + slides.length) % slides.length;
    slides[current].classList.add("is-active");
    if (dots[current]) dots[current].classList.add("is-active");
  }

  function startAutoplay() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    timer = setInterval(function () { show(current + 1); }, INTERVAL_MS);
  }

  dots.forEach(function (dot) {
    dot.addEventListener("click", function () {
      if (timer) clearInterval(timer);
      show(parseInt(dot.dataset.slide, 10));
      startAutoplay();
    });
  });

  startAutoplay();
})();
