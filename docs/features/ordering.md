---
type: features
description: L'ordre de pagination — instable par défaut, gelé pour le profil ophelie, et le bug de client que cela a révélé.
sources_of_truth:
  - src/boondmanager_mock/envelope.py
review_triggers:
  - src/boondmanager_mock/envelope.py
  - src/boondmanager_mock/dataset/**
update_policy: auto
last_verified: 2026-07-29
---

# L'ordre de pagination

## Ce que fait le mock

| Situation | Ordre |
|---|---|
| `sort=<champ>` fourni | **stable**, trié sur ce champ (`order=asc\|desc`) |
| profil `ophelie` | **stable** — profil gelé, comportement historique |
| profil `insights360`, sans `sort` | **INSTABLE**, et délibérément |
| `BOOND_MOCK_STABLE_ORDER=true` | stable, pour du `curl` exploratoire |

L'instabilité est déterministe dans un test donné — `hash((rang de requête, id))`
— donc reproductible, tout en variant réellement d'une requête à l'autre.

## Pourquoi l'instabilité est le comportement par défaut

Une API qui ne garantit pas l'ordre de ses résultats fait **sauter des
enregistrements et en dupliquer d'autres** dès qu'on la pagine sans tri
explicite. Le mécanisme est simple : si l'ordre change entre la requête de la
page 1 et celle de la page 2, un élément qui était en fin de page 1 peut se
retrouver en début de page 2 (rendu deux fois), et son voisin disparaître.

Rien ne le signale. Aucune erreur, aucun avertissement — juste des données
incomplètes qui ressemblent à des données complètes.

Un mock qui trierait toujours ses résultats laisserait donc passer ce défaut, et
le bug attendrait la production pour se manifester. C'est exactement ce que la
spécification d'insights360 demande de reproduire : *« unstable ordering unless
an explicit sort is requested »*.

## Ce que cela a révélé, immédiatement

À la migration d'ophelie vers ce paquet, son test
`test_iter_collection_walks_every_page` a échoué :

```
assert len({item["id"] for item in items}) == 24
E   AssertionError: assert 18 == 24
```

**Dix-huit ressources sur vingt-quatre.** Le client de production d'ophelie
(`app/boond/client.py::iter_collection`) pagine avec `page` et `maxResults`
**sans jamais envoyer de tri**. Contre un mock instable, il en perd six sur
vingt-quatre.

Ce n'est pas un artefact du mock : c'est le comportement qu'aurait ce client
contre n'importe quelle API qui ne garantit pas son ordre. BoondManager le
garantit-il ? Rien ne l'atteste — et c'est bien le problème.

**Le mock n'a pas été « corrigé » pour faire passer le test.** Le profil
`ophelie` a été gelé dans son comportement historique, parce qu'un profil dit
gelé dont la sémantique de pagination change n'est pas gelé — il casse
simplement plus tard. Le constat, lui, est remonté tel quel : c'est une décision
qui appartient à ophelie, pas à son mock.

## Ce que fait un consommateur correct

`insights360:extract/…/boondmanager/client.py` envoie **toujours** un tri :

```python
params = {"page": page, "maxResults": self.page_size, "sort": "id", "order": "asc"}
```

Tri sur l'identifiant : stable, présent partout, indépendant du contenu métier.
Et son test d'extraction le vérifie **côté serveur**, via
`GET /__admin/state` → `last_query_params_by_path` — parce qu'un client qui
aurait oublié son tri passerait sinon tous les autres tests.
