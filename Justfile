set windows-powershell := true

# Show this help
@help:
  just --list

# Set up dev env
install:
  poetry install
  pre-commit install

# Run the test suite
test *ARGS:
  poetry run pytest --log-level=DEBUG {{ARGS}}

# Run the command
run *ARGS:
  poetry run swiss-army-upload {{ARGS}}

# Run type checks
types:
  poetry run mypy

# Build packages
build: _changelog
  poetry build
  briefcase build

# Generate changelog from forge releases
_changelog:
  poetry run python changelog.py

# Run the command
sau *ARGS:
  poetry run swiss-army-upload {{ARGS}}
