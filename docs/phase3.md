# FANAFODIKO — Phase 3 : comptes professionnels

Cette phase ajoute l'inscription et la gestion du dossier de base des pharmacies, médecins, dentistes, laboratoires, coursiers indépendants et entreprises de livraison. Elle prolonge le socle Phase 2 (`accounts`, `reference`, `audit`) et conserve Django, DRF, PostgreSQL et Next.js.

## Modules et données

- `apps.professionals` : profil professionnel, informations propres à chaque catégorie, pièces justificatives privées, validation de complétude et endpoints associés.
- `apps.accounts` : inscription, connexion par session, demandes de validation et rôles existants. Les vérifications sont liées au profil professionnel.
- `apps.audit` : journalisation des inscriptions, soumissions, décisions et actions de suspension/réactivation.

Les tables ajoutées par `professionals.0001_initial` sont `professionals_professionalprofile`, `professionals_pharmacydetails`, `professionals_practitionerdetails`, `professionals_laboratorydetails`, `professionals_deliverydetails` et `professionals_professionaldocument`. Les migrations `accounts.0003` à `accounts.0005` étendent les catégories de demande et permettent la nouvelle soumission d'une demande refusée. Les profils restent reliés aux utilisateurs et aux pays du référentiel.

Une inscription crée un compte actif et un profil brouillon. La soumission requiert les champs obligatoires, les informations de catégorie et au moins un justificatif. Elle crée ou met à jour la demande existante et passe le profil en attente. Une décision d'administration approuve ou refuse le profil. Une modification après approbation retire le statut vérifié et repasse le dossier en brouillon pour une nouvelle vérification. Le statut de compte suspendu est indépendant du statut de vérification.

## API

Toutes les routes fonctionnelles sont sous `/api/v1/`. L'authentification utilise une session Django et les écritures exigent le jeton CSRF.

| Méthode et route | Usage |
|---|---|
| `GET /auth/csrf/` | Obtenir le cookie/jeton CSRF avant une mutation |
| `POST /auth/register/` | Créer un compte professionnel et sa session |
| `POST /auth/login/`, `POST /auth/logout/` | Ouvrir ou fermer une session |
| `GET /auth/me/` | Lire le compte connecté et son profil |
| `GET /professionals/categories/` | Catégories et champs spécifiques disponibles |
| `GET/PATCH /professionals/me/` | Lire ou modifier son profil et ses détails de catégorie |
| `POST /professionals/me/submit/` | Soumettre un dossier complet à validation |
| `GET/POST /professionals/me/documents/` | Lister ou téléverser ses justificatifs |
| `DELETE /professionals/me/documents/{id}/` | Supprimer un justificatif du dossier propre |
| `GET /professionals/me/documents/{id}/download/` | Télécharger un justificatif du dossier propre |
| `GET /professionals/admin/profiles/` | Lister les profils, avec filtres catégorie/statut |
| `POST /professionals/admin/profiles/{id}/suspend/` | Suspendre un compte professionnel |
| `POST /professionals/admin/profiles/{id}/reactivate/` | Réactiver un compte suspendu |
| `GET /professionals/admin/documents/` | Examiner les justificatifs |
| `GET /professionals/admin/documents/{id}/download/` | Télécharger un justificatif avec permission d'administration |

Le schéma OpenAPI et Swagger sont disponibles à `/api/schema/` et `/api/schema/swagger-ui/`. Les décisions d'approbation/refus passent par l'API d'administration Phase 2 `/api/v1/admin/professional-verifications/`.

## Interfaces

- `/professionnel/inscription` : inscription par catégorie.
- `/professionnel/connexion` : connexion.
- `/professionnel` : état de validation, informations manquantes et déconnexion.
- `/professionnel/profil` : édition des informations, justificatifs et soumission.
- `/administration` et `/admin/` : indicateurs Phase 2 et administration Django. Les profils professionnels sont filtrables dans Django Admin; les justificatifs ne sont accessibles que par une vue de téléchargement protégée.

## Sécurité et limites

Les fichiers sont limités aux PDF, JPEG et PNG, contrôlés par extension, type et signature, et plafonnés à 10 Mio. Le stockage se trouve dans `backend/private_media`, ignoré par Git. Django ne publie pas ce répertoire comme média public. En production, le serveur Web et le stockage objet doivent aussi maintenir ces fichiers privés; ne pas exposer directement `private_media`. Les réponses API ne renvoient ni chemin de stockage ni URL publique. Le téléchargement passe par une vue avec contrôle de propriété/permission, en-têtes de téléchargement et journal d'audit.

La Phase 3 ne met pas en œuvre de catalogue, recherche géographique, suivi GPS, tarifs, commandes, paiements, notifications ou logistique opérationnelle. Les coordonnées sont seulement des champs facultatifs de profil.

## Installation, lancement et vérification

Conserver le `.env` actuel et ses paramètres PostgreSQL. Après activation de l'environnement Python, depuis `backend` :

```powershell
python manage.py migrate
python manage.py runserver
```

Dans un terminal séparé, depuis `frontend` :

```powershell
npm run dev
```

Pour contrôler les changements :

```powershell
# Depuis backend
python manage.py test --settings=config.settings.test
python manage.py spectacular --validate --fail-on-warn --file ..\docs\api-schema.yaml

# Depuis frontend
npm run lint
npm run build
```

Les tests utilisent le paramétrage isolé `config.settings.test`. L'application et les migrations locales restent configurées pour PostgreSQL. Consultez aussi [README.md](../README.md) et [Phase 2](phase2.md).
