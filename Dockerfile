FROM python:3.9.13-buster as build

WORKDIR /app

# Install Node.
RUN curl -sL https://deb.nodesource.com/setup_16.x | bash -
RUN apt-get update && apt-get install -y nodejs

# Install Python dependencies.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Install Node dependencies.
COPY ./package* ./
RUN npm ci

FROM python:3.9.13-buster as deploy
WORKDIR /app
COPY --from=build /app /app
CMD ["./scripts/run_devserver_docker.sh"]
