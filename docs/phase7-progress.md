# FANAFODIKO — Phase 7 : rapport de progression

Ce fichier suit l'avancement des étapes 3 à 11 sans remplacer `docs/phase7.md`.

## État initial de la mission

- Étapes 0 à 2 terminées selon le contexte transmis, mais vérification en cours contre le dépôt réel.
- Aucune migration PostgreSQL ne doit être exécutée.
- Environnement de test autorisé : SQLite isolé via `config.settings.test`.
- Dernière mise à jour : 2026-11-25.

## Étape 3 — Produits, images, prix, stock et modération — TERMINÉE

- [x] Lecture et audit des modèles/serializers/vues existants
- [x] Implémentation CRUD partenaire
- [x] Galerie privée et validations fichiers
- [x] Historique des prix
- [x] Règles stock et commandabilité
- [x] Modération et audit
- [x] Tests complets (87 tests à ce stade)

## Étape 4 — Panier serveur — TERMINÉE

- [x] Implémentation
- [x] Tests (94 tests à ce stade)

## Étape 5 — Commandes et réservations — TERMINÉE

- [x] Implémentation
- [x] Tests de concurrence et transitions (104 tests à ce stade)
- [x] Migration additive `orders.0002_orderitem_regulatory_snapshots` préparée, non appliquée

## Étape 6 — Notifications et WhatsApp — TERMINÉE

- [x] Implémentation (boîte de réception, préférences, consentement révocable, liens `wa.me` backend)
- [x] Intégration événements réels : commandes, transitions, modération, stock épuisé
- [x] Aucun envoi automatique, aucun statut de livraison, aucune donnée de santé dans les messages
- [x] Tests (112 tests à ce stade)

## Étape 7 — Administration et OpenAPI — TERMINÉE

- [x] Correction de l’URL admin des documents professionnels
- [x] Résumé OpenAPI distinct pour la réactivation professionnelle
- [x] Version de santé alignée sur `SPECTACULAR_SETTINGS["VERSION"]`
- [x] Origines CORS/CSRF et `DJANGO_DEBUG` configurables par environnement
- [x] Lien administrateur Django configurable côté frontend
- [x] Endpoints partenaire/administration complétés (dashboard, stock, disponibilité, modération, prix, commandes, vidage du panier)
- [x] Schéma `docs/api-schema.yaml` régénéré sans avertissement ni erreur
- [x] Vérifications backend : `check`, 112 tests, `makemigrations --check --dry-run`, `showmigrations --plan`

## Étape 8 — Frontend partenaire — TERMINÉE

- [x] `PartnerSpace.tsx` : tableau de bord, produits, édition, stock, disponibilité, soumission, archivage, galerie privée, commandes et traitement
- [x] Routes réelles : `/partenaire`, `/partenaire/produits`, `/partenaire/produits/{id}`, `/partenaire/images`, `/partenaire/commandes`, `/partenaire/commandes/{id}`
- [x] Toutes les mutations passent par `apiMutate`, qui obtient d’abord le cookie CSRF
- [x] Lien « Espace partenaire » affiché seulement après réponse positive de `GET /v1/partner/dashboard/`
- [x] Confirmation explicite de vérification d’ordonnance disponible à chaque transition autorisée

## Étape 9 — Frontend client — TERMINÉE

- [x] `ClientSpace.tsx` : ajout au panier depuis la fiche publique, panier, quantités, retrait, vidage, réservation, historique, suivi, confirmation et annulation
- [x] Routes réelles : `/panier`, `/commandes`, `/commandes/{reference}`, `/commandes/confirmation/{reference}`
- [x] Messages obligatoires affichés : aucun paiement en ligne, retrait chez le partenaire, ordonnance vérifiée par le pharmacien, aucune donnée d’ordonnance stockée
- [x] Textes contradictoires du catalogue et de l’administration remplacés par le périmètre « réservation sans paiement »
- [x] `WhatsAppFloating` et `AdministrationContent` n’utilisent plus `NEXT_PUBLIC_WHATSAPP_NUMBER`; seule la configuration backend est utilisée

## Étape 10 — Tests complets — TERMINÉE

- [x] Backend : `python manage.py check --settings=config.settings.development` — aucun problème
- [x] Backend : `python manage.py test --settings=config.settings.test` — 112 tests, `OK`
- [x] Backend : `python manage.py makemigrations --check --dry-run --settings=config.settings.development` — `No changes detected`
- [x] Backend : `python manage.py showmigrations --plan --settings=config.settings.development` — 4 migrations Phase 7 non appliquées
- [x] Backend : `python manage.py spectacular --validate --fail-on-warn --file ..\docs\api-schema.yaml` — aucun avertissement
- [x] Frontend : `npm run test` — 21 tests, 0 échec
- [x] Frontend : `npm run lint` — aucune erreur
- [x] Frontend : `npm run build` — 27 pages générées, aucune erreur de type

## Étape 11 — Validation finale — TERMINÉE pour la préparation, en attente d’autorisation PostgreSQL

### Rapport final — 15 points de validation

1. **Périmètre documentaire** : `docs/phase7.md` reste le document de référence; le présent fichier suit uniquement l’avancement. Aucune phase absente n’a été réécrite.
2. **Produits partenaire (étape 3)** : CRUD, galerie privée, validation MIME/extension/signature/taille, historique des prix réel, règles `stock_quantity=NULL`/0, modération et audit sont implémentés et testés.
3. **Panier (étape 4)** : accès patient uniquement, prix calculés côté serveur, quantité 1–99, contrôles de commandabilité et d’AMM, isolation des comptes, ajout/modification/retrait.
4. **Commandes (étape 5)** : checkout atomique avec verrous, stock sécurisé, une commande par vendeur, snapshots réglementaires, `OrderEvent`, transitions autorisées, motif de refus et sauvegarde d’ordonnance.
5. **Notifications (étape 6)** : notifications créées uniquement par des événements réels, boîte de réception, lecture, consentement révocable, lien `wa.me` généré côté backend, audit, annulation client.
6. **Administration et OpenAPI (étape 7)** : corrections héritées, endpoints dashboard/modération/prix/commandes complétés, schéma régénéré sans avertissement ni erreur.
7. **Frontend partenaire (étape 8)** : six routes réelles, composants `PartnerSpace`, mutations avec CSRF, navigation conditionnée par l’API, traitement ordonnance/stock/modération.
8. **Frontend client (étape 9)** : quatre routes réelles, composants `ClientSpace`, réservation sans paiement, suivi par référence, annulation avant acceptation.
9. **Messages réglementaires** : absence de paiement en ligne, retrait chez le partenaire, vérification ordonnance par le pharmacien et non-stockage des données d’ordonnance sont affichés sur les parcours concernés.
10. **Sécurité et isolation** : `SellerOwner` est la seule source d’autorité partenaire; `IsActiveAccount` est conservé; les ressources d’autrui renvoient `404`; CSRF requis sur les mutations; le lien partenaire n’est qu’un indice d’interface.
11. **Données non inventées** : `stock_quantity=NULL` reste inconnu et non commandable; aucun backfill de prix, stock, vendeur, commande ou notification fictif; conservateur des groupes et de `CatalogProduct.image`.
12. **Paiement et WhatsApp** : aucun moyen de paiement, champ, événement ou webhook de paiement; aucun WhatsApp Cloud API, token, envoi automatique ou statut de livraison.
13. **Migrations** : `makemigrations --check --dry-run` ne détecte aucune dérive; `showmigrations --plan` liste uniquement `marketplace.0002_*`, `notifications.0001_initial`, `orders.0001_initial` et `orders.0002_orderitem_regulatory_snapshots` comme non appliquées.
14. **Vérifications automatisées** : backend `check` OK, 112 tests Django OK, OpenAPI sans avertissement; frontend 21 tests Node, lint et build OK. Un avertissement Node non bloquant sur un ancien fichier `.js` reste signalé par le runners de test.
15. **Arrêt et points ouverts** : aucune migration ni action PostgreSQL réelle n’a été exécutée; aucun commit/push/merge. Subissent encore une décision explicite : migration PostgreSQL, compatibilité réelle `private_media`, pages juridiques définitives, taxonomie `clinic`, documents de phases 1/4/5/6 absent et écart SQLite/PostgreSQL.

### Plan PostgreSQL — préparé, non exécuté

- Sauvegarde avant toute migration : `pg_dump --format=custom --file=backup_fanafodiko_pre_phase7.dump "$DATABASE_URL"`.
- Vérification : `python manage.py showmigrations --plan --settings=config.settings.production`, puis revue humaine des quatre migrations en attente.
- Application uniquement après autorisation explicite : `python manage.py migrate --settings=config.settings.production`.
- Restauration d’urgence uniquement sur autorisation explicite : `pg_restore --clean --if-exists --dbname="$DATABASE_URL" backup_fanafodiko_pre_phase7.dump`.
- Le `.env` et la base PostgreSQL actuels restent inchangés jusqu’à cette autorisation.

## Mission complémentaire — WhatsApp, administration locale et commandabilité (2026-11-25)

1. **Bouton WhatsApp** : `WhatsAppFloating.tsx` lit uniquement `/v1/site-content/public/configuration/`, construit `https://wa.me/<chiffres>?text=…`, masque le bouton si le numéro est absent et affiche « WhatsApp non configuré » en développement. Aucun `NEXT_PUBLIC_WHATSAPP_NUMBER`, Cloud API, token, webhook, envoi automatique ou statut de livraison. Lien vérifié : `https://wa.me/[NUMERO_ANONYMISE]?text=Bonjour%2C%20je%20souhaite%20obtenir%20des%20informations%20sur%20FANAFODIKO.` ; ouverture confirmée vers `api.whatsapp.com/send/`.
2. **Configuration admin WhatsApp** : `AdministrationContent.tsx` affiche « WhatsApp n’est pas configuré. Le bouton public est masqué… », enregistre via `PATCH /v1/site-content/admin/configuration/` et rappelle qu’aucun message n’est envoyé automatiquement. Test UI : numéro vidé → message admin + bouton public masqué ; numéro restauré → lien public réapparu.
3. **URLs et espaces** : `/administration` (opérations + gestion du contenu), `/professionnel` ( demande/inscription/connexion/profil), `/partenaire`, `/panier`, `/commandes`, `/medicaments`, `/materiel-medical`, `/recherche`. Le lien « Espace partenaire » dépend de `GET /v1/partner/dashboard/`.
4. **Administration** : `AdminOperations.tsx` couvre demandes professionnelles (validation/refus avec motif), profils/justificatifs, pharmacies et fournisseurs (vérification, révocation, assignation `SellerOwner`), modération produits (approbation/refus avec motif), réservations, notifications (lecture individuelle et globale). Les listes `orders`/`notifications` acceptent tableau ou réponse paginée. Tests UI réels : refus produit id 1 (`draft`/`rejected` + motif), refus demande id 3 (`rejected` + motif), lecture puis lecture globale des notifications de test.
5. **Partenaire** : tableau de bord, fiches, galerie privée, images principales, stock/disponibilité, modération, commandes (acceptée → préparation → prête → finalisée), notifications. `SellerOwner` reste seule source d’autorité ; chaque compte ne voit que son vendeur et ses produits. Testé avec `fournisseur.demo` (vendeur 2, produit 1) et `pharmacie.demo` (vendeur 1, produit 2, AMM `verified` fictive, `requires_prescription=true`).
6. **Client et catalogue** : réservation sans paiement, panier serveur, suivi par référence, ordonnance confirmée par le pharmacien. Correctif commandabilité : `CatalogProduct.orderability_reason`/`is_orderable` exposés par le sérialiseur public et partagés avec `validate_orderable_product` ; la fiche indisponible ou à stock `NULL` affiche désormais « Réservation indisponible » sans formulaire. Vérifié navigateur sur le paracétamol de démonstration (`Indisponible`, aucun bouton) et sur le stéthoscope disponible (formulaire présent).
7. **Données de démonstration** : uniquement dans `backend/local-test.sqlite3` et `backend/local-test-media`, préfixées `TEST –` ; comptes `admin.demo`/`AdminDemo123!`, `patient.demo`/`PatientDemo123!`, `pending.demo`/`PendingDemo123!`, `pharmacie.demo`/`PharmacieDemo123!`, `fournisseur.demo`/`FournisseurDemo123!`, `autre.demo`/`AutreDemo123!`. `stock_quantity=NULL` reste inconnu et non commandable ; AMM et modération obligatoires. Aucune donnée fictive en PostgreSQL.
8. **Validations finales** : backend `check` OK, `test` **114 tests OK**, `makemigrations --check --dry-run` = `No changes detected`, `spectacular --validate --fail-on-warn` OK (schéma régénéré avec `is_orderable`/`orderability_reason`) ; frontend `npm test` **28 tests OK**, `npm run lint` OK, `npm run build` OK (27 pages). Serveurs locaux : backend `config.settings.local_test` sur `127.0.0.1:8001`, frontend sur `3000` avec `NEXT_PUBLIC_API_URL=http://localhost:8001/api` ; les serveurs `development` sur `8000` sont préservés.
9. **Fichiers et points ouverts** : modifiés — `WhatsAppFloating.tsx`, `AdministrationContent.tsx`, `AdminOperations.tsx`, `ClientSpace.tsx`, `MarketplacePublic.tsx`, `marketplace.d.mts`, `package.json`, nouveaux tests `whatsapp-ui`, `orderability-ui`, `admin-operations`, backend `models.py`/`serializers.py`/`services.py`/`tests.py` des apps marketplace et orders, `local_test.py`, `seed_local_demo.py`, `docs/api-schema.yaml`, ce rapport. Aucune migration des quatre migrations Phase 7 n’a été appliquée à PostgreSQL, aucun commit/push/merge/déploiement. Restent à décider : migration PostgreSQL réelle, compatibilité `private_media`, pages juridiques définitives et taxonomie `clinic`.

## Mission complémentaire — promotions centralisées, espace acheteur et administration (2026-11-25)

1. **Cycles de promotion** : nouvelle app `apps.promotions` avec `Promotion`, `Redemption`, statuts `pending → approved → active` puis `paused`/`removal_requested`/`archived`. La validation administrative centrale est obligatoire et ne publie jamais directement : le partenaire doit activer lui-même la promotion approuvée pour la rendre publique. Le refus exige un motif enregistré, la resoumission repasse en `pending` et efface la note précédente. Aucune suppression physique : la demande d’archivage masque immédiatement la promotion et l’administration valide l’archivage définitif dans l’audit.
2. **Prix et coupons côté serveur** : `PromotionWriteSerializer` accepte uniquement produit, code, type/valeur de remise et dates ; `original_price_mga` et `promotional_price_mga` sont dérivés de `product.price_mga` par `derive_promotion_prices`. Le coupon est limité au produit concerné, à sa fenêtre de validité et à un quota de réservations ; `cart_pricing()` et `checkout()` calculent sous-total, remise et total côté backend, avec instantané du coupon sur `Cart`, `Order` et `OrderItem`. Le client n’envoie aucun prix, montant ou total.
3. **Espace acheteur complet** : carnet d’adresses patient (`/v1/accounts/patient/addresses/`) avec création, modification, adresse principale et archivage logique ; propriété stricte vérifiée côté backend ; sélection au checkout et instantané des coordonnées dans la réservation. Les adresses restent des coordonnées de retrait/contact : aucune livraison opérationnelle. `/panier` affiche le coupon serveur, la remise et le total calculés par l’API ; le détail de commande ajoute la timeline visuelle issue des événements serveur, le coupon, les prix figés et les notes vendeur.
4. **Catalogue public et image produit** : seules les promotions actives et les fiches approuvées/publiées sont exposées dans `/promotions`, le bandeau public, les cartes et les fiches détaillées, avec badges `PROMO`, prix barré et conditions du coupon. Le prix affiché utilise `effective_price_mga` fourni par le backend. Le correctif image conserve la garde `naturalWidth <= 1 || naturalHeight <= 1`, `onError`, la référence/le `useEffect` pour les images mises en cache et le libellé « Image non fournie » : le bloc vert 1×1 issu de la démo locale ne réapparaît plus.
5. **Espace partenaire et administration** : `/partenaire/promotions` permet création, modification des offres en attente/refusées, resoumission, activation, désactivation, demande d’archivage et consultation des résultats. `/administration` dispose d’un onglet « Promotions » avec validation, refus motivé et archivage centralisés ; aucun bouton d’activation publique n’y est présent. Les enums et schémas correspondants figurent dans `docs/api-schema.yaml`.
6. **Sécurité conservée** : `SellerOwner` reste la seule autorité partenaire ; `IsActiveAccount`, les groupes `patient`/`professional_pending`/`professional_verified`, le cookie `sessionid`, le CSRF, l’audit, les contrôles AMM/modération et `private_media` restent inchangés. Les tests couvrent l’isolation vendeur/client, l’impossibilité de publication directe, le quota, l’expiration, le coupon invalide, la propriété de l’adresse, la portée des commandes partenaire, la validation administrative et l’AMM.
7. **Validations automatisées finales** : backend `check` OK ; **125 tests Django OK** ; `makemigrations --check --dry-run` = `No changes detected` ; `spectacular --validate --fail-on-warn --file ..\docs\api-schema.yaml` sans avertissement. Frontend `npm test` = **40 tests OK**, `npm run lint` OK, `npm run build` OK (**30 pages** générées). Le seul avertissement restant est un message Node non bloquant sur un ancien fichier `.js` du runner de tests.
8. **Vérification navigateur** : après redémarrage du backend local avec le bon interpréteur (un ancien processus `--noreload` servait encore le code antérieur et renvoyait `404` sur `/v1/promotions/public/`), `GET /v1/promotions/public/` répond `200` et `/promotions` affiche l’état vide sans erreur console. Les écrans `/panier` (section coupon désactivée si le panier est vide), `/patient/adresses` (formulaire et liste vides), `/partenaire/promotions` (formulaire actif avec `fournisseur.demo`) et `/administration` (onglet « Promotions » opérationnel) ont été ouverts sans erreur bloquante. La fiche `test-gants-dexamen-demonstration-8b321110` charge une image réelle de **550 × 550** via l’endpoint backend, sans libellé « Image non fournie ». Les sessions de démonstration ont été restaurées sur le compte administrateur.
9. **Environnement et limites** : backend local `config.settings.local_test` sur `127.0.0.1:8001` avec `backend/local-test.sqlite3`, frontend `http://localhost:3000` avec `NEXT_PUBLIC_API_URL=http://localhost:8001/api`. Les migrations ont été appliquées uniquement à SQLite local (`accounts.0006_buyeraddress`, `promotions.0001_initial`, `orders.0003_...`). Aucune base réelle, migration PostgreSQL, donnée de production, commit, push, merge ou déploiement n’a été modifié. Aucun paiement en ligne, webhook, envoi WhatsApp automatique ni numéro d’ordonnance n’a été ajouté.

## Contraintes permanentes

- Ne jamais exécuter `migrate`.
- Ne jamais modifier PostgreSQL réel.
- Ne jamais supprimer ou réécrire une migration existante.
- Préserver les groupes et permissions existants.
- Aucun paiement en ligne, aucun WhatsApp Cloud API.
