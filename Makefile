NAME := poucave
CONFIG_FILE := $(shell echo $${CONFIG_FILE-config.toml})
VERSION_FILE := $(shell echo $${VERSION_FILE-version.json})
SOURCE := $(shell git config remote.origin.url | sed -e 's|git@|https://|g' | sed -e 's|github.com:|github.com/|g')
VERSION := $(shell git describe --always --tag)
COMMIT := $(shell git log --pretty=format:'%H' -n 1)
COMMIT_HOOK := .git/hooks/pre-commit
VENV := $(shell echo $${VIRTUAL_ENV-.venv})
PYTHON := $(VENV)/bin/python3
VIRTUALENV := virtualenv --python=python3.8
PIP_INSTALL := $(VENV)/bin/pip install --progress-bar=off
INSTALL_STAMP := $(VENV)/.install.stamp

.PHONY: clean check lint format tests

install: $(INSTALL_STAMP) $(COMMIT_HOOK)
$(INSTALL_STAMP): $(PYTHON) requirements/dev.txt requirements/constraints.txt requirements/default.txt checks/remotesettings/requirements.txt
	${PIP_INSTALL} --force-reinstall pip==20.2.4 setuptools==50.3.2 wheel==0.35.1
	$(PIP_INSTALL) -Ur requirements/default.txt -c requirements/constraints.txt
	$(PIP_INSTALL) -Ur checks/remotesettings/requirements.txt
	$(PIP_INSTALL) -Ur requirements/dev.txt
	touch $(INSTALL_STAMP)

$(PYTHON):
	$(VIRTUALENV) $(VENV)

$(COMMIT_HOOK):
	echo "make format" > $(COMMIT_HOOK)
	chmod +x $(COMMIT_HOOK)

clean:
	find . -type d -name "__pycache__" | xargs rm -rf {};
	rm -rf $(VENV)

lint: $(INSTALL_STAMP)
	$(VENV)/bin/isort --profile=black --lines-after-imports=2 --check-only checks tests $(NAME) --virtual-env=$(VENV)
	$(VENV)/bin/black --check checks tests $(NAME) --diff
	$(VENV)/bin/flake8 --ignore=W503,E501 checks tests $(NAME)
	$(VENV)/bin/mypy checks tests $(NAME) --ignore-missing-imports
	$(VENV)/bin/bandit -r $(NAME) -s B608

format: $(INSTALL_STAMP)
	$(VENV)/bin/isort --profile=black --lines-after-imports=2 checks tests $(NAME) --virtual-env=$(VENV)
	$(VENV)/bin/black checks tests $(NAME)

$(CONFIG_FILE):
	cp config.toml.sample $(CONFIG_FILE)

$(VERSION_FILE):
	echo '{"name":"$(NAME)","version":"$(VERSION)","source":"$(SOURCE)","commit":"$(COMMIT)"}' > $(VERSION_FILE)

serve: $(INSTALL_STAMP) $(VERSION_FILE) $(CONFIG_FILE)
	$(PYTHON) -m $(NAME)

check: $(INSTALL_STAMP) $(CONFIG_FILE)
	LOG_LEVEL=DEBUG LOG_FORMAT=text $(PYTHON) -m $(NAME) check $(project) $(check)

test: tests
tests: $(INSTALL_STAMP) $(VERSION_FILE)
	$(PYTHON) -m pytest tests --cov-report term-missing --cov-fail-under 100 --cov poucave --cov checks
