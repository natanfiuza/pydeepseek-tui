.PHONY: dev run test lint format build publish

dev:
	pipenv install --dev

run:
	pipenv run pydeepseek

test:
	pipenv run pytest

lint:
	pipenv run ruff check .
	pipenv run black --check .
	pipenv run mypy src

format:
	pipenv run ruff check --fix .
	pipenv run black .

build:
	pipenv run py -m build

publish:
	pipenv run twine upload dist/*