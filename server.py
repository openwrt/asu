#!/usr/bin/env python3
import logging
logging.basicConfig(level=logging.DEBUG)

# so here it begins
import server
from server import app

if __name__ == '__main__':
    app.run(host="0.0.0.0")
