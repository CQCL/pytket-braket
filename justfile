prepare:
    cp -R docs/pytket-docs-theming/_static docs
    cp docs/pytket-docs-theming/conf.py docs
    cp docs/pytket-docs-theming/extensions/pyproject.toml docs
    cp docs/pytket-docs-theming/extensions/poetry.lock docs

install: prepare
    cd docs && poetry install && poetry run pip install ../.

build *SPHINX_ARGS: install
    cd docs && poetry run sphinx-build {{SPHINX_ARGS}} -b html . build 

linkcheck: install
    cd docs && poetry run sphinx-build -b linkcheck . build 

coverage: install
    cd docs && poetry run sphinx-build -v -b coverage . build/coverage 

build-strict: install
    just build -W # Fail on sphinx warnings

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
    rm -f docs/poetry.lock
