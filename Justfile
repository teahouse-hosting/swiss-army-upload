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
  poetry run mypy src tests

# Build packages
build: _changelog
  poetry build
  briefcase package

# Generate changelog from forge releases
_changelog:
  poetry run python changelog.py

# Run the command
sau *ARGS:
  poetry run swiss-army-upload {{ARGS}}


# Do the multi-platform build locally
qemu-build:
  docker buildx build --platform linux/amd64,linux/riscv64,linux/ppc64le,linux/s390x,linux/386,linux/arm/v7,linux/arm/v6,linux/arm64/v8 .
