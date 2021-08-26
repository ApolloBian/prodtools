#!/usr/bin/env python

import json

def load_jsonl(filename):
    with open(filename) as f:
        return [json.loads(line) for line in f.readlines()]
