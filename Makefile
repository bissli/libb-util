.PHONY: list dev build test test-rust test-kernel test-all test-matrix lint lint-rust format-rust clean clean-matrix help

# Default target - show help
help:
	@echo "Available targets:"
	@echo "  make dev          - Install dependencies and build native extension"
	@echo "  make build        - Build native extension only"
	@echo "  make test         - Run all tests (current Python)"
	@echo "  make test-rust    - Run Rust tests (both feature configurations)"
	@echo "  make test-kernel  - Verify the kernel cdylib links without libpython"
	@echo "  make test-matrix  - Run tests on Python 3.10-3.14 + 3.14t via uv"
	@echo "  make test-all     - Alias for test-matrix"
	@echo "  make lint         - Run all linters (Python + Rust)"
	@echo "  make lint-rust    - Check Rust formatting and clippy"
	@echo "  make format-rust  - Auto-format Rust code"
	@echo "  make clean        - Remove build artifacts"
	@echo "  make clean-matrix - Remove the per-interpreter venvs (.venvs/)"

# Install dependencies and build extension
dev:
	poetry install --extras test --extras web --extras ldapauth --extras tokenauth
	maturin develop --release

# Build native extension only
build:
	maturin develop --release

# Run tests (current Python)
test:
	pytest tests/ -v

# Run Rust tests in both feature configurations
test-rust:
	cargo test --manifest-path rust/Cargo.toml
	cargo test --manifest-path rust/Cargo.toml --no-default-features

# Verify the kernel cdylib needs no Python symbols (ELF hosts only).
# Notes:
# - extension-module leaves libpython out of NEEDED and resolves Py* at
#   load time, so ldd is clean in both feature configurations and cannot
#   be used as the gate. The symbol table is what discriminates.
test-kernel:
	cargo build --manifest-path rust/Cargo.toml --no-default-features --release
	@SO=rust/target/release/lib_libb.so; \
	if [ ! -f "$$SO" ]; then \
		echo "ERROR: $$SO was not built (this target needs an ELF host)"; \
		exit 1; \
	fi; \
	if nm -D --undefined-only "$$SO" | grep ' U Py'; then \
		echo "ERROR: kernel build still needs Python symbols"; \
		exit 1; \
	fi; \
	if nm -D --defined-only "$$SO" | grep PyInit; then \
		echo "ERROR: kernel build still exports a Python module init"; \
		exit 1; \
	fi; \
	echo "OK: kernel needs no Python symbols"

# Run tests on every supported interpreter.
# Notes:
# - uv provisions the interpreters, so this reaches a free-threaded build
#   that tox could never install on its own.
test-matrix:
	./scripts/test-matrix.sh

# Alias for test-matrix
test-all: test-matrix

# Run all linters
lint: lint-rust
	@echo "Linting complete"

# Check Rust formatting and run clippy in both feature configurations
lint-rust:
	cd rust && cargo fmt --all -- --check
	cd rust && cargo clippy --all-targets -- -D warnings
	cd rust && cargo clippy --all-targets --no-default-features -- -D warnings

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

# Remove the per-interpreter venvs built by the matrix runner
clean-matrix:
	rm -rf .venvs
