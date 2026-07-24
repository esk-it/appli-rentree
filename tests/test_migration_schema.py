"""Test de migration auto-évolutive du schéma.

Reproduit le bug rencontré chez l'utilisateur : la table `arbitrage` avait
été créée par une version antérieure sans la colonne `date_decision`, ajoutée
au Lot 5 (v0.26.0). L'init_db doit détecter le drift et ajouter la colonne
via ALTER TABLE, sans perte de données.
"""
from __future__ import annotations

from sqlalchemy import inspect, text


def test_ajoute_colonne_manquante_arbitrage(session, tmp_db_path):
    """Une colonne nullable manquante dans arbitrage est ajoutée au démarrage."""
    from backend.database import _engine, _migrer_colonnes_manquantes
    from backend.models import Arbitrage

    # Simule l'état pré-v0.26 : drop date_decision de la table existante
    with _engine.begin() as conn:
        conn.execute(text("ALTER TABLE arbitrage DROP COLUMN date_decision"))

    # Vérifie que la colonne est bien absente
    inspector = inspect(_engine)
    cols = {c["name"] for c in inspector.get_columns("arbitrage")}
    assert "date_decision" not in cols, "setup KO : la colonne aurait dû être drop"

    # Relance la migration
    alters = _migrer_colonnes_manquantes()

    # La colonne est revenue
    inspector = inspect(_engine)
    cols = {c["name"] for c in inspector.get_columns("arbitrage")}
    assert "date_decision" in cols
    assert any("date_decision" in a for a in alters)


def test_migration_preserve_donnees(session, tmp_db_path):
    """Les rows existantes ne sont pas perdues quand on ajoute une colonne."""
    from backend.database import _engine, _migrer_colonnes_manquantes
    from backend.models import Arbitrage

    # Crée un arbitrage
    arb = Arbitrage(
        type_cas="collision_login",
        cle_cas="test-avant-migration",
        decision="suffixe:2",
        contexte_json="{}",
    )
    session.add(arb)
    session.commit()
    arb_id = arb.id

    # Simule un drift : drop date_decision puis re-migre
    with _engine.begin() as conn:
        conn.execute(text("ALTER TABLE arbitrage DROP COLUMN date_decision"))

    _migrer_colonnes_manquantes()

    # L'arbitrage est toujours là avec ses valeurs
    session.expire_all()
    retrouve = session.query(Arbitrage).filter_by(id=arb_id).one()
    assert retrouve.cle_cas == "test-avant-migration"
    assert retrouve.decision == "suffixe:2"
    # La nouvelle colonne est présente et null par défaut
    assert retrouve.date_decision is None


def test_pas_de_migration_si_schema_a_jour(session, tmp_db_path):
    """Aucun ALTER si toutes les colonnes sont déjà là."""
    from backend.database import _migrer_colonnes_manquantes

    alters = _migrer_colonnes_manquantes()
    assert alters == []


def test_init_db_relance_migration(tmp_db_path):
    """init_db exécute la migration après create_all — flux réel du démarrage."""
    from backend.database import _engine, init_db
    from sqlalchemy import inspect

    # Drop la colonne pour simuler l'état ancien
    with _engine.begin() as conn:
        conn.execute(text("ALTER TABLE arbitrage DROP COLUMN date_decision"))

    # Relance init_db comme au démarrage du sidecar
    init_db()

    inspector = inspect(_engine)
    cols = {c["name"] for c in inspector.get_columns("arbitrage")}
    assert "date_decision" in cols


def test_drift_nullability_recreation_si_vide(session, tmp_db_path):
    """Une colonne dont la nullabilité diverge → table recréée si vide.

    Reproduit le vrai bug : ancienne base avec `arbitrage.decision NOT NULL`,
    modèle actuel avec `decision` nullable → tentative d'INSERT avec None
    lève IntegrityError. La migration doit détecter et recréer la table.
    """
    from backend.database import _engine, _recreer_tables_vides_avec_drift
    from backend.models import Arbitrage

    # Recrée la table arbitrage avec la vieille contrainte NOT NULL sur decision
    with _engine.begin() as conn:
        conn.execute(text("DROP TABLE arbitrage"))
        conn.execute(
            text(
                """
                CREATE TABLE arbitrage (
                    id INTEGER PRIMARY KEY,
                    type_cas VARCHAR(30) NOT NULL,
                    cle_cas VARCHAR(300) NOT NULL UNIQUE,
                    decision VARCHAR(100) NOT NULL,
                    contexte_json TEXT NOT NULL,
                    date_creation DATETIME NOT NULL,
                    date_decision DATETIME,
                    note VARCHAR(500)
                )
                """
            )
        )

    recreees = _recreer_tables_vides_avec_drift()
    assert "arbitrage" in recreees

    # Un INSERT avec decision=None doit maintenant marcher
    arb = Arbitrage(
        type_cas="homonymie_ingestion",
        cle_cas="test-recreation",
        decision=None,
        contexte_json="{}",
    )
    session.add(arb)
    session.commit()
    assert arb.id is not None
    assert arb.decision is None


def test_drift_nullability_ne_touche_pas_table_non_vide(session, tmp_db_path):
    """Si la table a des données, on ne la drop pas — warning et on laisse."""
    from backend.database import _engine, _recreer_tables_vides_avec_drift
    from backend.models import Arbitrage

    # Ajoute une ligne pour que la table ne soit pas vide
    session.add(
        Arbitrage(
            type_cas="collision_login",
            cle_cas="deja-la",
            decision="suffixe:2",
            contexte_json="{}",
        )
    )
    session.commit()

    # Simule un drift en recréant la table avec NOT NULL et en réinsérant
    with _engine.begin() as conn:
        conn.execute(text("DROP TABLE arbitrage"))
        conn.execute(
            text(
                """
                CREATE TABLE arbitrage (
                    id INTEGER PRIMARY KEY,
                    type_cas VARCHAR(30) NOT NULL,
                    cle_cas VARCHAR(300) NOT NULL UNIQUE,
                    decision VARCHAR(100) NOT NULL,
                    contexte_json TEXT NOT NULL,
                    date_creation DATETIME NOT NULL,
                    date_decision DATETIME,
                    note VARCHAR(500)
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO arbitrage (type_cas, cle_cas, decision, contexte_json, date_creation) "
                "VALUES ('collision_login', 'deja-la', 'suffixe:2', '{}', datetime('now'))"
            )
        )

    recreees = _recreer_tables_vides_avec_drift()
    # Non vide → pas recréée
    assert "arbitrage" not in recreees
