export type Theme = "light" | "dark";

/** Thème actuellement appliqué au document. */
export function themeCourant(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/** Applique et mémorise le thème (préférence d'affichage locale uniquement). */
export function appliquerTheme(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
  try {
    localStorage.setItem("theme", theme);
  } catch {
    // Stockage indisponible (navigation privée) : le thème reste valable pour la session.
  }
}
