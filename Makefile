.PHONY: list dev build test test-all tox lint lint-rust format-rust clean clean-tox help

# Default target - show help
help:
	@echo "Available targets:"
	@echo "  make dev          - Install dependencies and build native extension"
	@echo "  make build        - Build native extension only"
	@echo "  make test         - Run all tests (current Python)"
	@echo "  make test-all     - Run tests on Python 3.9-3.13 via tox"
	@echo "  make tox          - Alias for test-all"
	@echo "  make lint         - Run all linters (Python + Rust)"
	@echo "  make lint-rust    - Check Rust formatting and clippy"
	@echo "  make format-rust  - Auto-format Rust code"
	@echo "  make clean        - Remove build artifacts"
	@echo "  make clean-tox    - Remove tox cache (~/.cache/tox/)"

# Install dependencies and build extension
dev:
	poetry install --extras test
	maturin develop --release

# Build native extension only
build:
	maturin develop --release

# Run tests (current Python)
test:
	pytest tests/ -v

# Run tests on all Python versions via tox
test-all:
	tox

# Alias for test-all
tox:
	tox

# Run all linters
lint: lint-rust
	@echo "Linting complete"

# Check Rust formatting and run clippy
lint-rust:
	cd rust && cargo fmt --all -- --check
	cd rust && cargo clippy -- -D warnings

# Auto-format Rust code
format-rust:
	cd rust && cargo fmt --all

# Remove build artifacts
clean:
	rm -rf rust/target
	rm -rf dist
	rm -f src/libb/*.so
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# Remove tox cache (stored in ~/.cache/tox/)
clean-tox:
	rm -rf $(HOME)/.cache/tox/libb-util
