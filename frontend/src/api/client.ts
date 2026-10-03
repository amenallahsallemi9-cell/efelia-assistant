/** Erreur renvoyée par l'API au format `{ erreur: { code, message, details } }`. */
export class ErreurApi extends Error {
  readonly code: string;
  readonly statut: number;
  readonly details: unknown;

  constructor(statut: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ErreurApi";
    this.statut = statut;
    this.code = code;
    this.details = details;
  }
}

/** Appel JSON typé vers l'API (préfixe /api relayé par Vite ou nginx). */
export async function requete<T>(chemin: string, init?: RequestInit): Promise<T> {
  let reponse: Response;
  try {
    reponse = await fetch(`/api${chemin}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch {
    throw new ErreurApi(0, "RESEAU", "Impossible de joindre le serveur. Vérifiez votre connexion.");
  }
  const corps: unknown = await reponse.json().catch(() => null);
  if (!reponse.ok) {
    const erreur = (corps as { erreur?: { code?: string; message?: string; details?: unknown } })
      ?.erreur;
    throw new ErreurApi(
      reponse.status,
      erreur?.code ?? `HTTP_${reponse.status}`,
      erreur?.message ?? "Une erreur inattendue est survenue.",
      erreur?.details,
    );
  }
  return corps as T;
}
