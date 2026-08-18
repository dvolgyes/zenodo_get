.PHONY: all clean test ci-test test-deploy deploy

all: test

clean:
	rm -fR build dist

test:
	uv run pytest -n 4 --cov

ci-test:
	uv run pytest -n 4 --cov

test-deploy:
	rm -fR build dist
	uv build && twine upload -r pypitest dist/* --verbose

deploy: test
	rm -fR build dist
	uv build && twine upload -r pypi dist/*  --verbose
