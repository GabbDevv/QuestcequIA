"""Outil d'évaluation IA Act : application Streamlit.

Lancement :  streamlit run app.py

Parcours :
1. Liste des projets            -> page_liste
2. Nouveau projet               -> page_creer
3. Suivi des réponses           -> page_projet   (statut Ouvert)
4. Questionnaire du participant -> page_questionnaire (lien ?token=...)
5. Lancer le rapport            -> page_projet   (statut Complet)
6. Rapport                      -> page_rapport  : analyse initiale, réponses
   finales arrêtées par consensus, rapport final, puis émission (statut Émis)
"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

import analyse
import courriel
import db
from db import COMPLET, EMIS, OUVERT

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc."]

COULEURS_STATUT = {
    OUVERT: ("#E4ECFB", "#1E3F8F"),
    COMPLET: ("#FBE9C8", "#6B4300"),
    EMIS: ("#111B2B", "#FFFFFF"),
}
COL_FINALE = "Réponse finale"

DESCRIPTION_STATUT = {
    OUVERT: "Questionnaire envoyé, réponses en attente.",
    COMPLET: "Toutes les réponses reçues, rapport à lancer.",
    EMIS: "Rapport émis, niveau de risque validé.",
}


# --- Outils d'affichage -----------------------------------------------------
# Les fragments HTML ci-dessous ne contiennent que des libellés fixes, jamais
# de texte saisi par un utilisateur.

def date_fr(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def badge(statut: str) -> str:
    fond, texte = COULEURS_STATUT[statut]
    return (
        f'<span style="background:{fond};color:{texte};padding:3px 12px;'
        f'border-radius:999px;font-size:0.85rem;font-weight:600">{statut}</span>'
    )


def frise_statut(statut: str) -> str:
    """Ouvert -> Complet -> Émis, avec l'étape courante en gras."""
    etapes = []
    for etape in (OUVERT, COMPLET, EMIS):
        if etape == statut:
            etapes.append(f'<b style="border-bottom:3px solid #0B5E6F;padding-bottom:2px">{etape}</b>')
        else:
            etapes.append(f'<span style="opacity:0.65">{etape}</span>')
    return '<div style="display:flex;gap:14px;flex-wrap:wrap">' + "<span>→</span>".join(etapes) + "</div>"


def echelle_risque(niveau: str) -> str:
    cases = []
    for n in analyse.NIVEAUX:
        if n == niveau:
            style = "background:#111B2B;color:#FFFFFF;font-weight:600;border:1px solid #111B2B"
        else:
            style = "border:1px solid #8A94A6;opacity:0.75"
        cases.append(f'<div style="flex:1 1 150px;padding:12px 14px;border-radius:8px;{style}">{n}</div>')
    return '<div style="display:flex;gap:8px;flex-wrap:wrap">' + "".join(cases) + "</div>"


def rapport_retenu(projet: dict) -> dict | None:
    """Le rapport final s'il existe, sinon l'analyse initiale."""
    return projet["rapport_final"] or projet["rapport"]


def aller(page: str, projet_id: int | None = None) -> None:
    st.session_state["page"] = page
    if projet_id is not None:
        st.session_state["projet_id"] = projet_id


def annoncer(message: str) -> None:
    """Message affiché une fois, en haut de la page suivante."""
    st.session_state["annonce"] = message


def afficher_annonce() -> None:
    message = st.session_state.pop("annonce", None)
    if message:
        st.success(message)


def url_application() -> str:
    """Adresse de l'application, pour construire les liens de questionnaire.

    Priorité à la variable IA_ACT_URL (utile derrière un proxy), sinon
    l'adresse de la page en cours.
    """
    url = os.getenv("IA_ACT_URL")
    if not url:
        try:
            url = st.context.url  # Streamlit >= 1.45
        except Exception:
            url = None
    return (url or "http://localhost:8501").split("?")[0].rstrip("/")


def lien_questionnaire(token: str) -> str:
    return f"{url_application()}/?token={token}"


# --- 1. Liste des projets ---------------------------------------------------

def page_liste() -> None:
    gauche, droite = st.columns([4, 1])
    gauche.title("Projets")
    gauche.caption(
        "Évaluez le niveau de risque IA Act de chaque projet qui utilise de "
        "l'IA, à partir des réponses des participants."
    )
    droite.write("")
    droite.button("Créer un projet", type="primary", on_click=aller, args=("creer",))
    afficher_annonce()

    projets = db.lister_projets()

    for colonne, statut in zip(st.columns(3), (OUVERT, COMPLET, EMIS)):
        with colonne.container(border=True):
            nombre = sum(1 for p in projets if p["statut"] == statut)
            st.markdown(badge(statut), unsafe_allow_html=True)
            st.subheader(str(nombre))
            st.caption(DESCRIPTION_STATUT[statut])

    if not projets:
        st.info("Aucun projet pour l'instant. Créez le premier pour envoyer un questionnaire.")
        return

    largeurs = [3.2, 1.2, 1.6, 1.3, 1.7, 1.6]
    entetes = st.columns(largeurs)
    for colonne, titre in zip(entetes, ["Projet", "Statut", "Réponses", "Créé le", "Niveau de risque", "Action"]):
        colonne.caption(titre.upper())

    for p in projets:
        with st.container(border=True):
            c_nom, c_statut, c_rep, c_date, c_niveau, c_action = st.columns(largeurs)
            c_nom.markdown(f"**{p['nom']}**")
            c_nom.caption(p["ref"])
            c_statut.markdown(badge(p["statut"]), unsafe_allow_html=True)
            total = p["nb_invites"] or 1
            c_rep.progress(p["nb_reponses"] / total, text=f"{p['nb_reponses']} / {p['nb_invites']}")
            c_date.write(date_fr(p["cree_le"]))
            if p["statut"] == EMIS and rapport_retenu(p):
                c_niveau.markdown(f"**{rapport_retenu(p)['niveau']}**")
                c_action.button("Voir le rapport", key=f"voir_{p['id']}",
                                on_click=aller, args=("rapport", p["id"]))
            else:
                c_niveau.caption("Non évalué")
                libelle = "Lancer le rapport" if p["statut"] == COMPLET else "Suivre les réponses"
                c_action.button(libelle, key=f"ouvrir_{p['id']}",
                                on_click=aller, args=("projet", p["id"]))


# --- 2. Nouveau projet ------------------------------------------------------

def retirer_participant(position: int) -> None:
    st.session_state["nouveau_participants"].pop(position)


def page_creer() -> None:
    st.button("Retour aux projets", on_click=aller, args=("liste",))
    st.title("Nouveau projet")
    st.caption(
        "Décrivez le cas d'usage, puis ajoutez les personnes qui répondront "
        "au questionnaire IA Act."
    )
    # La liste part vide à chaque nouveau projet : [{"prenom": ..., "email": ...}]
    participants = st.session_state.setdefault("nouveau_participants", [])

    gauche, droite = st.columns([3, 2])

    with gauche.container(border=True):
        st.subheader("Cas d'usage")
        nom = st.text_input("Nom du projet", key="nouveau_nom")
        description = st.text_area(
            "Description du cas d'usage",
            key="nouveau_description",
            height=160,
            help="À quoi sert le système, et ce qu'il produit. Cette description "
                 "est transmise aux participants et au LLM.",
        )

    with droite.container(border=True):
        st.subheader("Liste des participants")
        st.caption("Chaque personne ajoutée reçoit le questionnaire par e-mail.")
        if not participants:
            st.info("Aucun participant pour l'instant.")
        for position, p in enumerate(participants):
            c_nom, c_retirer = st.columns([3, 1])
            c_nom.markdown(f"**{p['prenom']}**")
            c_nom.text(p["email"])
            c_retirer.button("Retirer", key=f"retirer_{position}",
                             on_click=retirer_participant, args=(position,))
        with st.form("ajout_participant", clear_on_submit=True, border=False):
            prenom = st.text_input("Prénom")
            email = st.text_input("E-mail", placeholder="prenom@exemple.fr")
            if st.form_submit_button("Ajouter un participant"):
                email = email.strip().lower()
                if not prenom.strip() or "@" not in email:
                    st.error("Indiquez un prénom et un e-mail valide.")
                elif any(p["email"] == email for p in participants):
                    st.error("Cet e-mail est déjà dans la liste.")
                else:
                    participants.append({"prenom": prenom.strip(), "email": email})
                    st.rerun()

    with st.container(border=True):
        c_texte, c_bouton = st.columns([3, 1])
        n = len(participants)
        c_texte.markdown(
            "**Aucun participant**" if n == 0
            else f"**{n} participant{'s' if n > 1 else ''}**"
        )
        c_texte.caption("À l'envoi, le projet passe au statut Ouvert.")
        if c_bouton.button("Envoyer le questionnaire", type="primary"):
            if not nom.strip() or not description.strip():
                st.error("Renseignez le nom du projet et la description du cas d'usage.")
            elif not participants:
                st.error("Ajoutez au moins un participant.")
            else:
                ids = [db.obtenir_participant(p["prenom"], p["email"]) for p in participants]
                projet_id = db.creer_projet(nom, description, ids)
                projet = db.lire_projet(projet_id)
                invitations = db.lister_invitations(projet_id)
                envoyes = sum(
                    courriel.envoyer_invitation(inv, projet, lien_questionnaire(inv["token"]))
                    for inv in invitations
                )
                if envoyes == len(invitations):
                    annoncer(f"Questionnaire envoyé par e-mail à {envoyes} participant(s).")
                else:
                    annoncer(
                        "Projet créé. L'envoi d'e-mails n'est pas configuré ou a échoué : "
                        "transmettez à chaque participant son lien ci-dessous."
                    )
                for cle in ("nouveau_nom", "nouveau_description", "nouveau_participants"):
                    del st.session_state[cle]
                aller("projet", projet_id)
                st.rerun()


# --- 3 et 5. Projet : suivi des réponses, lancement du rapport --------------

def page_projet(projet_id: int) -> None:
    projet = db.lire_projet(projet_id)
    if projet is None:
        aller("liste")
        st.rerun()
    invitations = db.lister_invitations(projet_id)
    repondu = [inv for inv in invitations if inv["repondu_le"]]
    en_attente = [inv for inv in invitations if not inv["repondu_le"]]

    st.button("Retour aux projets", on_click=aller, args=("liste",))
    st.title(projet["nom"])
    st.markdown(badge(projet["statut"]), unsafe_allow_html=True)
    st.caption(f"{projet['ref']} · créé le {date_fr(projet['cree_le'])}")
    afficher_annonce()
    st.markdown(frise_statut(projet["statut"]), unsafe_allow_html=True)
    st.write("")

    # Bloc rapport : désactivé tant qu'il manque des réponses.
    with st.container(border=True):
        c_texte, c_bouton = st.columns([3, 1])
        if projet["statut"] == OUVERT:
            c_texte.markdown("**Rapport**")
            manquants = ", ".join(inv["prenom"] for inv in en_attente)
            c_texte.caption(
                f"Disponible dès que les {len(invitations)} participants ont répondu. "
                f"Il manque : {manquants}."
            )
            c_bouton.button("Lancer le rapport", disabled=True)
        elif projet["rapport"]:
            niveau = rapport_retenu(projet)["niveau"]
            if projet["statut"] == EMIS:
                c_texte.markdown("**Rapport émis**")
                c_texte.caption(f"Niveau de risque : {niveau}.")
            elif projet["rapport_final"]:
                c_texte.markdown("**Le rapport final est prêt**")
                c_texte.caption(f"Niveau de risque : {niveau}. Il reste à l'émettre.")
            else:
                c_texte.markdown("**L'analyse est prête**")
                c_texte.caption(
                    f"Niveau proposé : {niveau}. Arrêtez les réponses finales "
                    "pour générer le rapport final."
                )
            c_bouton.button("Voir le rapport", type="primary", on_click=aller, args=("rapport", projet_id))
        else:
            c_texte.markdown("**Toutes les réponses sont reçues**")
            c_texte.caption(
                "Le rapport met côte à côte les réponses de chaque participant, "
                "puis l'analyse du LLM."
            )
            if c_bouton.button("Lancer le rapport", type="primary"):
                with st.spinner("Analyse des réponses en cours…"):
                    db.enregistrer_rapport(projet_id, analyse.analyser(projet, invitations))
                aller("rapport", projet_id)
                st.rerun()

    gauche, droite = st.columns([3, 2])

    with gauche.container(border=True):
        st.subheader("Cas d'usage")
        st.write(projet["description"])

    with droite.container(border=True):
        st.subheader("Participants")
        st.progress(
            len(repondu) / max(len(invitations), 1),
            text=f"{len(repondu)} réponse{'s' if len(repondu) > 1 else ''} sur {len(invitations)}",
        )
        for inv in invitations:
            with st.container(border=True):
                if inv["repondu_le"]:
                    st.markdown(f"**{inv['prenom']}** · a répondu le {date_fr(inv['repondu_le'])}")
                    continue
                st.markdown(f"**{inv['prenom']}** · en attente, envoyé le {date_fr(inv['envoye_le'])}")
                lien = lien_questionnaire(inv["token"])
                st.code(lien, language=None)
                if courriel.smtp_configure() and st.button("Relancer", key=f"relance_{inv['id']}"):
                    if courriel.envoyer_invitation(inv, projet, lien):
                        st.success(f"Relance envoyée à {inv['prenom']}.")
                    else:
                        st.error("La relance n'a pas pu être envoyée.")


# --- 4. Questionnaire du participant ----------------------------------------

def page_questionnaire(token: str) -> None:
    _, centre, _ = st.columns([1, 3, 1])
    with centre:
        invitation = db.lire_invitation(token)
        if invitation is None:
            st.error("Ce lien de questionnaire n'est pas valide.")
            return
        projet = db.lire_projet(invitation["projet_id"])

        st.caption(f"{projet['ref']} · questionnaire IA Act · {invitation['prenom']}")
        st.title(projet["nom"])
        st.write(
            "Vous êtes invité(e) à donner votre lecture de ce projet. Vos réponses "
            "sont comparées à celles des autres participants dans le rapport."
        )
        with st.container(border=True):
            st.caption("CAS D'USAGE")
            st.write(projet["description"])

        deja = invitation["reponses"] or {}
        cle_modif = f"modifier_{token}"

        if projet["statut"] == EMIS:
            st.info("Le rapport de ce projet a été émis : les réponses ne sont plus modifiables.")
            return

        if deja and not st.session_state.get(cle_modif):
            st.success("Réponses enregistrées. Merci !")
            if projet["statut"] == COMPLET:
                st.write("Tous les participants ont répondu : le rapport peut être lancé.")
            else:
                st.write("Le rapport sera lancé quand tous les participants auront répondu.")
            if st.button("Modifier mes réponses"):
                st.session_state[cle_modif] = True
                st.rerun()
            return

        with st.form("questionnaire"):
            reponses = {}
            for numero, q in enumerate(analyse.QUESTIONS, start=1):
                precedent = deja.get(q["id"])
                reponses[q["id"]] = st.radio(
                    f"**{numero}. {q['texte']}**",
                    analyse.CHOIX,
                    index=analyse.CHOIX.index(precedent) if precedent in analyse.CHOIX else None,
                    horizontal=True,
                )
                st.caption(q["aide"])
            commentaire = st.text_area(
                "Un commentaire à ajouter ? (facultatif)", value=invitation["commentaire"] or ""
            )
            if st.form_submit_button("Soumettre mes réponses", type="primary"):
                sans_reponse = [str(i) for i, q in enumerate(analyse.QUESTIONS, start=1)
                                if reponses[q["id"]] is None]
                if sans_reponse:
                    st.error(f"Il manque une réponse aux questions : {', '.join(sans_reponse)}.")
                else:
                    db.enregistrer_reponses(token, reponses, commentaire)
                    st.session_state[cle_modif] = False
                    st.rerun()


# --- 6. Rapport -------------------------------------------------------------

def tableau_reponses(
    invitations: list[dict], rapport: dict, reponses_finales: dict | None = None
) -> pd.DataFrame:
    """Une ligne par question : participants, analyse initiale, réponse finale.

    La colonne « Réponse finale » n'apparaît que si `reponses_finales` est fourni.
    """
    colonne_analyse = "LLM" if rapport["source"] == "llm" else "Analyse"
    lignes = []
    for q in analyse.QUESTIONS:
        ligne = {"Question": f"{q['court']} ({q['reference']})"}
        for inv in invitations:
            ligne[inv["prenom"]] = (inv["reponses"] or {}).get(q["id"], "")
        item = rapport["par_question"][q["id"]]
        ligne[colonne_analyse] = (
            f"{item['reponse']} : {item['commentaire']}" if item["commentaire"] else item["reponse"]
        )
        if reponses_finales is not None:
            ligne[COL_FINALE] = reponses_finales.get(q["id"])
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def editeur_reponses_finales(projet: dict, invitations: list[dict]) -> dict[str, str]:
    """Tableau des réponses dont seule la colonne « Réponse finale » se modifie.

    Point de départ : les réponses finales déjà enregistrées, sinon la réponse
    unanime des participants. Renvoie les réponses finales saisies, par id de
    question (les questions laissées vides sont absentes).
    """
    depart = analyse.reponses_finales_proposees(invitations)
    depart.update(projet["reponses_finales"] or {})
    tableau = tableau_reponses(invitations, projet["rapport"], depart)
    saisie = st.data_editor(
        tableau,
        hide_index=True,
        key=f"finales_{projet['id']}",
        disabled=[colonne for colonne in tableau.columns if colonne != COL_FINALE],
        column_config={
            COL_FINALE: st.column_config.SelectboxColumn(
                COL_FINALE,
                options=analyse.CHOIX,
                help="Réponse arrêtée par consensus de tous les participants.",
            )
        },
    )
    return {
        q["id"]: reponse
        for q, reponse in zip(analyse.QUESTIONS, saisie[COL_FINALE])
        if reponse in analyse.CHOIX
    }


def bloc_analyse(rapport: dict, final: bool = False) -> None:
    """Niveau de risque, justification et actions d'une analyse."""
    par_llm = rapport["source"] == "llm"
    with st.container(border=True):
        if final:
            st.subheader("Rapport final")
            st.caption(
                (f"Généré par {rapport['modele']}" if par_llm else "Établi par les règles intégrées")
                + " à partir des réponses finales, arrêtées par consensus des participants."
            )
        elif par_llm:
            st.subheader("Réponse du LLM")
            st.caption(
                f"Proposition générée par {rapport['modele']} à partir du cas d'usage "
                "et des réponses de chaque participant."
            )
        else:
            st.subheader("Analyse par règles")
            st.caption(
                "Aucun LLM n'est configuré (variable ANTHROPIC_API_KEY ou GOOGLE_API_KEY) : le niveau "
                "est déduit des réponses de chaque participant par des règles simples."
            )
        if rapport.get("avertissement"):
            st.warning(rapport["avertissement"])

        st.caption("NIVEAU DE RISQUE FINAL" if final else "NIVEAU DE RISQUE PROPOSÉ")
        st.markdown(echelle_risque(rapport["niveau"]), unsafe_allow_html=True)
        st.write("")

        gauche, droite = st.columns(2)
        gauche.markdown("**Justification**")
        gauche.write(rapport["justification"])
        droite.markdown("**À faire**")
        droite.markdown("\n".join(f"- {action}" for action in rapport["actions"]) or "Rien à signaler.")

        if rapport["divergences"]:
            st.warning(
                "**Divergences entre participants, à trancher par les réponses finales :**\n\n"
                + "\n".join(f"- {d}" for d in rapport["divergences"])
            )
        if rapport.get("reserves"):
            st.warning(
                "**Points où le LLM s'écarte des réponses finales :**\n\n"
                + "\n".join(f"- {r}" for r in rapport["reserves"])
            )


def rapport_markdown(projet: dict, invitations: list[dict]) -> str:
    """Le rapport à télécharger : le rapport final, sinon l'analyse initiale."""
    initial, final = projet["rapport"], projet["rapport_final"]
    rapport = final or initial
    origine = f"LLM ({rapport['modele']})" if rapport["source"] == "llm" else "règles intégrées"
    lignes = [
        f"# Rapport d'évaluation IA Act : {projet['nom']}",
        "",
        f"- Référence : {projet['ref']}",
        f"- Statut : {projet['statut']}",
        f"- Participants : {', '.join(inv['prenom'] for inv in invitations)}",
        f"- {'Rapport final établi' if final else 'Analyse produite'} par : {origine}",
        "",
        "## Cas d'usage",
        "",
        projet["description"],
        "",
        f"## Niveau de risque : {rapport['niveau']}",
        "",
        rapport["justification"],
        "",
        "## À faire",
        "",
        *[f"- {action}" for action in rapport["actions"]],
        "",
    ]
    if rapport.get("reserves"):
        lignes += ["## Points où le LLM s'écarte des réponses finales", "",
                   *[f"- {r}" for r in rapport["reserves"]], ""]
    if not final and initial["divergences"]:
        lignes += ["## Divergences entre participants", "", *[f"- {d}" for d in initial["divergences"]], ""]
    tableau = tableau_reponses(invitations, initial, projet["reponses_finales"] if final else None)
    lignes += [
        "## Réponses par question",
        "",
        "| " + " | ".join(tableau.columns) + " |",
        "|" + " --- |" * len(tableau.columns),
        *["| " + " | ".join("" if v is None else str(v) for v in ligne) + " |"
          for ligne in tableau.itertuples(index=False)],
        "",
    ]
    if final:
        lignes += ["## Analyse initiale", "",
                   f"Niveau proposé avant les réponses finales : {initial['niveau']}.", ""]
        if initial["divergences"]:
            lignes += ["Divergences entre participants, tranchées par les réponses finales :", "",
                       *[f"- {d}" for d in initial["divergences"]], ""]
    commentaires = [f"- {inv['prenom']} : {inv['commentaire']}" for inv in invitations if inv["commentaire"]]
    if commentaires:
        lignes += ["## Commentaires des participants", "", *commentaires, ""]
    return "\n".join(lignes)


def page_rapport(projet_id: int) -> None:
    projet = db.lire_projet(projet_id)
    if projet is None or projet["rapport"] is None:
        aller("projet" if projet else "liste", projet_id)
        st.rerun()
    rapport, rapport_final = projet["rapport"], projet["rapport_final"]
    invitations = db.lister_invitations(projet_id)
    emis = projet["statut"] == EMIS

    st.button("Retour au projet", on_click=aller, args=("projet", projet_id))
    st.title("Rapport d'évaluation")
    st.markdown(badge(projet["statut"]), unsafe_allow_html=True)
    st.caption(f"{projet['nom']} · {projet['ref']} · {len(invitations)} participant(s)")
    afficher_annonce()

    a_jour = False  # le rapport final correspond-il aux réponses finales affichées ?
    if emis and rapport_final:
        bloc_analyse(rapport_final, final=True)
        st.subheader("Réponses par question")
        st.dataframe(tableau_reponses(invitations, rapport, projet["reponses_finales"]), hide_index=True)
        with st.expander("Analyse initiale"):
            bloc_analyse(rapport)
    elif emis:  # projet émis avant l'ajout des réponses finales
        bloc_analyse(rapport)
        st.subheader("Réponses par question")
        st.dataframe(tableau_reponses(invitations, rapport), hide_index=True)
    else:
        bloc_analyse(rapport)

        st.subheader("Réponses par question")
        st.caption(
            "Dans la colonne « Réponse finale », choisissez pour chaque question la "
            "réponse arrêtée par consensus de tous les participants. Les réponses "
            "unanimes sont proposées d'office et restent modifiables."
        )
        finales = editeur_reponses_finales(projet, invitations)
        complet = analyse.reponses_finales_completes(finales)
        a_jour = rapport_final is not None and finales == projet["reponses_finales"]

        with st.container(border=True):
            c_texte, c_bouton = st.columns([3, 1])
            c_texte.markdown("**Réponses finales**")
            if not complet:
                manquantes = ", ".join(q["court"] for q in analyse.QUESTIONS if q["id"] not in finales)
                c_texte.caption(f"Disponible quand chaque question a sa réponse finale. Il manque : {manquantes}.")
            elif a_jour:
                c_texte.caption("Le rapport final ci-dessous correspond aux réponses finales du tableau.")
            elif rapport_final:
                c_texte.warning(
                    "Les réponses finales ont changé depuis le rapport final ci-dessous : "
                    "régénérez-le avant de l'émettre."
                )
            else:
                c_texte.caption(
                    "Une nouvelle analyse est générée à partir des réponses finales : "
                    "c'est elle qui sera émise."
                )
            if c_bouton.button(
                "Régénérer le rapport final" if rapport_final else "Générer le rapport final",
                type="secondary" if a_jour else "primary",
                disabled=not complet,
            ):
                with st.spinner("Analyse des réponses finales en cours…"):
                    db.enregistrer_rapport_final(
                        projet_id, finales, analyse.analyser_final(projet, invitations, finales)
                    )
                st.rerun()

        if rapport_final:
            bloc_analyse(rapport_final, final=True)

    commentaires = [inv for inv in invitations if inv["commentaire"]]
    if commentaires:
        st.subheader("Commentaires des participants")
        for inv in commentaires:
            st.markdown(f"**{inv['prenom']}**")
            st.write(inv["commentaire"])

    with st.container(border=True):
        if emis:
            c_texte, c_bouton = st.columns([3, 1])
            c_texte.markdown(f"**Rapport émis le {date_fr(projet['emis_le'])}**")
            c_texte.caption(f"Niveau retenu : {rapport_retenu(projet)['niveau']}.")
            c_bouton.download_button(
                "Télécharger le rapport",
                data=rapport_markdown(projet, invitations),
                file_name=f"rapport_{projet['ref']}.md",
                mime="text/markdown",
            )
        else:
            c_texte, c_regenerer, c_emettre = st.columns([3, 1, 1])
            c_texte.markdown("**Émettre le rapport final ?**")
            c_texte.caption(
                "Le projet passe au statut Émis. Cette action est définitive." if a_jour
                else "Générez d'abord le rapport final à partir des réponses finales."
            )
            if c_regenerer.button("Régénérer l'analyse initiale"):
                with st.spinner("Analyse des réponses en cours…"):
                    db.enregistrer_rapport(projet_id, analyse.analyser(projet, invitations))
                st.rerun()
            if c_emettre.button("Émettre le rapport", type="primary", disabled=not a_jour):
                if not db.emettre_rapport(projet_id):
                    st.error("Le rapport n'a pas pu être émis : régénérez le rapport final.")
                    st.stop()
                projet = db.lire_projet(projet_id)
                texte = rapport_markdown(projet, invitations)
                envoyes = sum(courriel.envoyer_rapport(inv, projet, texte) for inv in invitations)
                annoncer(
                    f"Rapport final émis et envoyé à {envoyes} participant(s)." if envoyes
                    else "Rapport final émis."
                )
                st.rerun()


# --- Routage ----------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Évaluation IA Act", layout="wide")
    db.init_db()

    # Un participant arrive par son lien personnel : il ne voit que son questionnaire.
    token = st.query_params.get("token")
    if token:
        page_questionnaire(token)
        return

    page = st.session_state.get("page", "liste")
    projet_id = st.session_state.get("projet_id")
    if page == "creer":
        page_creer()
    elif page == "projet" and projet_id:
        page_projet(projet_id)
    elif page == "rapport" and projet_id:
        page_rapport(projet_id)
    else:
        page_liste()


main()
