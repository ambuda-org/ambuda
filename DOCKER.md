```bash
# Run all tests
make docker-dev-shell
uv run pytest

# Run with coverage
uv run pytest --cov=ambuda
```

4. Try running tests: `make docker-dev-shell` then `uv run pytest`
