# FANAFODIKO — Phase 7 : marketplace complet, espace partenaires et commandes

Cette phase prolonge le catalogue public et l'administration du marketplace déjà présents. Elle ajoute un espace réservé aux partenaires, un panier, des demandes de commande sans paiement en ligne, un suivi client et des notifications réelles. Elle conserve strictement Django 5.2, DRF, PostgreSQL, Next.js 15, TypeScript, Tailwind, l'authentification par session, la protection CSRF, le format d'erreur commun, le journal d'audit et le stockage privé des fichiers.

> **État de ce document : spécification de l'Étape 0.** Aucun code métier, modèle, migration, fichier de configuration ni donnée PostgreSQL n'a été modifié pour sa rédaction. Sa validation déclenche l'Étape 1.

## Décisions validées avant rédaction

1. Une **commande est une réservation sans paiement en ligne**. Le paiement et la remise effective des produits se font chez le partenaire. Aucun statut de paiement n'est introduit.
2. WhatsApp utilise uniquement les **liens `wa.me` générés côté backend** à partir de `SiteConfiguration.whatsapp_number`, la configuration officielle déjà présente. Aucune WhatsApp Cloud API, aucun token, aucun template, aucun webhook et aucun envoi automatique ne sont ajoutés dans cette phase.
3. Deux nouvelles applications Django sont créées : `orders` et `notifications`.
4. Toute publication d'un produit partenaire passe par une **modération administrative obligatoire**.
5. Pour les produits existants, `stock_quantity` reste **NULL** : aucun stock n'est inventé et aucun produit existant n'est rendu commandable automatiquement.

## Périmètre

### Inclus

- Espace partenaire : tableau de bord, produits, images multiples, prix, stock, disponibilité, soumission en modération et suivi des commandes reçues.
- Administration : attribution explicite d'un vendeur à un partenaire, file de modération des produits, consultation des commandes.
- Panier serveur avec quantités validées côté backend.
- Commande/réservation avec prix et stock contrôlés côté serveur, cycle de vie complet et historique.
- Notifications en base, créées uniquement par des événements réels, avec lien WhatsApp contextuel.
- Mises à jour documentaires : `README.md`, schéma OpenAPI et création du présent document.

### Exclus explicitement

- Paiement en ligne, MVola, Orange Money, Airtel Money, cartes bancaires, remboursements et réconciliation.
- WhatsApp Cloud API / Business API, envoi automatique, statut de livraison ou de lecture, webhook Meta, templates approuvés.
- Délivrance de médicaments par FANAFODIKO, téléconsultation, ordonnance numérique, stockage d'ordonnances ou de données de santé de patient.
- Livraison opérationnelle, suivi GPS, coursiers et tarifs de transport.
- Création de faux vendeurs, faux produits, faux stocks, fausses commandes ou fausses statistiques.
- Suppression physique de données ou de migrations existantes.

### À préserver sans remplacement

- Groupes `patient`, `professional_pending`, `professional_verified` et distinction avec `is_staff`.
- `IsActiveAccount`, contrôle de compte actif et CSRF sur toutes les mutations.
- Format d'erreur `error.status`, `error.code`, `error.message`, `error.details`.
- Vérification professionnelle, documents privés et contrôle d'AMM existants.
- `CatalogProduct.image` existant : la galerie s'ajoute à côté, elle ne le remplace pas.
- Statuts existants `draft`, `published`, `archived` et `available`, `limited`, `unavailable`.
- Archivage logique des produits et désactivation logique des vendeurs, sans suppression physique.
- Filtres publics existants sur vendeur vérifié, profil approuvé et AMM vérifiée pour les médicaments.
- `private_media` non exposé comme média public ; fichiers servis uniquement par vues contrôlées.

## État du catalogue avant la Phase 7

Le catalogue disponible avant cette phase est un **catalogue d'information** :

- `CatalogSeller` est créé et vérifié par l'administration ; il n'existe aucun propriétaire partenaire.
- `CatalogProduct` contient titre, prix MGA, disponibilité déclarative, statut de publication, image unique, données médicament ou matériel, mais aucun stock quantitatif.
- La publication d'un médicament exige une pharmacie vérifiée, une AMM `verified` et une référence d'AMM.
- `requires_prescription` vaut `True` par défaut.
- L'interface publique affiche encore explicitement qu'aucune commande ni délivrance en ligne n'est proposée.

La Phase 7 ne supprime pas ces règles : elle ajoute une couche transactionnelle au-dessus, avec les garde-fous décrits ci-dessous.

## Règles métier

### Partenaires et vendeurs

- Un partenaire est un compte actif explicitement attaché à un `CatalogSeller` existant via une table d'attribution dédiée.
- Aucun vendeur n'est créé automatiquement depuis l'espace partenaire : la création et la vérification du vendeur restent administratives.
- Aucun vendeur existant n'est attribué automatiquement : l'administrateur doit choisir le compte propriétaire.
- Pour un vendeur de type `pharmacy`, le compte propriétaire doit être actif et son profil professionnel doit être approuvé, de catégorie pharmacie.
- Pour un vendeur de type `medical_supplier`, le compte propriétaire doit être actif et le vendeur doit conserver sa référence de vérification.
- Un compte ne peut être propriétaire que d'un seul vendeur.
- Un partenaire ne peut voir, modifier ou administrer que les produits et commandes rattachés à son propre vendeur. Tout accès à une ressource d'un autre vendeur renvoie `404`, sans révéler son existence.

### Produits, prix, stock et disponibilité

- `stock_quantity` est un entier positif ou nul, ou `NULL` lorsqu'il n'a jamais été renseigné.
- `NULL` signifie « stock non renseigné » et rend le produit **non commandable** ; il n'est pas interprété comme zéro ni comme stock illimité.
- Seul un stock renseigné et strictement positif permet une commande, en plus des conditions de publication et de vérification déjà présentes.
- `availability` reste une information déclarative et conservée pour l'affichage public. Le contrôle de commande utilise la valeur réelle de `stock_quantity`.
- Le prix est toujours relu depuis la base côté backend. Aucun prix, remise ou total envoyé par le client n'est accepté.
- Toute modification réelle de prix est enregistrée dans un historique dédié, sans ligne rétroactive fictive.
- Les images partenaires sont des fichiers JPEG, PNG ou WebP, avec validation de type et de signature, stockés dans `private_media` et servis par une vue contrôlée.
- Un produit modifié après approbation repasse en attente de modération avant toute nouvelle publication.

### Modération

- Statuts existants conservés : `draft`, `published`, `archived`.
- Statut de modération ajouté, distinct : `not_required`, `pending`, `approved`, `rejected`.
- Valeur `not_required` utilisée pour les produits déjà publiés avant la Phase 7, afin de ne pas les masquer ni les modifier artificiellement.
- Un produit partenaire soumis passe en `pending` et ne peut pas être publié tant qu'il n'est pas `approved`.
- Un produit `rejected` peut être corrigé par le partenaire puis resoumis.
- L'administrateur approuve ou refuse avec une note facultative ; la décision est horodatée, attribuée et journalisée dans `AuditEvent`.
- Un administrateur ne modère pas une décision déjà rendue sans nouvelle soumission.

### Panier

- Le panier est attaché au compte client connecté, pas au navigateur.
- Une quantité est un entier compris entre `1` et `99`.
- L'ajout au panier vérifie que le produit est publié, approuvé, vendu par un vendeur vérifié actif, avec stock renseigné et positif.
- Le panier affiche un prix indicatif calculé serveur ; ce prix est recomposé au moment de la commande.
- La suppression d'un article du panier n'affecte pas le stock, aucune réservation n'étant effectuée avant la commande.

### Commande et réservation

- `POST /api/v1/orders/` transforme le panier en commande dans une transaction atomique.
- Les lignes de commande figent le titre, le prix unitaire et la quantité au moment de la commande.
- Le stock est verrouillé puis décrémenté de façon atomique ; une commande est refusée si le stock est insuffisant.
- Aucun champ de paiement n'est créé. Le montant total est indicatif et le texte de l'interface précise que le paiement se fait chez le partenaire.
- Le cycle de vie est :
  - `awaiting_seller` → `accepted` ou `rejected`
  - `accepted` → `preparing`
  - `preparing` → `ready`
  - `ready` → `completed`
  - `awaiting_seller` → `cancelled` uniquement avant acceptation
- Toute transition est enregistrée dans un événement horodaté avec acteur, statut précédent, nouveau statut et note.
- Un produit qui redevient disponible après une commande ne réactive jamais automatiquement une commande refusée ou annulée.
- Une commande complétée n'est pas modifiable.

### Médicaments et ordonnance

- Les médicaments restent réservés aux pharmacies vérifiées avec AMM vérifiée et référence.
- Pour un médicament avec `requires_prescription=True`, la commande est une **réservation sous réserve de présentation de l'ordonnance chez le pharmacien**.
- La finalisation d'une telle commande exige la confirmation explicite du pharmacien que l'ordonnance a été vérifiée.
- FANAFODIKO ne stocke ni image, ni numéro, ni contenu d'ordonnance et ne réalise aucune validation médicale.
- Aucun message automatique ne suggère que la commande vaut délivrance ou conseil médical.

### Notifications et WhatsApp

- Une notification n'est créée que par un événement réel : commande créée, acceptée, refusée, préparée, prête, complétée, annulée, modération approuvée/rejetée ou stock épuisé.
- Le destinataire est le compte concerné : client pour sa commande, partenaire pour les commandes de son vendeur, soumetteur pour une modération.
- Chaque notification possède un titre, un corps, un type, une référence d'objet, un lien applicatif, une date de création et une date de lecture.
- Le lien WhatsApp est construit côté backend avec le numéro issu de `SiteConfiguration.whatsapp_number`, après validation et normalisation du numéro.
- Le message contient la référence de commande ou de produit concernée, sans données de santé.
- `whatsapp_opt_in` est désactivé par défaut. Le lien n'est proposé que si le destinataire a explicitement activé cette préférence.
- Aucun message n'est envoyé automatiquement : la notification fournit un lien `wa.me` que l'utilisateur choisit d'ouvrir.
- Aucun statut de livraison, de lecture WhatsApp ou de template n'est simulé.

## Modèles prévus

Les modèles suivants sont **spécifiés**, pas encore créés. Leur création appartient à l'Étape 1.

### Application `orders`

| Modèle | Finalité |
|---|---|
| `Cart` | Panier attaché à un `AccountProfile`. |
| `CartItem` | Produit et quantité dans un panier. |
| `Order` | Réservation avec client, vendeur, statut, référence, montant indicatif calculé serveur et horodatages de transition. |
| `OrderItem` | Ligne immutable : produit, titre figé, prix unitaire figé, quantité, indicateur ordonnance et confirmation pharmacien. |
| `OrderEvent` | Traçabilité des transitions de statut avec acteur, note et horodatage. |

### Application `notifications`

| Modèle | Finalité |
|---|---|
| `Notification` | Notification réelle liée à un compte, un type, un objet, un lien et une date de lecture. |
| `NotificationPreference` | Préférence d'ouverture des liens WhatsApp, désactivée par défaut. |

### Extension additive du marketplace

| Modèle ou champ | Finalité |
|---|---|
| `SellerOwner` | Attribution explicite et unique d'un compte à un vendeur existant. |
| `ProductImage` | Galerie additive avec fichier privé, ordre, texte alternatif et image principale. |
| `stock_quantity` | Stock réel, nullable, jamais initialisé avec une valeur inventée. |
| `stock_updated_at` | Horodatage de la dernière modification de stock. |
| `moderation_status` | Statut de modération distinct du statut de publication. |
| `submitted_for_review_at`, `reviewed_by`, `reviewed_at`, `review_notes` | Suivi de la décision administrative. |
| `ProductPriceHistory` | Historique des changements de prix réels à partir de la Phase 7. |

Aucune suppression de champ, aucune suppression de table et aucune suppression de migration ne sont prévues. Les champs `null=True` ou à valeur neutre sont utilisés pour préserver les données existantes.

## Permissions

| Permission | Règle |
|---|---|
| `IsActiveAccount` | Conservée pour toutes les routes authentifiées ; compte `active` et `user.is_active`. |
| `IsPartnerOwner` | Vérifie l'attribution `SellerOwner` du compte connecté ; filtre obligatoire dans `get_queryset()` et `get_object()`. |
| `IsOrderCustomer` | Le client ne voit que ses propres commandes. |
| `IsOrderSeller` | Le partenaire ne traite que les commandes de son vendeur. |
| `IsAdminUser` | Conservé pour l'attribution des vendeurs, la modération et la consultation globale. |
| `IsStaffWithPermission` | Conservé pour les endpoints professionnels existants ; non remplacé. |
| CSRF | Exigé pour toutes les mutations par session. |
| Accès forbidden | Une ressource d'un autre propriétaire renvoie `404`, pas `403`, afin d'éviter l'énumération. |

Les permissions sont appliquées dans les vues et dans les sérializers, jamais uniquement dans l'interface.

## Endpoints prévus

Toutes les routes sont sous `/api/v1/`. Elles suivent le format d'erreur commun existant.

### Espace partenaire

| Méthode et route | Usage |
|---|---|
| `GET /partner/dashboard/` | Indicateurs calculés sur les seules données du vendeur attribué. |
| `GET/POST /partner/products/` | Lister ou créer ses produits. |
| `GET/PATCH/DELETE /partner/products/{id}/` | Lire, modifier ou archiver son produit. |
| `POST /partner/products/{id}/submit-review/` | Soumettre le produit à modération. |
| `PATCH /partner/products/{id}/stock/` | Mettre à jour le stock réel. |
| `PATCH /partner/products/{id}/availability/` | Mettre à jour la disponibilité déclarative. |
| `GET/POST /partner/products/{id}/images/` | Lister ou ajouter des images. |
| `DELETE /partner/products/{id}/images/{image_id}/` | Supprimer une image de sa propre galerie. |
| `GET /partner/orders/` | Lister les commandes de son vendeur. |
| `GET /partner/orders/{id}/` | Lire une commande et son suivi. |
| `POST /partner/orders/{id}/accept/` | Accepter une commande. |
| `POST /partner/orders/{id}/reject/` | Refuser une commande avec motif. |
| `POST /partner/orders/{id}/prepare/` | Passer en préparation. |
| `POST /partner/orders/{id}/mark-ready/` | Marquer la réservation prête. |
| `POST /partner/orders/{id}/complete/` | Finaliser après remise et vérification d'éventuelle ordonnance. |

### Client

| Méthode et route | Usage |
|---|---|
| `GET/POST/DELETE /cart/` | Lire, ajouter ou vider le panier. |
| `PATCH/DELETE /cart/items/{id}/` | Modifier ou retirer une quantité. |
| `POST /orders/` | Créer la réservation depuis le panier, avec validation serveur. |
| `GET /orders/` | Historique des commandes du client. |
| `GET /orders/{id}/` | Détail et suivi de sa commande. |
| `POST /orders/{id}/cancel/` | Annuler avant acceptation du vendeur. |

### Administration

| Méthode et route | Usage |
|---|---|
| `POST /admin/marketplace/sellers/{id}/assign-owner/` | Attribuer explicitement un vendeur à un compte partenaire. |
| `GET /admin/marketplace/moderation/` | File des produits en attente de modération. |
| `POST /admin/marketplace/products/{id}/approve/` | Approuver un produit soumis. |
| `POST /admin/marketplace/products/{id}/reject/` | Refuser un produit soumis avec note. |
| `GET /admin/marketplace/price-history/{id}/` | Consulter l'historique réel des prix. |
| `GET /admin/orders/` | Consulter l'ensemble des commandes pour supervision. |

### Notifications

| Méthode et route | Usage |
|---|---|
| `GET /notifications/` | Lister ses notifications. |
| `GET /notifications/unread-count/` | Nombre de notifications non lues. |
| `POST /notifications/{id}/read/` | Marquer une notification comme lue. |
| `POST /notifications/read-all/` | Marquer toutes ses notifications comme lues. |
| `GET/PATCH /notifications/preferences/` | Lire ou modifier `whatsapp_opt_in`. |

## Interfaces prévues

| Route | Usage |
|---|---|
| `/partenaire` | Tableau de bord du partenaire. |
| `/partenaire/produits` | Liste de ses produits. |
| `/partenaire/produits/{id}` | Édition produit, stock, disponibilité et soumission. |
| `/partenaire/images` | Galerie de ses images par produit. |
| `/partenaire/commandes` | Commandes reçues. |
| `/partenaire/commandes/{id}` | Traitement et suivi d'une commande. |
| `/panier` | Panier client. |
| `/commandes` | Historique client. |
| `/commandes/{reference}` | Suivi client. |
| `/commandes/confirmation/{reference}` | Confirmation de réservation, sans paiement. |

Le lien vers l'espace partenaire est ajouté à la navigation publique uniquement lorsque l'API confirme une attribution de vendeur active. L'interface ne constitue jamais un contrôle de sécurité.

## Anomalies et contradictions signalées — non corrigées dans l'Étape 0

Les points suivants sont constatés et doivent être traités explicitement aux étapes prévues, sans correction automatique dans ce document :

1. Les textes actuels du catalogue affirment qu'aucune commande ni délivrance en ligne n'est proposée (`frontend/src/components/MarketplacePublic.tsx:70,143`, `MarketplaceAdmin.tsx:118`). La Phase 7 change le périmètre vers une réservation sans paiement ; ces textes devront être reformulés à l'Étape 9, sans supprimer les avertissements AMM et ordonnance.
2. `docs/api-schema.yaml` est périmé : il omet les routes patient, `site-content` et `marketplace` déjà existantes. Il sera régénéré à l'Étape 7 uniquement.
3. `AdminProfessionalDocumentSerializer.get_download_url()` pointe vers la route propriétaire `/professionals/me/documents/{id}/download/` au lieu de la route admin `/professionals/admin/documents/{id}/download/`. Anomalie héritée, à corriger à l'Étape 7.
4. La catégorie `clinic` existe dans `ProfessionalVerificationRequest.Category` mais pas dans `ProfessionalCategory`. Contradiction de taxonomie héritée, non modifiée ici.
5. `/api/health/` renvoie `version: 0.1.0` alors que le schéma OpenAPI annonce `0.3.0`. Incohérence de version signalée.
6. `CORS_ALLOWED_ORIGINS` et `CSRF_TRUSTED_ORIGINS` sont codés en dur pour `localhost` et `127.0.0.1` dans `config/settings/base.py:34-36`, y compris hérités en production. Point de déploiement à arbitrer plus tard.
7. `DJANGO_DEBUG` figure dans `.env.example` mais n'est pas lu par la configuration Django actuelle.
8. Le lien « Gérer les données » de `/administration` pointe en dur vers `http://localhost:8000/admin/`. À remplacer par une URL configurable à l'Étape 7.
9. La suite de tests Django utilise SQLite en mémoire et `InMemoryStorage`, tandis que la production utilise PostgreSQL et `private_media`. Les contraintes PostgreSQL réelles et le stockage privé réel ne sont donc pas encore couverts.
10. `frontend/src/app/conditions/page.tsx` et `frontend/src/app/confidentialite/page.tsx` restent des brouillons non contractuels. Aucune collecte de données de santé n'est prévue par la Phase 7, mais les textes juridiques devront être validés par l'exploitant avant toute évolution ultérieure.
11. Le résumé OpenAPI de la route `reactivate/` reprend celui de `suspend/`. Anomalie documentaire héritée.
12. Aucun document de Phase 1, 4, 5 ou 6 n'existe dans le dépôt. La Phase 7 est donc spécifiée à partir du code existant, pas de documents de phase absents.

## Migrations et sécurité des données

- Les seules migrations prévues sont additives : `CreateModel`, `AddField` avec `null=True` ou valeur neutre, et `AddConstraint` non destructif.
- `marketplace.0002_*` ajoute les extensions catalogue sans supprimer `CatalogProduct.image`.
- `orders.0001_initial` et `notifications.0001_initial` créent de nouvelles tables.
- Aucune donnée existante n'est backfillée avec une valeur inventée.
- Aucune migration n'est exécutée dans l'Étape 0.
- PostgreSQL n'est ni réinitialisé, ni modifié, ni interrogé en écriture.

## Critères d'acceptation de la Phase 7

### Données et migrations

- `makemigrations --check --dry-run` ne révèle aucune dérive après création des migrations prévues.
- `migrate --plan` ne contient que des opérations additives.
- Les produits existants restent visibles avec `stock_quantity=NULL` et `moderation_status=not_required`.
- Aucun prix historique, stock, vendeur, produit, commande ou notification fictif n'existe.

### Sécurité et isolation

- Un partenaire ne peut accéder qu'à son vendeur, ses produits et ses commandes ; tout autre objet renvoie `404`.
- Un client ne peut consulter que ses propres commandes.
- Un compte suspendu ou inactif ne peut effectuer aucune mutation.
- Toutes les mutations passent par CSRF.
- Aucun chemin de fichier privé n'est exposé dans une réponse API.

### Commandes

- Un produit avec `stock_quantity=NULL`, `0`, non approuvé ou non publié ne peut pas être commandé.
- Le prix et la quantité validés sont ceux du backend, jamais ceux du client.
- Une commande concurrente ne peut pas dépasser le stock disponible.
- Le cycle de vie refuse toute transition non autorisée.
- Un médicament nécessitant une ordonnance ne peut pas être complété sans confirmation du pharmacien.
- Aucun champ ni événement de paiement n'est créé.

### Notifications et WhatsApp

- Toute notification correspond à un événement réel.
- Aucune notification n'est créée pour un événement simulé ou de test en base de production.
- Le lien `wa.me` utilise exclusivement `SiteConfiguration.whatsapp_number`.
- Le lien n'est fourni que si `whatsapp_opt_in` est vrai.
- Aucun envoi automatique, token, webhook ou statut de livraison n'est introduit.

### Documentation et vérification

- `README.md` mentionne la Phase 7 et renvoie au présent document.
- `docs/api-schema.yaml` est régénéré avec la commande documentée dans `docs/phase3.md:73`.
- Les tests Django couvrent l'isolement partenaire, le stock, le prix serveur, les transitions, l'ordonnance et les notifications.
- `npm run lint` et `npm run build` réussissent.
- Les tests restent isolés du PostgreSQL de production.

## Vérification locale prévue aux étapes suivantes

```powershell
# Depuis backend, sans toucher aux données de production
python manage.py test --settings=config.settings.test
python manage.py makemigrations --check --dry-run
python manage.py spectacular --validate --fail-on-warn --file ..\docs\api-schema.yaml

# Depuis frontend
npm run lint
npm run build
```

La commande `migrate` réelle ne sera proposée qu'après validation du plan de migrations de l'Étape 1 et lecture de `migrate --plan`. Le `.env` actuel et la configuration PostgreSQL existante sont conservés.

Consulter aussi [README.md](../README.md), [Phase 2](phase2.md) et [Phase 3](phase3.md).
