###############
# VARIABLES
###############
GIT_ROOT ?= $(shell git rev-parse --show-toplevel)
PROJECT_NAME ?= $(shell basename $(GIT_ROOT))
.PHONY: bump docs docstrings find help integration

###############
##@Utils ⭐ 
###############
help: ## Show this helpful message
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[33m%-25s\033[0m %s\n", $$1, $$2} /^##@/ {printf "\n\033[0;32m%s\033[0m\n", substr($$0, 4)} ' $(MAKEFILE_LIST)

install: ## Install all project deps and create a venv (local)
	make clean-all
	@echo "Creating a venv from pyproject.toml and installing deps using poetry..."
	poetry install --with dev
	@echo "All deps installed and venv created."

find: ## Search for a pattern. Use `make find term="pattern"`
	@find . -type d \( -name '.venv' -o -name '__pycache__' \) -prune -o -type f -print | xargs grep -l "$(term)"

clean: ## Clean temp files
	@echo "Cleaning tempfiles..."
	[ ! -f .coverage ] || rm .coverage
	[ ! -d .edsl_cache ] || rm  -rf .edsl_cache
	[ ! -d .mypy_cache ] || rm -rf .mypy_cache
	[ ! -d .temp ] || rm -rf .temp
	[ ! -d dist ] || rm -rf dist
	[ ! -d htmlcov ] || rm -rf htmlcov
	[ ! -d prof ] || rm -rf prof
	find . -type d -name '.venv' -prune -o -type f -name '*.db' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type f -name '*.db.bak' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type f -name '*.log' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type d -name '.pytest_cache' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type d -name '__pycache__' -exec rm -rf {} +

clean-docs: ## Clean documentation files
	[ ! -d .temp/docs ] || rm -rf .temp/docs

clean-test: ## Clean test files
	[ ! -d dist ] || rm -rf dist
	[ ! -d htmlcov ] || rm -rf htmlcov
	[ ! -d prof ] || rm -rf prof
	[ ! -d tests/temp_outputs ] || rm -rf tests/temp_outputs
	[ ! -f tests/edsl_cache_test.db ] || rm tests/edsl_cache_test.db
	[ ! -f tests/interview.log ] || rm tests/interview.log
	[ ! -f tests/test_pytest_report.html ] || rm tests/test_pytest_report.html
	@for file in *.html; do \
		[ ! -f "$$file" ] || rm "$$file"; \
	done
	@for file in *.jsonl; do \
		[ ! -f "$$file" ] || rm "$$file"; \
	done

clean-all: ## Clean everything (including the venv)
	@if [ -n "$$VIRTUAL_ENV" ]; then \
		echo "Your virtual environment is active. Please deactivate it."; \
		exit 1; \
	fi
	@echo "Cleaning tempfiles..."
	@make clean
	@echo "Cleaning testfiles..."
	@make clean-test
	@echo "Cleaning the venv..."
	@[ ! -d .venv ] || rm -rf .venv
	@echo "Done!"

publish: ## Publish the package to PyPI (requires credentials)
	@version=$$(grep "^version =" pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/'); \
	echo "You are about to publish EDSL version '$$version' to PyPI."
	@read -p "Are you sure you want to continue? (y/n) " answer; \
	if [ "$$answer" != "y" ]; then \
		echo "Publish canceled."; \
		exit 1; \
	fi
	poetry build
	poetry publish


###############
##@Development 🛠️  
###############
backup: ## Backup the code to `edsl/.backups/`
	TIMESTAMP=$$(date +"%Y%m%d_%H%M%S"); \
	BACKUP_NAME=$(PROJECT_NAME)_$${TIMESTAMP}.tar.gz; \
	mkdir -p "./.backups"; \
	tar -czf $${BACKUP_NAME} --exclude="*pkl" --exclude="*tar.gz" --exclude="*db" --exclude="*csv" --exclude="./.*" --exclude="node_modules" --exclude="__pycache__" .;\
	mv $${BACKUP_NAME} "./.backups";\
	echo "Backup created: $${BACKUP_NAME}"

bump: ## Bump the version of the package
	@python scripts/bump_version.py $(filter-out $@,$(MAKECMDGOALS))
%:
	@:

docs: ## Generate documentation
	make clean-docs
	mkdir -p .temp/docs
	poetry export -f requirements.txt --with dev --output .temp/docs/requirements.txt
	poetry export -f requirements.txt --with dev --output docs/requirements.txt
	sphinx-build -b html docs .temp/docs

docs-view: ## View documentation
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open .temp/docs/index.html; \
	else \
		firefox .temp/docs/index.html; \
	fi

docstrings: ## Check docstrings
	pydocstyle edsl

format: ## Run code autoformatters (black).
	pre-commit install
	pre-commit run black-jupyter --all-files --all

lint: ## Run code linters (flake8, pylint, mypy).
	mypy edsl

visualize: ## Visualize the repo structure
	python scripts/visualize_structure.py
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open .temp/visualize_structure/index.html; \
	else \
		firefox .temp/visualize_structure/index.html; \
	fi

###############
##@Testing 🐛
###############
test: ## Run regular tests (no Coop tests) 
	make clean-test
	pytest -xv tests --nocoop

test-coop: ## Run Coop tests (no regular tests, requires Coop local server running)
	make clean-test
	pytest -xv tests --coop

test-coverage: ## Run regular tests and get a coverage report
	make clean-test
	poetry run coverage run -m pytest tests --ignore=tests/stress --ignore=tests/coop && poetry run coverage html
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open htmlcov/index.html; \
	else \
		firefox htmlcov/index.html; \
	fi

test-report: ## Run unit tests and view a test report
	make clean-test
	pytest -xv tests --nocoop --html=tests/test_pytest_report.html
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open tests/test_pytest_report.html; \
	else \
		firefox tests/test_pytest_report.html; \
	fi

test-data: ## Create serialization test data for the current EDSL version
	python scripts/create_serialization_test_data.py

test-doctests: ## Run doctests
	make clean-test
	pytest --doctest-modules edsl/inference_services
	pytest --doctest-modules edsl/results
	pytest --doctest-modules edsl/jobs
	pytest --doctest-modules edsl/surveys
	pytest --doctest-modules edsl/agents
	pytest --doctest-modules edsl/scenarios
	pytest --doctest-modules edsl/questions
	pytest --doctest-modules edsl/utilities
	pytest --doctest-modules edsl/language_models
	pytest --doctest-modules edsl/data

test-integration: ## Run integration tests via pytest **consumes API credits**
	cd integration/printing && python check_printing.py
	pytest -v integration/test_example_notebooks.py
	pytest -v integration/test_integration_jobs.py
	pytest -v integration/test_memory.py
	pytest -v integration/test_models.py
	pytest -v integration/test_questions.py
	pytest -v integration/test_runners.py

integration-job-running: # DOES NOT WORK!
	pytest -v --log-cli-level=INFO integration/test_job_running.py

integration-tricky-questions: # DOES NOT WORK!
	pytest -v --log-cli-level=INFO integration/test_tricky_questions.py

# ###############
# ##@COOP 🪺
# ###############
# env-chick:
# 	@echo "Setting up the environment"
# 	cp .env_chick .env

# env-local-coop: 
# 	@echo "Setting up the environment"
# 	cp .env_local_coop .env
