.PHONY: build test package clean
build: ; python3 build.py
test: ; python3 -m unittest discover -s tests
package: ; ./package.sh
clean: ; rm -rf dist release
