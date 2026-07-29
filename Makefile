SHELL := /bin/bash
.DEFAULT_GOAL := help
UV := uv

.PHONY: help bootstrap test lint format run image contract

help:        ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

bootstrap:   ## Résout et installe l'environnement
	$(UV) sync

test:        ## pytest — dont la régression ophelie portée verbatim
	$(UV) run pytest tests/ -W ignore::DeprecationWarning

lint:        ## ruff + mypy (le profil ophelie gelé est exclu, cf. pyproject)
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy src/boondmanager_mock

format:      ## Formate
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

run:         ## Démarre le mock en local (profil insights360, admin ouvert)
	BOOND_MOCK_ADMIN_ENABLED=true $(UV) run python -m boondmanager_mock

image:       ## Construit l'image
	docker build -t boondmanager-mock:dev .

contract:    ## Régénère contracts/boondmanager.openapi.yaml depuis l'app
	@# `contrat_openapi()` et non `app.openapi()` : le contrat décrit le DIALECTE
	@# BoondManager. /__admin et /__fixtures sont des affordances du mock — les
	@# publier ferait passer pour du fournisseur ce qui n'en est pas, et /__admin
	@# n'est monté que sous condition, ce qui rendrait le contrat dépendant de
	@# l'environnement de génération.
	$(UV) run python -c "import yaml, boondmanager_mock as m; \
open('contracts/boondmanager.openapi.yaml','w').write(yaml.safe_dump(m.contrat_openapi(), sort_keys=False, allow_unicode=True))"
	@echo "✓ contrat régénéré — RELIRE le diff : une forme de réponse qui change est un changement de contrat"
