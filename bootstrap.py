import os
import sys
import subprocess
import functools

run = functools.partial(subprocess.call, shell=True)

run('python3 -mvenv .env')

run('.env/bin/pip install --upgrade setuptools')

run('.env/bin/pip install --upgrade pip')
run('.env/bin/pip install wheel')

run('cd vendor2/buildout; ../../.env/bin/python setup.py develop')

run('.env/bin/buildout bootstrap')

if not os.path.exists('buildout.cfg'):
    TPL = """
[buildout]
extends = buildout/development.cfg
"""

    f = open('buildout.cfg', 'w')
    f.write(TPL)

run('.env/bin/buildout bootstrap')
