# Décisions d'architecture et d'interprétation

Ce document trace les choix structurants du projet et leurs raisons, phase par phase.

**Les trois décisions centrales** :
- pourquoi un garde-fou → [D1](#d1--le-statut-est-calculé-par-des-règles-pures-jamais-par-le-llm-garde-fou)
  et [D17](#d17--le-garde-fou-de-lagent-en-détail) ;
- pourquoi pgvector → [D14](#d14--pgvector-plutôt-quune-base-vectorielle-dédiée) ;
- pourquoi un worker → [D8](#d8--un-worker-séparé-rq--redis-pour-le-pipeline).

## D1 — Le statut est calculé par des règles pures, jamais par le LLM (garde-fou)

`backend/app/domain/regles.py` calcule le statut à partir de contrôles déterministes.
L'agent LLM explique, cite et conseille. Si le statut qu'il propose diffère, le statut
des règles s'applique et l'écart est tracé (`garde_fou_declenche`).

**Pourquoi :** un LLM peut se tromper ou être manipulé (injection de prompt dans un
document). Une décision administrative doit être reproductible, testable et auditable.

## D2 — Le domaine ne dépend d'aucune bibliothèque externe

`app/domain/` n'utilise que la bibliothèque standard (dataclasses, enum, zoneinfo). Le
YAML est lu et validé par Pydantic dans `app/core/reglement.py`, puis converti en objets
du domaine.

**Pourquoi :** les règles se testent en millisecondes, sans base de données ni réseau, et
mypy les vérifie en mode `strict`.

## D3 — Le règlement est dans un YAML versionné

`config/regles_2026.yaml` contient les seuils, les dates, les pièces et la **conséquence
de chaque contrôle**. Un code de contrôle manquant ou inconnu empêche l'application de
démarrer.

**Pourquoi :** l'édition 2027 se prépare en copiant le fichier, sans toucher au code.

## D4 — Interprétations du règlement

Les ambiguïtés du règlement ont été soumises au porteur du projet avant de coder. Il en a
**confirmé explicitement** deux (✔). Les autres sont les choix par défaut proposés, qu'il
n'a pas contestés : ils restent modifiables dans `config/regles_2026.yaml` (colonne
« conséquences »), sans toucher au code.

| Point ambigu | Interprétation retenue | |
|---|---|---|
| « 18 octobre 2026 à minuit » | Fin de la journée du 18 : reçu **avant** le 19/10/2026 00:00:00, heure de Paris (borne exclusive). | ✔ |
| Nom de fichier non conforme | **Avertissement** seulement, sans effet sur le statut. | ✔ |
| Date de réception | Champ de la fiche (date d'envoi de l'e-mail). À défaut, l'horodatage du dépôt. | |
| CV de plus de 2 pages, attestation non signée, certificat d'une autre année | A_COMPLETER | |
| Lettre qui n'aborde pas les 3 thèmes | Avertissement (c'est une appréciation du LLM). | |
| Certificat au mauvais nom ou d'un autre établissement | A_COMPLETER (pièce à fournir de nouveau). L'éligibilité se juge sur la fiche. | |
| « Autre bourse d'études » | Toute bourse autre que la bourse CROUS sur critères sociaux rend le dossier NON_RECEVABLE. Le message invite à vérifier auprès d'EFELIA s'il s'agit d'une aide ponctuelle ou de mobilité. | |
| 24 h d'IA | Sur déclaration (`heures_ia ≥ 24`, 24 incluses). Le certificat ne les mentionne pas. | |
| Relevés de notes | Avertissement si l'année lue diffère de 2025-2026. | |

## D5 — Une information indéterminée ne change jamais le statut

Un contrôle dont la donnée est illisible (signature non détectée, année absente…) donne
un résultat `INDETERMINE`. Ce résultat est affiché comme avertissement à vérifier par
un humain, mais il ne fait basculer le dossier ni vers A_COMPLETER ni vers
NON_RECEVABLE.

**Pourquoi :** une lecture imparfaite (OCR, mise en page) n'est pas la preuve qu'une
pièce est absente ou non conforme. Seule une non-conformité établie pèse sur le statut.

## D6 — Tolérances sur les noms

Les noms sont comparés sans tenir compte de la casse, des accents, des ligatures (œ, æ),
des tirets, des apostrophes ni des espaces dans les noms composés. Pour les prénoms,
l'ordre est libre et l'un des ensembles doit contenir l'autre : « Marie » correspond à
« Marie Claire Anne ». Une inversion nom/prénom est tolérée sur les documents, mais pas
dans le nom du fichier.

## D7 — Les justificatifs sensibles sont écartés dès l'extraction

`domain/sensibles.py` repère les justificatifs sociaux (avis d'imposition, RIB, bulletins
de paie, notifications de bourse) et de handicap (MDPH, RQTH, CMI, certificats médicaux)
par un **score de mots-clés**. Ce repérage a lieu **avant** tout stockage ou appel au
LLM. Pour ces pages, on ne garde que le type de document : le texte n'est jamais écrit
en base, jamais envoyé au LLM et jamais indexé.

Un indice isolé ne suffit pas : il faut un score d'au moins 2. Par exemple, un CV qui
mentionne « bénévole à la MDPH » n'est pas écarté. Une attestation sur l'honneur de
non-cumul n'est jamais considérée comme sensible, même si elle cite la bourse CROUS.

**Pourquoi :** si le tri était confié au LLM, il faudrait lui envoyer le texte, ce que le
RGPD du projet interdit. Le compromis : un justificatif mal repéré passe dans le circuit
normal (son texte serait lu), d'où des mots-clés larges et testés.

## D8 — Un worker séparé (RQ + Redis) pour le pipeline

L'OCR (environ 0,5 s par page scannée) et les appels au LLM (plusieurs secondes) se
font dans un processus `worker`. L'API répond tout de suite après le dépôt avec
l'identifiant du dossier. La progression est publiée sur Redis (pub/sub) puis diffusée
au navigateur en Server-Sent Events.

**Pourquoi RQ plutôt que Celery :** RQ suffit pour une seule file, se configure en
quelques lignes et fonctionne avec le même Redis. En cas d'échec, le dossier passe en
`ERREUR` avec un message sûr : soit un message prévu par le code, soit un message
générique, jamais un texte venant d'un document.

## D9 — Validation stricte des fichiers déposés

Le type réel du fichier est vérifié par sa signature `%PDF-`, sans se fier à l'extension
ni à l'en-tête HTTP. Sont aussi contrôlés : la taille (20 Mo), l'ouverture effective par
PyMuPDF, l'absence de mot de passe et le nombre de pages. Le fichier est stocké sous un
nom aléatoire (UUID), avec les droits `0600`, et écrit de façon atomique. Le nom
d'origine, réduit à son nom de base (sans chemin), n'est conservé que pour le contrôle
de format.

## D10 — Les fournisseurs passent par des interfaces abstraites, avec un FakeProvider réaliste

`providers/base.py` définit `LLMProvider`, `EmbeddingProvider` et `Reranker` avec des types
neutres (`Message`, `Outil`, `ReponseLLM`). Cohere n'apparaît que dans
`providers/cohere.py`. Le `FakeLLM` a trois modes :
- il rejoue un scénario (tests de l'agent) ;
- il appelle une fonction de réponse personnalisée ;
- par défaut, il répond aux tâches structurées avec les **mêmes heuristiques** que le
  secours (`services/heuristiques.py`).

Les embeddings factices projettent les mots sur 1024 dimensions par hachage : deux
textes au vocabulaire commun sont proches.

**Pourquoi :** le mode démo produit un vrai résultat sans clé, les tests sont
déterministes et hors ligne, et l'adaptateur Cohere est testé contre un client simulé.
**Limite :** les appels réels à Cohere ne sont pas exécutés en CI. Il faut une clé pour
les valider à la main.

## D11 — Les extraits cités par le LLM sont vérifiés

Chaque champ `extrait` renvoyé par le LLM est recherché dans le texte réel des pages,
après normalisation. S'il est introuvable, il est retiré et la confiance tombe à
« moyenne ». Sinon, on lui associe le numéro de page qui sert de preuve.

**Pourquoi :** une preuve affichée dans l'interface doit exister dans le document.
Un LLM peut paraphraser ou inventer une citation.

## D12 — Lecture : une relance, puis secours heuristique, et une confiance faible n'établit rien

Si la sortie JSON est invalide, on relance une fois en joignant l'erreur. Au second
échec, on se rabat sur l'heuristique avec `confiance = faible`. Les données d'une pièce
lue en confiance faible ne produisent **aucune non-conformité** : ses contrôles de
cohérence deviennent « indéterminés » (voir D5).

## D13 — La signature de l'attestation est déduite d'indices, pas du LLM

Le LLM ne voit que le texte et ne peut donc pas voir une signature. La décision se
prend dans cet ordre :
1. une mention de signature électronique suffit ;
2. sinon, la présence d'un tracé ou d'une image **sous** la mention « Signature » ou
   « Fait à » compte comme une signature ;
3. sans aucune marque visuelle ni mention, l'attestation est jugée non signée ;
4. dans les cas ambigus, comme une page scannée ou une mention sans marque, le contrôle
   reste indéterminé.

## D14 — pgvector plutôt qu'une base vectorielle dédiée

Les embeddings sont stockés dans PostgreSQL (`vector(1024)`) avec un index HNSW en
distance cosinus. La recherche plein texte française (`tsvector`, index GIN) se fait
dans la même table.

**Pourquoi :**
- une seule base à opérer, sauvegarder et purger (RGPD) ;
- la suppression d'un dossier efface ses vecteurs par `ON DELETE CASCADE` ;
- les filtres (dossier, source, modèle) s'écrivent en SQL ordinaire ;
- à l'échelle d'un appel à candidatures (quelques centaines de dossiers), PostgreSQL
  suffit largement.

**Filtres et index :** pgvector ≥ 0.8 permet le parcours itératif
(`hnsw.iterative_scan = relaxed_order`), qui évite de perdre des résultats quand on
filtre. Pour une requête très sélective (un seul dossier), Postgres choisit souvent
l'index B-tree sur `dossier_id`, ce qui est plus rapide. L'index HNSW sert les
recherches larges, comme celles dans le règlement.

## D15 — Recherche hybride avec fusion RRF, puis reranking

On récupère 20 candidats par similarité cosinus et 20 par texte intégral : la requête
est construite en OU, avec et sans accents, à partir de mots alphanumériques seulement,
pour qu'aucun opérateur venant de l'utilisateur n'atteigne `to_tsquery`. Les deux
listes sont fusionnées par rang réciproque (k = 60), puis le reranker choisit les
3 meilleurs passages.

Le reranker et les embeddings reçoivent le même texte enrichi : « section — passage ».
Si le reranker échoue, l'ordre de la fusion est conservé.

**Pourquoi :** les vecteurs captent le sens, le texte intégral attrape les termes exacts
(« ECTS », un nom propre), et la fusion par rang évite de comparer des scores
d'échelles différentes.

## D16 — Chaque morceau garde le nom du modèle qui l'a vectorisé

La colonne `modele_embedding` sert à filtrer toutes les recherches. Si l'on passe du
mode démo à Cohere, les anciens vecteurs, qui ne sont pas comparables, sont ignorés. Le
règlement est réindexé automatiquement quand son texte ou le modèle change.

## D17 — Le garde-fou de l'agent, en détail

L'agent LLM **ne décide jamais seul**. Il dispose de 9 outils et propose un statut via
`enregistrer_decision`. Ensuite :
1. le statut final est **toujours** recalculé par `domain/` (`instruire_par_regles`) ;
2. si la proposition diffère, `garde_fou_declenche = true` et le rapport l'affiche ;
3. l'outil renvoie au LLM le statut retenu, pour que son rapport reste cohérent ;
4. l'en-tête du rapport (verdict, motifs et preuves, points de vigilance, pièces à
   fournir) est **généré par le code**. Le texte du LLM n'apparaît que dans les sections
   « Conseils » et « Analyse de l'agent ».

D'autres protections viennent s'ajouter au garde-fou :
- **Accès** : un outil ne peut agir que sur le dossier en cours (`dossier_id` vérifié).
- **Minimisation** : l'adresse e-mail n'est jamais transmise au LLM.
- **Erreurs** : un outil inconnu, un JSON invalide ou un argument hors schéma devient
  `{"erreur": …}` renvoyé au LLM, qui peut se corriger. La boucle ne plante jamais.
- **Injection de prompt** : elle est détectée de façon déterministe et signalée dans
  `lire_fiche` et dans les avertissements de la décision, même si le LLM l'ignore.
- **Prédiction** : toute phrase qui estime les chances (« chances », « probabilité »,
  « %», « vous serez retenu·e »…) est retirée du texte du LLM et le retrait est signalé.
  On accepte quelques retraits en trop plutôt que de laisser passer une prédiction.
- **Résilience** : si le fournisseur est en panne, ou si l'agent n'a pas conclu au bout
  de 12 tours, une décision est quand même enregistrée à partir des règles, avec une
  note explicative.
- **Audit** : chaque tour de LLM (plan, jetons) et chaque appel d'outil (arguments,
  résultat, durée) est écrit dans `traces_agent`. Toutes les décisions successives sont
  conservées.

## D18 — Un agent scripté pour le mode démo

Sans clé, `FakeLLM` joue un agent scripté (`services/agent/demo.py`). Il suit la même
procédure, avec plusieurs appels d'outils par tour, déduit sa proposition des résultats
des outils et rédige un rapport à partir des données lues. Toute la chaîne (outils,
traces, garde-fou, rapport) fonctionne donc hors ligne, et le rapport indique
clairement qu'il a été produit en mode démo.

## D19 — Choix de l'API REST

- **Dépôt asynchrone** : `POST /api/dossiers` valide, stocke, puis répond **202** avec
  l'identifiant. Le pipeline tourne dans le worker. Le consentement au traitement des
  données est obligatoire (`CONSENTEMENT_REQUIS`), et le fichier est lu dans la limite
  de taille + 1 octet.
- **Temps réel (SSE)** : l'API s'abonne au canal Redis **avant** de lire l'état en base,
  pour ne manquer aucun événement entre les deux. Le flux s'arrête à INSTRUIT ou ERREUR,
  envoie un ping toutes les 15 s et dure au plus 15 minutes. nginx ne met pas la réponse
  en tampon (`proxy_buffering off`).
- **Pas de texte brut exposé** : l'API ne renvoie jamais le texte des pages, seulement les
  données structurées et les extraits servant de preuves.
- **Visionneuse** : l'aperçu PNG surligne l'extrait demandé, grâce à la couche texte du
  PDF. Les **pages sensibles sont toujours pixelisées** : l'outil d'instruction n'a pas à
  afficher un avis d'imposition ou un certificat médical, dont seul le type compte.
  Limite : une page scannée (OCR) ne peut pas être surlignée.
- **Relance** : `POST …/instruire` ne rejoue que l'agent si le dossier est déjà indexé,
  sinon tout le pipeline. Elle est refusée (409) pendant un traitement. L'historique des
  décisions est conservé.
- **Effacement** : `DELETE` supprime le dossier en base (la cascade efface les pages,
  pièces, embeddings, décisions et traces) puis le fichier. On vérifie d'abord que le
  chemin est bien dans le volume de stockage.
- **Endpoints ajoutés au cahier des charges** : `GET /api/dossiers/statistiques`
  (compteurs du tableau de bord) et `GET /api/reglement` (date limite pour le compte à
  rebours, pièces, nom de fichier attendu).
- **Erreurs** : toujours `{"erreur": {code, message, details}}` en français, avec des
  codes stables (`DOSSIER_INTROUVABLE`, `TYPE_NON_PDF`, `FICHE_INVALIDE`,
  `TRAITEMENT_EN_COURS`…).

## D20 — Interface : choix et vérifications

- **Composants** : style shadcn/ui (jetons de couleur dans `index.css`, Tailwind v4).
  Radix est utilisé pour les onglets, la fenêtre de confirmation et l'accordéon (focus et
  clavier gérés). Les éléments natifs (`select`, `details`, cases et boutons radio
  stylés) sont gardés quand ils suffisent.
- **Statuts** : toujours une icône, une couleur et un libellé, y compris pour les
  lecteurs d'écran (`sr-only`). Un contrôle « avertissement » s'affiche en ⚠️, jamais en ❌.
- **Visionneuse** : chaque contrôle qui cite une page est un bouton (`aria-pressed`). Un
  clic affiche la page et surligne l'extrait (aperçu rendu par l'API). Sur mobile, la
  page défile jusqu'à la visionneuse.
- **Temps réel** : `EventSource` sur `/evenements`. Le détail du dossier est aussi
  rafraîchi toutes les 4 s tant que le traitement n'est pas terminé, en secours.
- **Graphique** : une seule série en barres horizontales. Couleur validée au script
  (`#2563eb` en clair, `#4f8ef7` en sombre : bande de luminosité et contraste ≥ 3:1),
  valeur au bout de chaque barre, info-bulle au survol et au focus clavier, vue tableau.
- **Accessibilité** : audit **axe-core (WCAG 2.1 AA)** sur les 7 pages, en clair et en
  sombre : **0 violation**. S'y ajoutent un lien d'évitement, des libellés sur tous les
  champs, des annonces `aria-live` pour la progression et les résultats, et le respect
  de `prefers-reduced-motion`.
- **Performance** : les pages se chargent à la demande (`React.lazy`). L'accueil n'embarque
  ni le rendu Markdown ni Radix.
- **Rapport** : rendu par `react-markdown` avec `skipHtml`. Aucun HTML venant du LLM n'est
  interprété (pas d'injection de script possible par le rapport).

## D21 — Sécurité et RGPD : mesures de la phase 9

- **Aucune donnée de document dans les journaux.** Un test d'intégration parcourt tout
  le cycle (dépôt, pipeline, agent, consultation, aperçu surligné, éligibilité,
  effacement) et vérifie que les journaux ne contiennent ni texte de document, ni nom,
  ni e-mail. Les failles trouvées et corrigées :
  - le paramètre `?surligner=` (un extrait de document) aurait été écrit par le journal
    d'accès d'uvicorn et par celui de nginx. Uvicorn tourne désormais en
    `--no-access-log`, remplacé par un journal maison sans chaîne de requête, et nginx
    utilise un `log_format` basé sur `$uri` (sans `$args`) ;
  - les clients HTTP (`httpx`, `httpcore`, utilisés par le SDK Cohere) journalisent les
    URL complètes. Ils sont ramenés au niveau WARNING.
- **Conservation limitée** : au démarrage, le worker planifie une purge quotidienne
  (RQ). Elle efface les dossiers plus vieux que `RETENTION_JOURS` (180 par défaut) et
  les fichiers orphelins de plus d'une heure. Chaque exécution a son propre identifiant :
  sans cela, la purge en cours empêchait de planifier la suivante (bug corrigé, couvert
  par un test de non-régression). Une purge immédiate se lance avec `make purge`.
- **Limitation de débit** (Redis, fenêtre fixe, par IP) : 10 dépôts par heure et
  30 vérifications d'éligibilité par minute, configurables. Au-delà, l'API répond 429
  avec `Retry-After`. Si Redis est indisponible, les requêtes passent : la
  disponibilité prime, et l'incident est journalisé.
- **Adresse IP fiable** : nginx **remplace** `X-Forwarded-For` par l'adresse réelle, sans
  la compléter, et uvicorn lui fait confiance. Les ports de l'API et de l'interface ne
  sont publiés que sur `127.0.0.1`, et celui de la base ne l'est plus du tout : impossible
  d'usurper une IP en contactant l'API directement depuis le réseau.
- **En-têtes** : CSP stricte côté interface (`script-src 'self'`, d'où le script de thème
  sorti de `index.html`, `frame-ancestors 'none'`, `object-src 'none'`). L'API envoie
  `default-src 'none'`, sauf sur `/docs`. S'y ajoutent `nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer` et une `Permissions-Policy`. `style-src` garde
  `'unsafe-inline'` pour les largeurs calculées du graphique et de la barre de
  progression.
- **Rappels des mesures déjà en place** : validation stricte des fichiers (D9), justificatifs
  sensibles jamais lus (D7), aperçus sensibles pixelisés (D19), e-mail jamais transmis au
  LLM (D17), effacement complet en un appel (D19), conteneurs exécutés sans droits root.

## D22 — Leçons du premier passage avec le vrai Cohere

Le premier `make seed` avec une clé Cohere donnait les bons verdicts, mais **presque
uniquement grâce aux secours** (heuristiques, repli déterministe). Le diagnostic, appel
par appel, a révélé quatre problèmes. Chacun est corrigé et couvert par un test.

| Constat | Correctif |
|---|---|
| Sortie JSON refusée (HTTP 400 « non-supported constraint: minimum ») | Les contraintes (`minimum`, `maxLength`…) sont retirées du schéma **envoyé** à Cohere, et la réponse reste revalidée par Pydantic avec ses bornes. Les noms de champs ne sont jamais filtrés. |
| Clé d'essai limitée à 20 appels par minute (HTTP 429) | L'adaptateur relance sur les erreurs 429 et 5xx avec une attente exponentielle (4 → 60 s), ou le délai `Retry-After` s'il est fourni. Pas de relance sur 400 ou 422. |
| Erreur ponctuelle non reproductible (HTTP 422) en milieu d'instruction | Le tour de l'agent est rejoué une fois avant le repli déterministe. |
| Le LLM a mal recopié l'UUID du dossier (un caractère), reçu un refus d'accès et abandonné | Le refus rappelle l'identifiant du dossier en cours (ce n'est pas une fuite), le prompt demande de corriger et de réessayer, et si l'agent conclut sans décision, on lui rappelle **une fois** de terminer la procédure. |

Résultat : les 5 dossiers sont instruits par l'agent Cohere jusqu'au bout, sans repli,
avec une proposition identique au statut des règles. Le garde-fou n'a pas eu à
intervenir.

Au passage, un bug d'infrastructure est apparu : après un `make up` qui recrée le
conteneur `api`, nginx gardait l'ancienne adresse IP et répondait 502. nginx
réinterroge désormais le DNS de Docker toutes les 10 s (`resolver` + variable dans
`proxy_pass`).
