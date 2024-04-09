#!/bin/bash
virtualenv venv

source venv/bin/activate

alias python=python3

python -m pip install -–upgrade pip

pip install -r requirements.txt

pip freeze > requirements.txt