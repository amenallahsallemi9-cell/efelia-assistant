-- Exécuté une seule fois, à la création du volume PostgreSQL.
-- Crée la base de test et active pgvector dans les deux bases.
CREATE DATABASE efelia_test;

CREATE EXTENSION IF NOT EXISTS vector;

\connect efelia_test
CREATE EXTENSION IF NOT EXISTS vector;
