#!/usr/bin/env bash

# Install OS-specific binaries that we use in Ambuda.

# Redis
# =====
#
# We use Redis to send messages to Celery and receive updates from active
# Celery tasks. For context on why we use Redis instead of RabbitMQ, see the
# `Background tasks with Celery` page in our docs.
#
# For more installation details, see::
#
# https://redis.io/docs/getting-started/installation/install-redis-on-mac-os/

brew update
brew install redis

# Start the Redis service through Homebrew.
#
# If the `start` command fails, you might need to clean up your Homebrew setup.
# Try:
# 
#     brew doctor
#
# And perhaps also:
#
#     sudo chown -R $(whoami) /usr/local/*
brew services start redis
