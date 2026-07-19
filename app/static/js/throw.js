/* EcoSort-Search — animation de "jet" du produit vers la bonne poubelle.
 *
 * Au clic sur "Voir la poubelle" :
 *   1. On demande au serveur la catégorie du produit (/api/classify),
 *      car il faut connaître la poubelle CIBLE avant d'animer.
 *   2. Une copie de l'image du produit "vole" en arc (comme un vrai lancer,
 *      pas une ligne droite) depuis la carte jusqu'à la poubelle
 *      correspondante, accompagnée d'un son de lancer puis d'un son
 *      d'impact ; la poubelle fait un petit rebond de réception.
 *   3. On soumet ensuite le formulaire vers /classify (la catégorie déjà
 *      calculée est transmise en champs cachés pour ne pas classifier
 *      deux fois).
 *
 * Cas dégradés : si l'API échoue, si la poubelle cible est introuvable ou
 * si l'utilisateur préfère les animations réduites (prefers-reduced-motion),
 * on soumet le formulaire directement, sans animation ni son — l'appli
 * reste 100 % fonctionnelle sans JavaScript, le formulaire étant un vrai
 * <form> POST vers /classify.
 */
(function () {
  "use strict";

  // Durée totale du jet (assez longue pour bien voir l'objet partir de la
  // carte, monter en arc, puis atterrir dans la poubelle).
  var THROW_DURATION_MS = 950;
  var LANDING_OFFSET_MS = 260; // rebond + son d'impact déclenchés juste avant la fin de l'arc
  var NAVIGATE_DELAY_MS = 260; // petite pause après l'atterrissage avant de changer de page

  // Un seul AudioContext réutilisé pour toute la page (créé/relancé au
  // premier clic, dans le geste utilisateur, pour respecter les politiques
  // "autoplay" des navigateurs).
  var audioCtx = null;
  function getAudioContext() {
    var AudioCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtor) return null;
    if (!audioCtx) audioCtx = new AudioCtor();
    if (audioCtx.state === "suspended") audioCtx.resume();
    return audioCtx;
  }

  // Son de "lancer" : un souffle bref (bruit blanc filtré, en dégradé) —
  // pas besoin de fichier audio externe, tout est synthétisé.
  function playWhoosh(ctx) {
    if (!ctx) return;
    if (ctx.state === "suspended") ctx.resume();
    var duration = 0.32;
    var bufferSize = Math.floor(ctx.sampleRate * duration);
    var buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    var data = buffer.getChannelData(0);
    for (var i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize);
    }
    var noise = ctx.createBufferSource();
    noise.buffer = buffer;

    var filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.setValueAtTime(1900, ctx.currentTime);
    filter.frequency.exponentialRampToValueAtTime(450, ctx.currentTime + duration);
    filter.Q.value = 0.7;

    var gain = ctx.createGain();
    gain.gain.setValueAtTime(0.5, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

    noise.connect(filter).connect(gain).connect(ctx.destination);
    noise.start();
    noise.stop(ctx.currentTime + duration);
  }

  // Son d'"impact" (courte percussion grave) : joué au moment où l'objet
  // atterrit dans la poubelle.
  function playThud(ctx) {
    if (!ctx) return;
    if (ctx.state === "suspended") ctx.resume();
    var t = ctx.currentTime;
    var osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.setValueAtTime(170, t);
    osc.frequency.exponentialRampToValueAtTime(55, t + 0.14);

    var gain = ctx.createGain();
    gain.gain.setValueAtTime(0.6, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.2);

    osc.connect(gain).connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.22);
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".js-throw");
    if (!button) return;

    var form = button.closest("form.classify-form");
    if (!form) return;

    event.preventDefault();
    if (button.disabled) return;
    button.disabled = true;
    button.textContent = "Analyse...";

    // Créé/relancé DANS le geste utilisateur (le clic), même si le son
    // sera joué un peu plus tard (après la réponse de /api/classify).
    var ctx = getAudioContext();

    var product = {
      name: form.querySelector("[name=name]").value,
      price: form.querySelector("[name=price]").value,
      image: form.querySelector("[name=image]").value,
    };

    fetch("/api/classify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(product),
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        form.querySelector("[name=category]").value = data.category || "";
        form.querySelector("[name=confidence]").value = data.confidence != null ? data.confidence : "";
        animateThrowThenSubmit(form, data.category, ctx);
      })
      .catch(function () {
        // API indisponible : /classify refera la classification côté serveur.
        form.submit();
      });
  });

  function animateThrowThenSubmit(form, categoryKey, ctx) {
    var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var bin = categoryKey ? document.getElementById("bin-" + categoryKey) : null;
    var binImg = bin ? bin.querySelector("img") : null;
    var card = form.closest(".product-card");
    var productImg = card ? card.querySelector(".result-media img") : null;

    if (reducedMotion || !bin || !binImg || !productImg) {
      form.submit();
      return;
    }

    var from = productImg.getBoundingClientRect();
    var to = binImg.getBoundingClientRect();

    var clone = productImg.cloneNode(false);
    clone.className = "throw-clone";
    clone.style.left = from.left + "px";
    clone.style.top = from.top + "px";
    clone.style.width = from.width + "px";
    clone.style.height = from.height + "px";

    // Trajectoire : du centre de l'image produit vers l'ouverture (le haut)
    // de la poubelle cible. --tx/--ty/--throw-duration pilotent le
    // @keyframes throw-arc défini dans style.css.
    var dx = (to.left + to.width / 2) - (from.left + from.width / 2);
    var dy = (to.top + to.height * 0.2) - (from.top + from.height / 2);
    clone.style.setProperty("--tx", dx + "px");
    clone.style.setProperty("--ty", dy + "px");
    clone.style.setProperty("--throw-duration", THROW_DURATION_MS + "ms");

    document.body.appendChild(clone);
    playWhoosh(ctx);

    // Rebond de réception + son d'impact, calés juste avant la fin de l'arc.
    setTimeout(function () {
      bin.classList.add("bin-receiving");
      playThud(ctx);
    }, THROW_DURATION_MS - LANDING_OFFSET_MS);

    setTimeout(function () { form.submit(); }, THROW_DURATION_MS + NAVIGATE_DELAY_MS);
  }
})();
