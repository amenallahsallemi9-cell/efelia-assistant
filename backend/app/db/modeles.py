"""Modèles SQLAlchemy 2 (tables PostgreSQL)."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    Computed,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.modeles import (
    Confiance,
    MethodeExtraction,
    SourceMorceau,
    StatutPipeline,
    TypePiece,
    Verdict,
)

DIMENSION_EMBEDDING = 1024


def _enum(classe: type, nom: str) -> Enum:
    """Enum PostgreSQL stockant les *valeurs* (et non les noms) des StrEnum."""
    return Enum(classe, name=nom, values_callable=lambda e: [m.value for m in e])


class Base(DeclarativeBase):
    """Base déclarative commune."""


class Dossier(Base):
    """Dossier de candidature et informations déclarées par l'étudiant·e."""

    __tablename__ = "dossiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom: Mapped[str] = mapped_column(String(120))
    prenom: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    formation: Mapped[str] = mapped_column(String(255))
    inscrit_uca: Mapped[bool] = mapped_column(Boolean)
    heures_ia: Mapped[int] = mapped_column(Integer)
    alternance: Mapped[bool] = mapped_column(Boolean)
    autre_bourse: Mapped[bool] = mapped_column(Boolean)
    autre_bourse_libelle: Mapped[str | None] = mapped_column(String(255))
    bourse_crous: Mapped[bool] = mapped_column(Boolean, default=False)
    date_reception: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    nom_fichier: Mapped[str] = mapped_column(String(255))
    chemin_fichier: Mapped[str] = mapped_column(String(512))
    nb_pages: Mapped[int | None] = mapped_column(Integer)
    statut_pipeline: Mapped[StatutPipeline] = mapped_column(
        _enum(StatutPipeline, "statut_pipeline"), default=StatutPipeline.RECU, index=True
    )
    message_erreur: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pages: Mapped[list["Page"]] = relationship(
        back_populates="dossier", cascade="all, delete-orphan", order_by="Page.numero"
    )
    pieces: Mapped[list["Piece"]] = relationship(
        back_populates="dossier", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="dossier", cascade="all, delete-orphan", order_by="Decision.created_at"
    )


class Page(Base):
    """Page d'un dossier. Le texte est nul pour les pages sensibles (justificatifs)."""

    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("dossier_id", "numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dossiers.id", ondelete="CASCADE"), index=True
    )
    numero: Mapped[int] = mapped_column(Integer)
    texte: Mapped[str | None] = mapped_column(Text)
    methode: Mapped[MethodeExtraction] = mapped_column(
        _enum(MethodeExtraction, "methode_extraction")
    )
    type_piece: Mapped[TypePiece | None] = mapped_column(_enum(TypePiece, "type_piece"))
    confiance_classification: Mapped[float | None] = mapped_column(Float)
    sensible: Mapped[bool] = mapped_column(Boolean, default=False)

    dossier: Mapped[Dossier] = relationship(back_populates="pages")


class Piece(Base):
    """Pièce identifiée (regroupement de pages) et données structurées extraites."""

    __tablename__ = "pieces"

    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dossiers.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[TypePiece] = mapped_column(_enum(TypePiece, "type_piece"))
    pages: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    donnees_extraites: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confiance: Mapped[Confiance] = mapped_column(_enum(Confiance, "confiance"))

    dossier: Mapped[Dossier] = relationship(back_populates="pieces")


class Morceau(Base):
    """Morceau de texte indexé (dossier ou règlement) avec son embedding."""

    __tablename__ = "morceaux"
    __table_args__ = (
        Index(
            "ix_morceaux_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_morceaux_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[SourceMorceau] = mapped_column(
        _enum(SourceMorceau, "source_morceau"), index=True
    )
    dossier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dossiers.id", ondelete="CASCADE"), index=True
    )
    type_piece: Mapped[TypePiece | None] = mapped_column(_enum(TypePiece, "type_piece"))
    page: Mapped[int | None] = mapped_column(Integer)
    texte: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSION_EMBEDDING))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('french', texte)", persisted=True)
    )


class Decision(Base):
    """Décision de recevabilité. `statut_regles` fait foi (garde-fou)."""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dossiers.id", ondelete="CASCADE"), index=True
    )
    statut_regles: Mapped[Verdict] = mapped_column(_enum(Verdict, "verdict"))
    statut_propose_llm: Mapped[Verdict | None] = mapped_column(_enum(Verdict, "verdict"))
    garde_fou_declenche: Mapped[bool] = mapped_column(Boolean, default=False)
    motifs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    avertissements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    conseils: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    rapport: Mapped[str] = mapped_column(Text, default="")
    modele: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dossier: Mapped[Dossier] = relationship(back_populates="decisions")


class TraceAgent(Base):
    """Journal d'audit : un appel d'outil (ou une réponse) de l'agent."""

    __tablename__ = "traces_agent"

    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dossiers.id", ondelete="CASCADE"), index=True
    )
    ordre: Mapped[int] = mapped_column(Integer)
    outil: Mapped[str] = mapped_column(String(80))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    resultat: Mapped[Any] = mapped_column(JSONB, nullable=True)
    duree_ms: Mapped[int] = mapped_column(Integer)
    tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
