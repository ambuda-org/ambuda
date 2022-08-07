brew update
brew install rabbitmq

# If the `start` command fails, you might need to clean up your Homebrow setup.
# Try:
# 
#     brew doctor
#
# And perhaps also:
#
#     sudo chown -R $(whoami) /usr/local/*
brew services start rabbitmq
