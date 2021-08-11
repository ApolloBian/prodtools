#!/usr/bin/env python
from tqdm import tqdm
import multiprocessing as mp


def chunk(iterable, chunk_size):
    ret = []
    for record in iterable:
        ret.append(record)
        if len(ret) == chunk_size:
            yield ret
            ret = []
    if ret:
        yield ret


def progress_pmap(fn, lst, num_threads=10):
    with mp.Pool(num_threads) as p:
        res = list(tqdm(p.imap(fn, lst), total=len(lst)))
    return res
