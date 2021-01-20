#!/bin/bash
if [ $1 == "server" ]; then
    exec poetry run python -m poucave

elif [ $1 == "check" ]; then
    shift
    exec poetry run python -m poucave $@

elif [ $1 == "test" ]; then
    # Note: poetry has no option to only install dev dependencies.
    # https://github.com/python-poetry/poetry/issues/2572
    poetry install --extras=remotesettings
    poetry run pytest tests

else
    exec poetry run "$@"
fi