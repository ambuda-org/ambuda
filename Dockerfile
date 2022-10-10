FROM python:3.9.13-slim-buster as base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y curl && curl -sL https://deb.nodesource.com/setup_16.x | bash -
RUN apt-get install -y nodejs && apt-get remove -y curl && rm -rf /var/lib/apt/lists/*

FROM base as build

ARG WHICH_ENV

ENV WHICH_ENV=${WHICH_ENV} \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_DEFAULT_TIMEOUT=100 \
  POETRY_VERSION=1.2.1

RUN pip install "poetry==$POETRY_VERSION"
RUN python -m venv /venv

COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt | /venv/bin/pip install -r /dev/stdin

COPY . .
RUN poetry build && /venv/bin/pip install dist/*.whl

FROM base as final
COPY --from=build /venv /venv

# Install Node dependencies.
COPY ./package* ./
RUN npm ci

# Install code
CMD ["./scripts/run_devserver_docker.sh"]
