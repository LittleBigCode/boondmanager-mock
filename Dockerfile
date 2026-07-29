# Image dédiée, non-root, minimale.
#
# Le mock d'origine n'avait PAS d'image à lui : le compose d'ophelie réutilisait
# l'image du backend avec une autre commande. Il embarquait donc SQLAlchemy,
# psycopg2, authzed, elasticsearch, boto3, mcp… pour un service qui n'a jamais
# eu besoin que de FastAPI et d'uvicorn. Une image dédiée est un gain immédiat
# de taille et de surface d'attaque.
#
# `python:3.12-slim` en direct plutôt que via le proxy Harbor : cette image doit
# se construire AUSSI hors VPN (poste de dev, GitHub Actions), où
# harbor.build.graal.systems est injoignable. C'est la convention déjà retenue
# par ophelie pour son Dockerfile backend, pour la même raison. En CI Tekton,
# kaniko pousse ensuite vers Harbor, d'où les pods la tirent — la policy Kyverno
# `only-harbor-images` est donc satisfaite côté cluster.
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

RUN pip install --no-cache-dir uv

WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# `--frozen`      : la construction ne résout jamais, elle installe le lockfile.
# `--no-dev`      : pytest et ruff n'ont rien à faire dans l'image livrée.
# `--no-editable` : SANS CETTE OPTION, uv installe le projet en mode éditable,
#                   c'est-à-dire un lien vers /build/src — qui n'existe pas dans
#                   l'étage final. L'image se construit alors sans erreur et
#                   échoue au démarrage sur « No module named boondmanager_mock ».
RUN uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# uid/gid fixes et non-root : le namespace insights360 tourne en PSA `baseline`
# (à cause de Spilo, cf. infra), mais tout ce que NOUS écrivons reste
# restricted-clean. Le chart pose runAsNonRoot + seccomp + drop ALL ; l'image
# doit suivre, sinon la déclaration est un mensonge.
RUN groupadd --gid 65532 mock && \
    useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin mock

COPY --from=builder /opt/venv /opt/venv

USER 65532:65532
EXPOSE 8000

# Le healthcheck manquait au service compose d'ophelie alors que /health
# existait : le backend attendait `service_started`, donc pouvait interroger un
# mock pas encore prêt.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["python", "-m", "boondmanager_mock"]
