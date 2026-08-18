.PHONY: all clean test

all: test

clean:
	rm -f .coverage

test:
	uv run pytest -n 4 --cov
