REM #
cd tests
python ../src/zenodo_get.py 10.5281/zenodo.1215979 -m -e -k
python ../src/zenodo_get.py -d 10.5281/zenodo.1215979 -w urls.txt -n
python ../src/zenodo_get.py -r 1215979 -w -
python ../src/zenodo_get.py 1215979 -R 3 -p 2 -n
python ../src/zenodo_get.py 1215979

