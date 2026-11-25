# FANAFODIKO

Plateforme de démonstration de réservation de produits de santé — projet portfolio.

> **Projet de démonstration locale. Ce dépôt n'est pas prêt pour une utilisation en production.**
> Le verdict de l'audit final est documenté dans [docs/final-security-audit-report.md](docs/final-security-audit-report.md).

## État du projet

- **Site web FANAFODIKO** : encore en cours de développement.
- **Application mobile FANAFODIKO** : également en cours de développement.
- Le projet est en **développement actif** et n'est **pas encore prêt pour la production**.

## Présentation

FANAFODIKO est un monolithe modulaire qui met en relation patients, vendeurs partenaires et administration centrale autour d'un catalogue de produits de santé. Le projet illustre la conception d'une API Django REST sécurisée, d'un frontend Next.js responsive, d'un workflow de validation réglementaire (AMM) et d'une réservation sans paiement en ligne.

Les phases de développement sont décrites dans [docs/phase2.md](docs/phase2.md), [docs/phase3.md](docs/phase3.md), [docs/phase7.md](docs/phase7.md) et [docs/phase7-progress.md](docs/phase7-progress.md). Les durcissements de sécurité réalisés sont résumés dans [docs/security-hardening-report.md](docs/security-hardening-report.md).

## Technologies utilisées

- **Backend** : Python 3.12, Django 5.2, Django REST Framework, PostgreSQL, sessions Django, CSRF, throttling.
- **Frontend** : Next.js 15, React 19, TypeScript, Tailwind CSS, ESLint, `node:test`.
- **Données** : migrations Django, référentiel Madagascar, baseline de démonstration locale.
- **Documentation API** : drf-spectacular / OpenAPI (`docs/api-schema.yaml`).

## Fonctionnalités développées

- Catalogue public de médicaments et de matériel médical, avec règles de commandabilité calculées côté serveur.
- Workflow AMM : déclaration par le partenaire, décision par l'administration centrale, garde-fous avant publication.
- Espace partenaire : gestion des produits, images, stocks, promotions et commandes reçues.
- Espace patient : panier serveur, coupons, adresses de livraison, réservation sans paiement en ligne, suivi des commandes.
- Administration centrale : supervision des comptes, vérifications professionnelles, modération catalogue, promotions et journaux d'audit.
- Séparation des rôles : patient, partenaire vendeur, staff avec permissions explicites, superutilisateur.
- Notifications internes et lien WhatsApp configuré côté backend, sans envoi automatique ni Cloud API.
- Durcissements E1-E3, M1 et M2 : configuration production, throttling, workflow AMM, révocation de sessions et permissions explicites.

## Installation locale

### Prérequis

- Python 3.12+
- Node.js 20.9+ et npm
- PostgreSQL 16+ (ou SQLite pour le settings `local_test`)

### Backend

```powershell
# À la racine du dépôt
copy .env.example .env
# Renseigner les valeurs locales dans .env (ne jamais publier ce fichier)

cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate --settings=config.settings.development
python manage.py runserver --settings=config.settings.development
```

Pour travailler avec la base locale de démonstration :

```powershell
python manage.py migrate --settings=config.settings.local_test
python manage.py seed_local_demo --settings=config.settings.local_test
```

### Frontend

```powershell
cd frontend
npm ci
npm run dev
```

URLs locales : API `http://localhost:8000/api/`, Swagger `http://localhost:8000/api/schema/swagger-ui/`, administration `http://localhost:8000/admin/`, web `http://localhost:3000`.

## Tests et vérifications

```powershell
# Backend
cd backend
python manage.py test --settings=config.settings.test
python manage.py check --settings=config.settings.test

# Frontend
cd frontend
npm test
npm run lint
npm run build
```

## État de sécurité et limites connues

- **Non prêt pour la production** : voir [docs/final-security-audit-report.md](docs/final-security-audit-report.md).
- Les durcissements E1-E3, M1 et M2 sont implémentés et testés localement, mais l'audit final liste des actions obligatoires avant production.
- Aucune donnée réelle ni secret n'est inclus dans ce dépôt. Les fichiers `.env`, bases locales et médias de test sont exclus de la publication.
- Ce dépôt est destiné à démontrer une démarche de développement et de sécurisation, pas à être déployé tel quel.

## Structure du dépôt

```text
backend/   API Django/DRF, apps modulaires, migrations, tests
frontend/  Application Next.js, composants, tests, assets publics
docs/      Comptes rendus de phases, schéma API, rapports de sécurité
```
