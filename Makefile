#!/usr/bin/make

test:
	make -C tests

ci-test:
	tests/test.sh

test-deploy:
	rm -fR build dist
	python3 setup.py sdist bdist_wheel --universal && twine upload -r pypitest dist/*
	pip3  install --user zenodo_get --index-url https://test.pypi.org/simple/
	pip3 uninstall zenodo_get

deploy:
	rm -fR build dist
	python3 setup.py sdist bdist_wheel --universal && twine upload -r pypi dist/*