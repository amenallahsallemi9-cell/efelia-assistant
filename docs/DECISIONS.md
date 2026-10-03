# Décisions d'architecture et d'interprétation

Ce document trace les choix structurants du projet et leurs raisons. Il est complété à
chaque phase.

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

## D4 — Interprétations du règlement (validées par le porteur du projet)

| Point ambigu | Interprétation retenue |
|---|---|
| « 18 octobre 2026 à minuit » | Fin de la journée du 18 : reçu **avant** le 19/10/2026 00:00:00, heure de Paris (borne exclusive). |
| Date de réception | Champ de la fiche (date d'envoi de l'email). À défaut, l'horodatage du dépôt. |
| Nom de fichier non conforme | **Avertissement** seulement, sans effet sur le statut. |
| CV de plus de 2 pages, attestation non signée, certificat d'une autre année | A_COMPLETER |
| Lettre qui n'aborde pas les 3 thèmes | Avertissement (c'est une appréciation du LLM). |
| Certificat au mauvais nom ou d'un autre établissement | A_COMPLETER (pièce à fournir de nouveau). L'éligibilité se juge sur la fiche. |
| « Autre bourse d'études » | Toute bourse autre que la bourse CROUS sur critères sociaux rend le dossier NON_RECEVABLE. Le message invite à vérifier auprès d'EFELIA s'il s'agit d'une aide ponctuelle ou de mobilité. |
| 24 h d'IA | Sur déclaration (`heures_ia ≥ 24`, 24 incluses). Le certificat ne les mentionne pas. |
| Relevés de notes | Avertissement si l'année lue diffère de 2025-2026. |

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
