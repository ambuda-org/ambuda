FROM python:3.9.13-buster as build

ENV POETRY_VERSION=1.1.4
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python
ENV PATH /root/.poetry/bin:$PATH


WORKDIR /app
COPY pyproject.toml poetry.lock ./

# Install Node.
RUN curl -sL https://deb.nodesource.com/setup_16.x | bash -
RUN apt-get update && apt-get install -y nodejs swig freetype

# Install Node dependencies.
COPY ./package* ./
RUN npm ci

# Install Python dependencies.
RUN python -m venv --copies /app/env
RUN . /app/env/bin/activate && poetry install 

# Old style with requirements
# COPY requirements.txt ./
# RUN pip install -r requirements.txt


# Install code
CMD ["./scripts/install_devserver_docker.sh"]


# Second stage start
FROM python:3.9.13-slim-buster as deploy
COPY --from=build /app/ /app/
ENV PATH /app/env/bin/:$PATH
WORKDIR /app/

CMD ["./scripts/run_devserver_docker.sh"]
