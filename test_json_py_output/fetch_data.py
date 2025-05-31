# -*- coding: utf-8 -*-

# fetch all json files from GraphRyder

import urllib2
import json

baseURL = "http://164.132.58.138:5000/"
baseDIR = (
    "/Users/melancon/Documents/Recherche/Proposals/H2020 CAPSSI OPENCARE/DMP/Data_2018/"
)
filenames = ["users", "comments", "posts", "tags", "annotations"]
for f in filenames:
    req = urllib2.Request(baseURL + f)
    opener = urllib2.build_opener()
    fj = opener.open(req)
    json_obj = json.loads(fj.read())
    with open(baseDIR + "opencare-" + f + "-anonymized.json", "w") as fp:
        fp.write(str(json_obj))
