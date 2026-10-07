# Outil d'évaluation IA Act (Streamlit)

Application qui évalue le niveau de risque IA Act d'un projet à partir d'un
questionnaire rempli par plusieurs participants.

## Lancer

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre sur http://localhost:8501. La base SQLite `ia_act.db`
est créée au premier lancement.

## Parcours

1. **Liste des projets** : statuts Ouvert, Complet, Émis.
2. **Nouveau projet** : cas d'usage, participants, envoi du questionnaire.
3. **Suivi** : qui a répondu ; chaque participant a un lien personnel
   (`?token=...`).
4. **Questionnaire** : le participant répond par son lien ; les réponses sont
   enregistrées en base.
5. **Lancer le rapport** : disponible quand tous ont répondu (statut Complet).
6. **Rapport** : réponses côte à côte et analyse initiale. La dernière colonne
   du tableau, **Réponse finale**, reçoit pour chaque question la réponse
   arrêtée par consensus de tous les participants (les réponses unanimes sont
   proposées d'office).
7. **Rapport final** : une nouvelle analyse est générée à partir des réponses
   finales. C'est ce rapport qui est émis (statut Émis) ; l'émission n'est
   possible que s'il correspond aux réponses finales affichées.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `app.py` | Écrans et navigation |
| `db.py` | Tables SQLite et changements de statut |
| `analyse.py` | Questions du questionnaire, analyse initiale et rapport final, par règles ou par LLM |
| `courriel.py` | Envoi d'e-mails (facultatif) |

## Configuration (variables d'environnement, toutes facultatives)

| Variable | Effet |
| --- | --- |
| `ANTHROPIC_API_KEY` | Active l'analyse par LLM. Sans elle, des règles simples classent le projet. |
| `IA_ACT_MODELE` | Modèle utilisé (`claude-sonnet-5-5` par défaut). |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Active l'envoi des invitations et du rapport par e-mail. Sans elles, les liens s'affichent sur l'écran de suivi. |
| `IA_ACT_URL` | Adresse publique de l'application, pour les liens de questionnaire. |
| `IA_ACT_DB` | Chemin de la base SQLite. |

## Limites connues

- Pas d'authentification : toute personne qui ouvre l'application voit la vue
  PMO. Seul le lien `?token=...` limite un participant à son questionnaire.
- Les cinq questions de `analyse.py` sont un point de départ, à valider par le
  groupe de travail.
- Le niveau de risque proposé est une aide à la décision, pas un avis
  juridique.
