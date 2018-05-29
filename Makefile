#!/usr/bin/make

test:
	make -C tests

ci-test:
	tests/test.sh
