# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?= -j auto 
SPHINXBUILD   ?= sphinx-build
SPHINXAUTOBUILD   ?= sphinx-autobuild
SOURCEDIR     = .
BUILDDIR      = _build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile
# Generate API reference RST files
generate-api-rst:
	python ./create_api_rst.py

# Combined target to generate API RST and build HTML
api-docs: generate-api-rst build-html

.PHONY: generate-api-rst build-html api-docs

clobber: clean
	rm -rf langsmith

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@echo "SOURCEDIR: $(SOURCEDIR)"
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	
