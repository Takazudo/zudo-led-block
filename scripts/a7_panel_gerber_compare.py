#!/usr/bin/env python3
"""Gerber-to-Gerber comparison of two panel builds (usage: a7_panel_gerber_compare.py BUILD_A BUILD_B; needs the pinned
gerbonara from engineering/a7/verification/optical/tools/requirements.lock): each file is parsed with gerbonara and its
flattened graphic primitives (aperture-resolved, units mm, rounded to 1 nm) are compared as multisets,
so aperture numbering and object order do not matter. Drill files are compared the same way."""
import collections, io, json, sys, zipfile
from gerbonara import GerberFile, ExcellonFile
from gerbonara.utils import MM

def prims(name, data):
    path = io.StringIO(data.decode('latin1'))
    f = ExcellonFile.from_string(data.decode('latin1')) if name.endswith('.drl') else GerberFile.from_string(data.decode('latin1'))
    c = collections.Counter()
    for obj in f.objects:
        for p in obj.to_primitives(MM):
            d = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in vars(p).items()}
            c[(type(p).__name__, repr(sorted((k, repr(v)) for k, v in d.items())))] += 1
    return c

res = {}
for b in ('controller', 'led_leaf', 'power_adapter'):
    x, y = zipfile.ZipFile(f'{sys.argv[1]}/{b}-panel-gerbers-DRYRUN.zip'), zipfile.ZipFile(f'{sys.argv[2]}/{b}-panel-gerbers-DRYRUN.zip')
    r = {}
    for n in sorted(x.namelist()):
        if n.endswith('.gbrjob'):
            continue
        a, c = prims(n, x.read(n)), prims(n, y.read(n))
        r[n] = {'primitives': sum(a.values()), 'equal': a == c}
    res[b] = r
print(json.dumps(res, indent=1))
