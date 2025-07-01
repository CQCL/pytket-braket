install:
    cp docs/pytket-docs-theming/extensions/pyproject.toml docs
    cp docs/pytket-docs-theming/extensions/poetry.lock docs
    cd docs && poetry install && pip install ../.


prepare: install
    cp -R docs/pytket-docs-theming/_static docs
    cp docs/pytket-docs-theming/conf.py docs

build *SPHINX_ARGS: prepare
    cd docs && poetry run sphinx-build {{SPHINX_ARGS}} -b html . build 

linkcheck: prepare
    cd docs && poetry run sphinx-build -b linkcheck . build 

coverage:
    cd docs && poetry run sphinx-build -v -b coverage . build/coverage 

build-strict: prepare
    just build -W # Fail on sphinx warnings

serve: build
    npm exec serve docs/build

cleanup:
    rm -rf docs/build
    rm -rf docs/.jupyter_cache
    rm -rf docs/jupyter_execute
    rm -rf docs/_static
    rm -f docs/conf.py
