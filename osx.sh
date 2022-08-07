# https://redis.io/docs/getting-started/installation/install-redis-on-mac-os/
# redis-cli
brew update
brew install redis

# If the `start` command fails, you might need to clean up your Homebrow setup.
# Try:
# 
#     brew doctor
#
# And perhaps also:
#
#     sudo chown -R $(whoami) /usr/local/*
brew services start redis
