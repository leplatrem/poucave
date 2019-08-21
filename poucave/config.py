import os
import re
import sys

import toml


HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", 8000))
CONFIG_FILE = os.getenv("CONFIG_FILE", "config.toml")
DEFAULT_TTL = int(os.getenv("DEFAULT_TTL", 60))
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
VERSION_FILE = os.getenv("VERSION_FILE", "version.json")
LOGGING = {
    "version": 1,
    "formatters": {
        "json": {"()": "dockerflow.logging.JsonLogFormatter", "logger_name": "poucave"}
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": sys.stdout,
        }
    },
    "loggers": {
        "poucave": {"handlers": ["console"], "level": "DEBUG"},
        "request.summary": {"handlers": ["console"], "level": "INFO"},
    },
}


def interpolate_env(d):
    new = {}
    for k, v in d.items():
        if isinstance(v, str):
            search = re.search("\\$\\{(.+)\\}", v)
            if search:
                for g in search.groups():
                    v = v.replace(f"${{{g}}}", os.getenv("ENV_NAME", ""))
            new[k] = v
        elif isinstance(v, dict):
            new[k] = interpolate_env(v)
        else:
            new[k] = v
    return new


def load(configfile):
    conf = toml.load(open(configfile, "r"))
    conf = interpolate_env(conf)
    return conf
