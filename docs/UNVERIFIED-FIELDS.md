---
type: reference
description: Le registre des champs et endpoints BoondManager que le mock expose sans preuve documentaire — à lever avec le fournisseur.
sources_of_truth:
  - src/boondmanager_mock/dataset/**
  - src/boondmanager_mock/envelope.py
review_triggers:
  - contracts/boondmanager.openapi.yaml
update_policy: propose
last_verified: 2026-07-29
---

# Champs non attestés

La spécification d'insights360 est catégorique :

> *« Do not invent BoondManager API fields. Mark unknowns `TODO` in the contract
> and raise them rather than guessing. »*

Ce fichier est le registre correspondant. Tout champ marqué
`x-boond-confidence: unverified` ou `invented` dans
`contracts/boondmanager.openapi.yaml` **doit** y figurer — un test le vérifie,
pour que l'honnêteté soit une contrainte de build et non une discipline.

## Ce qui EST attesté

Ces éléments viennent d'une intégration production vérifiée (ophelie,
`docs/adr/0002-boondmanager-scheduled-ingestion.md`) et ne sont pas en question :

- l'en-tête `X-Jwt-Client-Boondmanager`, HS256, base64url sans padding, payload
  `{"userToken","clientToken"}` ; le 422 sur signature invalide ;
- l'enveloppe `{"data": […], "meta": {"totals": {"rows": N}}}` ;
- la pagination `page` / `maxResults`, plafond 500 ;
- le filtre `keywords` ;
- les collections `resources`, `companies`, `contacts`, `projects`, `agencies`,
  le sous-onglet `resources/{id}/technical-data`, et `application/current-user` ;
- les noms d'attributs consommés par le pipeline d'ophelie (`firstName`,
  `lastName`, `email1`, `businessUnit`, `averageDailyPriceExcludingTax`, …).

## Ce qui NE l'est PAS

### 1. Le paramètre de filtre incrémental — `unverified`

**Statut** : le mock accepte **deux** formes, `updatedSince=<ISO8601>` et
`filter[updateDate][gte]=<ISO8601>`.

**Pourquoi** : l'ADR-0002 d'ophelie documente le dialecte depuis la production
et ne mentionne **aucun** filtre sur horodatage — seulement `page`,
`maxResults` et `keywords`. Le pipeline d'insights360 est pourtant incrémental
par conception (« Never full-refresh in the scheduled path »), donc il lui en
faut un.

**Coût de la correction** : une ligne. Le nom est une constante unique côté
consommateur — `insights360:extract/src/insights360_extract/boondmanager/client.py::UPDATED_SINCE_PARAM`
— et un test vérifie via `/__admin/state` que le paramètre est bien **envoyé**,
pas seulement toléré.

**À faire** : confirmer le nom réel dans la documentation du tenant
BoondManager, ou auprès du support. Retirer alors la forme non retenue.

### 2. L'attribut `updateDate` — `unverified`

**Statut** : porté par tous les items de toutes les collections.

**Pourquoi** : corollaire du point 1 — un curseur incrémental a besoin d'un
champ sur lequel s'appuyer. Le nom est plausible (BoondManager expose
`updateDate` sur plusieurs entités) mais n'est pas attesté par l'intégration
d'ophelie, qui ne l'utilise pas.

### 3. L'attribut `upn` — **ajout du mock, pas un champ fournisseur**

**Statut** : ajouté délibérément, marqué comme tel.

**Pourquoi** : tout le modèle d'autorisation d'insights360 est keyé sur l'UPN
(`dim_collaborateur.upn` unique et non nul, `acl_utilisateur.upn`, le prédicat
`USERPRINCIPALNAME()` de Power BI). BoondManager expose `email1`, qui n'est pas
la même chose : dans une organisation réelle, l'e-mail de contact et l'UPN Entra
divergent.

**Décision** : le mock expose les deux, `email1` et `upn`, avec la même valeur
par défaut. Le pipeline doit décider explicitement lequel il consomme, et cette
décision doit être documentée côté insights360 plutôt qu'implicite.

### 4. Les collections `deliveries` et `times-reports` — `unverified`

**Statut** : implémentées, avec des attributs plausibles
(`startDate`/`endDate`/`businessUnit` ; `term`/`workedDays`).

**Pourquoi** : insights360 en a besoin pour `fct_mission` et `fct_cra`.
BoondManager possède bien ces notions, mais l'intégration d'ophelie ne les
consomme pas — les noms d'attributs exacts ne sont donc pas vérifiés.

**À faire** : aligner sur la documentation avant la première extraction réelle.
La forme de l'enveloppe et la pagination, elles, sont attestées : seuls les noms
d'attributs sont en question.

### 5. La rémunération — **pas un endpoint BoondManager du tout**

**Statut** : servie sur `/__fixtures/remuneration.csv`, délibérément **hors de
`/api`**.

**Pourquoi** : aucun endpoint de rémunération par ressource n'est attesté. Le
seul champ monétaire par ressource est `averageDailyPriceExcludingTax`, qui est
un **tarif de vente**, pas un salaire. Inventer un endpoint aurait gravé une
fiction dans le contrat, le schéma, l'ADR et les tests de sécurité à la fois —
et `fct_remuneration` est justement la table la plus sensible du modèle.

Voir [`adr/0004-compensation-is-not-a-boond-endpoint.md`](adr/0004-compensation-is-not-a-boond-endpoint.md).

C'est probablement aussi la vérité métier : une rémunération vit dans une paie
ou un SIRH, pas dans l'ERP commercial.

### 6. `code` sur les agences — **ajout du mock**

**Statut** : code court de l'entité (`ENT-FR`, `ENT-BE`, `ENT-LU`).

**Pourquoi** : c'est la clé de périmètre du modèle d'autorisation d'insights360
(`acl_role_perimetre.entite`). BoondManager expose `name` sur ses agences ; rien
n'atteste qu'il expose un code court et STABLE, ce qui est pourtant la propriété
requise — un libellé renommé ne doit pas invalider un périmètre de sécurité.

**À faire** : déterminer quel champ d'agence est stable côté fournisseur. À
défaut, le mapping entité → code devient un seed versionné de plus, au même
titre que `acl_role_perimetre`.

### 7. `managerUpn` et `statut` sur les ressources — **ajouts du mock**

**Statut** : deux doublons de commodité, tous deux marqués.

`managerUpn` double la relation `mainManager`, qui est attestée. Il évite au
consommateur une résolution d'identifiant pour aplatir la hiérarchie. Les deux
sont servis et cohérents ; le consommateur peut ignorer l'ajout.

`statut` (`actif` | `sorti`) double `state` (entier), qui est attesté. Le libellé
sert aux cas limites d'insights360 — un employé sorti conserve son historique
mais perd toute visibilité. **La correspondance entre `state` et ce libellé n'est
pas vérifiée** : on suppose `state = 1` → actif. C'est le point à confirmer en
premier, parce qu'une erreur ici retirerait ou accorderait de la visibilité à
tort.

### 8. L'attribut `isDeleted` — **ajout du mock**

**Statut** : porté par tous les items, à `false` par défaut ; passé à `true` par
`POST /__admin/delete`.

**Pourquoi** : un pipeline incrémental en stratégie `merge` **ne peut pas**
observer une suppression physique sans rafraîchissement complet. Le mock
n'expose donc que la suppression logique, parce que c'est le seul cas qu'un
pipeline incrémental peut réellement traiter — et parce que prétendre le
contraire est exactement comment les tables ACL continuent d'accorder l'accès à
des partants.

**À faire** : déterminer si BoondManager expose un drapeau de suppression, et
sous quel nom. Si le fournisseur ne fait que des suppressions physiques, la
politique documentée côté insights360 (réconciliation par rafraîchissement
complet hebdomadaire) devient obligatoire, pas optionnelle.
