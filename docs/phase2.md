# FANAFODIKO — socle Phase 2

## Modules

- `apps.accounts` : profil de compte lié au modèle utilisateur Django existant, statuts actif/suspendu/clôturé, demandes de validation professionnelle, permissions et administration des utilisateurs.
- `apps.reference` : référentiel de pays, amorcé avec Madagascar.
- `apps.audit` : journal des actions de compte, de rôle, de référentiel et de validation, consultable en lecture seule dans l’administration.
- `apps.core` : disponibilité API et format commun des erreurs REST.

Les rôles `patient`, `professional_pending` et `professional_verified` sont des groupes Django. Un administrateur peut leur attribuer des permissions dans l’administration. Le statut `is_staff` reste réservé à l’accès administratif Django; un groupe métier ne donne pas cet accès.

## API REST

- `GET /api/health/` : contrôle de disponibilité public.
- `GET /api/v1/reference/countries/` : pays actifs.
- `GET /api/v1/accounts/professional-verifications/` : demandes du compte connecté.
- `POST /api/v1/accounts/professional-verifications/` : soumettre une demande (session authentifiée, compte actif).
- `GET /api/v1/admin/dashboard/` : indicateurs calculés sur les données présentes (staff actif seulement).
- `GET /api/v1/admin/accounts/?status=active|suspended|closed&page=1&page_size=50` : comptes paginés (staff actif seulement; maximum 200 par page).
- `GET /api/v1/admin/professional-verifications/` : demandes professionnelles pour examen.
- `POST /api/v1/admin/professional-verifications/{id}/review/` : approuver/refuser une demande avec une note facultative (staff actif seulement).
- `GET /api/schema/` et `/api/schema/swagger-ui/` : schéma OpenAPI et Swagger.

Les mutations sensibles utilisent la protection CSRF de Django. La réponse API d’erreur utilise `error.status`, `error.code`, `error.message` et `error.details`.

## Administration

Ouvrir `http://localhost:8000/admin/` et se connecter avec un utilisateur Django `is_staff` actif. Le tableau de bord montre des comptes totaux/actifs/suspendus et les demandes en attente/approuvées. Les utilisateurs et profils, groupes et permissions, pays, demandes et événements d’audit sont administrables dans leurs rubriques respectives. Les événements du journal ne sont ni modifiables ni supprimables depuis l’administration.

Une vue complémentaire est disponible à `http://localhost:3000/administration`. Elle lit les mêmes indicateurs via l’API REST et nécessite une session administrateur active sur `localhost:8000` dans le même navigateur. Le lien « Gérer les données » mène à l’administration Django.

Pour examiner une demande, sélectionner les demandes en attente dans la rubrique correspondante puis choisir l’action Approuver ou Refuser. La décision est enregistrée avec l’administrateur et l’heure; l’auteur de la demande ne peut pas l’examiner lui-même.

## Modèle et migrations

Les migrations ajoutent `reference_country`, `accounts_accountprofile`, `accounts_professionalverificationrequest` et `audit_auditevent`. Elles créent le référentiel Madagascar, les groupes métier et un profil pour chaque utilisateur préexistant. Elles ne remplacent pas le modèle utilisateur Django ni les paramètres de connexion PostgreSQL.

## Vérification locale

Après installation des dépendances et configuration existante de `.env` :

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py test --settings=config.settings.test
.\.venv\Scripts\python.exe manage.py runserver
```

Dans un autre terminal :

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
npm.cmd run dev
```

La Phase 2 ne comprend pas encore les espaces professionnels complets, les médicaments, la recherche géographique, les rendez-vous, les patients, les commandes, les partenaires, les notifications, les paiements ou la logistique.
