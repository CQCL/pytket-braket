# Build the docs. Ensure we have the correct project title.
sphinx-build -b html -D html_title="$EXTENSION_NAME" . build 
# Remove copied files. This ensures reusability.
rm -r _static 
rm -r quantinuum-sphinx
rm conf.py