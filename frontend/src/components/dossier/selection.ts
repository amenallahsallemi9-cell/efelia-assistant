/** Page affichée dans la visionneuse et extrait éventuel à surligner. */
export type Selection = { page: number; extrait: string | null };

/** Sélection à partir des preuves d'un contrôle (première preuve qui cite une page). */
export function selectionDepuisPreuves(
  preuves: { page: number | null; extrait: string | null }[],
): Selection | null {
  const preuve = preuves.find((p) => p.page !== null);
  return preuve?.page ? { page: preuve.page, extrait: preuve.extrait } : null;
}
