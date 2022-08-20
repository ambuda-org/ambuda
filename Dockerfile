FROM python:3.9.13-buster

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

COPY . .

# Database setup
# ==============

# Create tables
RUN python -m scripts.initialize_db

# Create Alembic's migrations table.
RUN alembic ensure_version

# Set the most recent revision as the current one.
RUN alembic stamp head

CMD ["make", "devserver"]
