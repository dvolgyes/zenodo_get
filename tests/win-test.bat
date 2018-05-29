REM #

cd tests
python ../src/zenodo_get.py 10.5281/zenodo.1215979
python ../src/zenodo_get.py -d 10.5281/zenodo.1215979
python ../src/zenodo_get.py -r 1215979
python ../src/zenodo_get.py 1215979

