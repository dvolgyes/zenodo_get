#!/usr/bin/make

test:
	uv run pytest -n 4 --cov

ci-test:
	uv run pytest -n 4 --cov

test-deploy:
	rm -fR build dist
	uv build && twine upload -r pypitest dist/*

deploy:
	rm -fR build dist
	uv build && twine upload -r pypi dist/*
