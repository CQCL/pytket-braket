install:
    cd docs && bash ./install.sh && pip install ../.

build: install
    cp -R docs/pytket-docs-theming/_static docs
    cp docs/pytket-docs-theming/conf.py docs
    cd docs && poetry run sphinx-build -b html . build 

serve: build
    npm exec serve docs/build

cleanup:
    rm -rf docs/build
    rm -rf docs/.jupyter_cache
    rm -rf docs/jupyter_execute
    rm -rf docs/_static
    rm docs/conf.py
