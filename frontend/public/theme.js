// Applique le thème avant le premier rendu (évite le flash clair → sombre).
// Fichier séparé : la politique de sécurité (CSP) interdit les scripts en ligne.
try {
  var t = localStorage.getItem("theme");
  if (t === "dark" || (!t && matchMedia("(prefers-color-scheme: dark)").matches)) {
    document.documentElement.classList.add("dark");
  }
} catch (e) {}
