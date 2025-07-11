prepare:
    cp -R docs/pytket-docs-theming/_static docs
    cp docs/pytket-docs-theming/conf.py docs
    cp docs/pytket-docs-theming/pyproject.toml docs
    cp docs/pytket-docs-theming/uv.lock docs

PROJECT_NAME := `(basename $(pwd))`

install: prepare
    cd docs && uv pip install .

build *SPHINX_ARGS: install
    cd docs && sphinx-build {{SPHINX_ARGS}} -b html . build -D html_title={{PROJECT_NAME}}

linkcheck: install
    cd docs && sphinx-build -b linkcheck . build

coverage: install
    cd docs && sphinx-build -v -b coverage . build/coverage

build-strict: install
    just build -W # Fail on sphinx warnings
    just linkcheck
    just coverage

serve: build
    npm exec serve docs/build

cleanup:
    rm -rf docs/build
    rm -rf docs/.jupyter_cache
    rm -rf docs/jupyter_execute
    rm -rf docs/_static
    rm -f docs/conf.py

cleanup-all:
    just cleanup
    rm -rf docs/.venv
    rm -f docs/pyproject.toml
    rm -f docs/uv.lock
