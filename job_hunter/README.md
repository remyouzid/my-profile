# AI Job Hunter — stages en finance

Agent qui cherche des offres de stage, les note avec Claude, rédige une lettre de motivation
personnalisée pour chacune, envoie les candidatures par e-mail (avec ta validation) et tient un
tableau de suivi avec relances.

## Installation

```bash
cd job_hunter
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Crée un fichier `job_hunter/.env` :

```
ANTHROPIC_API_KEY=sk-ant-...
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx      # myaccount.google.com/apppasswords
FRANCE_TRAVAIL_CLIENT_ID=...                 # optionnel, francetravail.io
FRANCE_TRAVAIL_CLIENT_SECRET=...
```

Dépose ton CV en PDF dans `job_hunter/cv.pdf` : l'agent le lit pour noter les offres et écrire
les lettres, et le joint aux e-mails. Ajuste `config.json` (postes, villes, banques ciblées).

`cv.pdf`, `.env`, le suivi et les lettres sont exclus de git : tes données personnelles ne
partent jamais sur GitHub.

## Utilisation quotidienne

```bash
python main.py search        # 1. trouve et note les offres (score 0-100)
python main.py prepare       # 2. rédige les lettres -> dossier letters/  (relis-les !)
python main.py send          # 3. envoie, une confirmation par e-mail, 15 max par jour
python main.py follow-up     # 4. relance après 10 jours sans réponse
python main.py status        # 5. stats + suivi_candidatures.xlsx
```

Autres commandes :

```bash
python main.py add "https://www.linkedin.com/jobs/view/..." --company "BNP Paribas" --title "Stage M&A"
python main.py set "BNP" entretien      # statuts : entretien, refus, offre...
```

## Comment ça marche

| Étape | Détail |
|---|---|
| Recherche web | Claude cherche sur le web entier : sites carrières des ~40 banques et sociétés de gestion de `target_companies`, JobTeaser, LinkedIn, eFinancialCareers, iAgora, Jooble, Hellowork, Apec… puis une recherche par type de poste. |
| Sites d'annonces | En complément : Welcome to the Jungle, Indeed, France Travail (API officielle). `--sources web` pour n'utiliser que la recherche web. |
| Tri | Claude note chaque offre selon ton profil ; sous 65, elle est écartée. |
| Lettre | Une lettre unique par offre, fondée uniquement sur ton CV (rien d'inventé). |
| Envoi | Par e-mail quand l'annonce donne un contact. Sinon l'offre passe en `a_postuler_manuellement` avec le lien et la lettre prête. |
| Suivi | `applications.csv` + export Excel, relance automatique proposée à J+10. |

## Limites à connaître

- La plupart des grandes banques passent par des formulaires (Workday, Taleo) : l'outil prépare
  la lettre, mais la soumission reste manuelle. C'est là que Claude dans Chrome peut t'aider.
- Coût : la recherche web complète (~12 lots de 8 recherches) coûte de l'ordre de quelques
  dollars de crédits API par passage. Une fois par jour ou tous les deux jours suffit.
- Les scrapers WTTJ/Indeed dépendent du HTML des sites : s'ils renvoient 0 résultat, le site a
  changé ou bloque les requêtes. France Travail (API officielle) est la source la plus fiable.
- Garde la confirmation avant envoi : des dizaines d'e-mails génériques envoyés sans relecture
  font plus de mal que de bien, et Gmail peut bloquer un compte qui envoie en masse.
