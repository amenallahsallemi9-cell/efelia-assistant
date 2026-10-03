# EFELIA — Agent d'instruction des dossiers (Bourse Excellence 2026)

> Projet étudiant indépendant, non affilié à EFELIA. Le règlement officiel fait foi.

Application qui lit un dossier de candidature (PDF), en extrait les pièces avec un LLM et
instruit sa **recevabilité** (RECEVABLE / A_COMPLETER / NON_RECEVABLE) avec motifs, preuves
et conseils. Elle ne prédit **jamais** la décision du jury.

🚧 En cours de construction. Le README complet (architecture, captures, choix techniques)
arrive en phase 10.

## Démarrage rapide

Prérequis : Docker Desktop (compatible Apple Silicon).

```bash
cp .env.example .env   # sans clé Cohere : mode démo automatique
make up                # http://localhost:3000 — API : http://localhost:8000/docs
make test              # tests back + front, sans clé API ni réseau
```

`make` sans argument liste toutes les commandes.
