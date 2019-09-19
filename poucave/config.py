import os
import re
import sys

import toml


HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", 8000))
CONFIG_FILE = os.getenv("CONFIG_FILE", "config.toml")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
DEFAULT_TTL = int(os.getenv("DEFAULT_TTL", 60))
REQUESTS_TIMEOUT_SECONDS = int(os.getenv("REQUESTS_TIMEOUT_SECONDS", 5))
REQUESTS_MAX_RETRIES = int(os.getenv("REQUESTS_MAX_RETRIES", 2))
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
VERSION_FILE = os.getenv("VERSION_FILE", "version.json")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
REQUESTS_MAX_PARALLEL = int(os.getenv("REQUESTS_MAX_PARALLEL", 16))
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")
LOGGING = {
    "version": 1,
    "formatters": {
        "text": {
            "format": "%(name)s [%(levelname)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {"()": "dockerflow.logging.JsonLogFormatter", "logger_name": "poucave"},
    },
    "handlers": {
        "console": {
            "level": LOG_LEVEL.upper(),
            "class": "logging.StreamHandler",
            "formatter": LOG_FORMAT,
            "stream": sys.stdout,
        }
    },
    "loggers": {
        "poucave": {"handlers": ["console"], "level": "DEBUG"},
        "checks": {"handlers": ["console"], "level": "DEBUG"},
        "backoff": {"handlers": ["console"], "level": "DEBUG"},
        "kinto_http": {"handlers": ["console"], "level": "DEBUG"},
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
