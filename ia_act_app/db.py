"""Stockage SQLite de l'outil d'évaluation IA Act.

Trois tables :
- participants : les personnes que l'on peut inviter ;
- projets      : un cas d'usage et son statut (Ouvert -> Complet -> Émis), avec
                 l'analyse initiale, les réponses finales arrêtées par
                 consensus et le rapport final ;
- invitations  : un questionnaire par (projet, participant), avec ses réponses.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.getenv(
    "IA_ACT_DB",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "questcequia.db"),
)

OUVERT, COMPLET, EMIS = "Ouvert", "Complet", "Émis"

SCHEMA = """
CREATE TABLE IF NOT EXISTS participants (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    prenom TEXT NOT NULL,
    email  TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS projets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ref          TEXT,
    nom          TEXT NOT NULL,
    description  TEXT NOT NULL,
    statut       TEXT NOT NULL DEFAULT 'Ouvert',
    cree_le      TEXT NOT NULL,
    rapport_json TEXT,
    emis_le      TEXT,
    reponses_finales_json TEXT,
    rapport_final_json    TEXT
);
CREATE TABLE IF NOT EXISTS invitations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    projet_id      INTEGER NOT NULL REFERENCES projets(id),
    participant_id INTEGER NOT NULL REFERENCES participants(id),
    token          TEXT NOT NULL UNIQUE,
    envoye_le      TEXT NOT NULL,
    repondu_le     TEXT,
    reponses_json  TEXT,
    commentaire    TEXT,
    UNIQUE (projet_id, participant_id)
);
"""


def _maintenant() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connexion():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Colonnes ajoutées après la première version : créées sur les bases existantes.
COLONNES_AJOUTEES = {
    "projets": {
        "reponses_finales_json": "TEXT",
        "rapport_final_json": "TEXT",
    },
}


def init_db() -> None:
    """Crée les tables si elles n'existent pas et complète les anciennes bases."""
    with connexion() as conn:
        conn.executescript(SCHEMA)
        for table, colonnes in COLONNES_AJOUTEES.items():
            presentes = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for nom, type_sql in colonnes.items():
                if nom not in presentes:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {type_sql}")


# --- Participants -----------------------------------------------------------

def obtenir_participant(prenom: str, email: str) -> int:
    """Renvoie l'identifiant du participant, en le créant si besoin.

    L'e-mail identifie la personne : s'il est déjà connu, la fiche existante
    est réutilisée telle quelle.
    """
    email = email.strip().lower()
    with connexion() as conn:
        row = conn.execute("SELECT id FROM participants WHERE email = ?", (email,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO participants (prenom, email) VALUES (?, ?)", (prenom.strip(), email)
        )
        return cur.lastrowid


# --- Projets ----------------------------------------------------------------

def creer_projet(nom: str, description: str, participant_ids: list[int]) -> int:
    """Crée le projet (statut Ouvert) et une invitation par participant."""
    now = _maintenant()
    with connexion() as conn:
        cur = conn.execute(
            "INSERT INTO projets (nom, description, statut, cree_le) VALUES (?, ?, ?, ?)",
            (nom.strip(), description.strip(), OUVERT, now),
        )
        projet_id = cur.lastrowid
        ref = f"IA-{datetime.now().year}-{projet_id:03d}"
        conn.execute("UPDATE projets SET ref = ? WHERE id = ?", (ref, projet_id))
        conn.executemany(
            "INSERT INTO invitations (projet_id, participant_id, token, envoye_le) "
            "VALUES (?, ?, ?, ?)",
            [(projet_id, pid, secrets.token_urlsafe(16), now) for pid in participant_ids],
        )
    return projet_id


def _projet_depuis_row(row: sqlite3.Row) -> dict:
    projet = dict(row)
    # rapport : analyse initiale ; rapport_final : analyse des réponses finales.
    for cle in ("rapport", "reponses_finales", "rapport_final"):
        brut = projet.pop(f"{cle}_json")
        projet[cle] = json.loads(brut) if brut else None
    return projet


def lister_projets() -> list[dict]:
    """Projets du plus récent au plus ancien, avec le décompte des réponses."""
    with connexion() as conn:
        rows = conn.execute(
            """
            SELECT p.*,
                   COUNT(i.id)         AS nb_invites,
                   COUNT(i.repondu_le) AS nb_reponses
            FROM projets p
            LEFT JOIN invitations i ON i.projet_id = p.id
            GROUP BY p.id
            ORDER BY p.id DESC
            """
        ).fetchall()
    return [_projet_depuis_row(r) for r in rows]


def lire_projet(projet_id: int) -> dict | None:
    with connexion() as conn:
        row = conn.execute("SELECT * FROM projets WHERE id = ?", (projet_id,)).fetchone()
    return _projet_depuis_row(row) if row else None


def enregistrer_rapport(projet_id: int, rapport: dict) -> None:
    """Enregistre l'analyse initiale (réponses individuelles des participants)."""
    with connexion() as conn:
        conn.execute(
            "UPDATE projets SET rapport_json = ? WHERE id = ?",
            (json.dumps(rapport, ensure_ascii=False), projet_id),
        )


def enregistrer_rapport_final(projet_id: int, reponses_finales: dict, rapport: dict) -> None:
    """Enregistre les réponses finales (consensus) et le rapport qui en découle.

    Les deux sont écrits ensemble : le rapport final correspond toujours aux
    réponses finales enregistrées. Sans effet une fois le rapport émis.
    """
    with connexion() as conn:
        conn.execute(
            "UPDATE projets SET reponses_finales_json = ?, rapport_final_json = ? "
            "WHERE id = ? AND statut = ?",
            (
                json.dumps(reponses_finales, ensure_ascii=False),
                json.dumps(rapport, ensure_ascii=False),
                projet_id,
                COMPLET,
            ),
        )


def emettre_rapport(projet_id: int) -> bool:
    """Passe le projet au statut Émis. Le rapport final doit déjà exister.

    Renvoie True si le projet a bien été émis.
    """
    with connexion() as conn:
        cur = conn.execute(
            "UPDATE projets SET statut = ?, emis_le = ? "
            "WHERE id = ? AND statut = ? AND rapport_final_json IS NOT NULL",
            (EMIS, _maintenant(), projet_id, COMPLET),
        )
        return cur.rowcount == 1


# --- Invitations et réponses ------------------------------------------------

def _invitation_depuis_row(row: sqlite3.Row) -> dict:
    inv = dict(row)
    inv["reponses"] = json.loads(inv.pop("reponses_json")) if inv["reponses_json"] else None
    return inv


def lister_invitations(projet_id: int) -> list[dict]:
    with connexion() as conn:
        rows = conn.execute(
            """
            SELECT i.*, pa.prenom, pa.email
            FROM invitations i
            JOIN participants pa ON pa.id = i.participant_id
            WHERE i.projet_id = ?
            ORDER BY i.id
            """,
            (projet_id,),
        ).fetchall()
    return [_invitation_depuis_row(r) for r in rows]


def lire_invitation(token: str) -> dict | None:
    with connexion() as conn:
        row = conn.execute(
            """
            SELECT i.*, pa.prenom, pa.email
            FROM invitations i
            JOIN participants pa ON pa.id = i.participant_id
            WHERE i.token = ?
            """,
            (token,),
        ).fetchone()
    return _invitation_depuis_row(row) if row else None


def enregistrer_reponses(token: str, reponses: dict, commentaire: str) -> str:
    """Enregistre les réponses d'un participant et met à jour le statut du projet.

    Le projet passe à Complet dès que tous les invités ont répondu. Si une
    analyse ou un rapport final avaient déjà été générés, ils sont effacés :
    ils ne reflètent plus les réponses. Les réponses finales déjà saisies sont
    conservées comme point de départ. Renvoie le statut du projet après
    enregistrement.
    """
    with connexion() as conn:
        inv = conn.execute(
            "SELECT projet_id FROM invitations WHERE token = ?", (token,)
        ).fetchone()
        if inv is None:
            raise ValueError("Invitation inconnue")
        projet_id = inv["projet_id"]
        statut = conn.execute(
            "SELECT statut FROM projets WHERE id = ?", (projet_id,)
        ).fetchone()["statut"]
        if statut == EMIS:
            raise ValueError("Le rapport est émis : les réponses ne sont plus modifiables")

        conn.execute(
            "UPDATE invitations SET reponses_json = ?, commentaire = ?, repondu_le = ? "
            "WHERE token = ?",
            (json.dumps(reponses, ensure_ascii=False), commentaire.strip(), _maintenant(), token),
        )
        en_attente = conn.execute(
            "SELECT COUNT(*) FROM invitations WHERE projet_id = ? AND repondu_le IS NULL",
            (projet_id,),
        ).fetchone()[0]
        nouveau_statut = COMPLET if en_attente == 0 else OUVERT
        conn.execute(
            "UPDATE projets SET statut = ?, rapport_json = NULL, rapport_final_json = NULL "
            "WHERE id = ?",
            (nouveau_statut, projet_id),
        )
    return nouveau_statut
