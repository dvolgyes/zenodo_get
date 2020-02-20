REM #
cd tests
python -m zenodo_get 10.5281/zenodo.1215979 -m -e -k
python -m zenodo_get -d 10.5281/zenodo.1215979 -w urls.txt -n
python -m zenodo_get  -r 1215979 -w -
python -m zenodo_get  1215979 -R 3 -p 2 -n
python -m zenodo_get 1215979

