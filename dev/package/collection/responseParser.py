#!/Anaconda3/env/honours python

"""responseParser.py"""

#standard modules
from json import dumps, loads
import os
import logging

#third-party modules
import dpath.util as dp
import yaml

#local modules
from logManager import timed, traced
from configManager import configManager

#constants

#configManager
cm = configManager()

#logger

log = logging.getLogger(__name__)

#helper functions

def get_table(json):
    table = json["properties"]["api_path"].split("/")[0]
    table_lookup = {v: k for k, v in cm.api_table_lookup.items()}
    table = table_lookup[table]
    return table

def safe(glob):
    glob = [x for x in glob if not (type(x) is int)]
    return glob

def get_value(dictionary, glob):
    try: return dp.get(dictionary, glob)
    except KeyError: return None

def split_key(keychain, reference):
    key = ''.join(keychain[-1:])
    ref_value = get_value(reference, safe(keychain))
    dp.delete(reference, safe(keychain))
    keychain.pop()
    keychain.extend(key.split(".",maxsplit=1))
    dp.new(reference, safe(keychain), ref_value)

def unpack(keychain, reference, response):
    res_keys = get_value(response, keychain).keys()
    table = get_value(reference, safe(keychain)).split(".")[0]
    dp.delete(reference, safe(keychain))
    for res_key in res_keys:
        keychain.append(res_key)
        value = "{0}.{1}".format(table, res_key)
        dp.new(reference, safe(keychain), value)
        keychain.pop()

def log_records(records):
    output = ", ".join(["{0}:{1}".format(record_type, len(records[record_type])) for record_type in records])
    return output

#core functions

def parse_split(keychain, visited, reference, response, records):
    log.debug("Parse split attribute")
    split_key(keychain, reference)
    visited.append(list(keychain[:-1]))
    if keychain not in visited:
        _parse(keychain, visited, reference, response, records)
        visited.append(list(keychain))
    keychain.pop()

def parse_items(keychain, visited, reference, response, records):
    log.debug("Parse items")
    res_value = get_value(response, keychain)
    if res_value:
        for i, res_item in enumerate(res_value):
            keychain.append(i)
            _parse(keychain, visited, reference, response, records)
            keychain.pop()

def parse_dict(keychain, visited, reference, response, records):
    log.debug("Parse dictionary")
    ref_value = get_value(reference, safe(keychain))
    if type(ref_value) is dict:
        ref_keys = ref_value.keys()
    else: ref_keys = reference.keys()
    for ref_key in ref_keys:
        keychain.append(ref_key)
        if keychain not in visited:
            _parse(keychain, visited, reference, response, records)
            visited.append(list(keychain))
        keychain.pop()

def parse_properties(keychain, visited, reference, response, records):
    log.debug("Parse properties")
    if keychain not in visited:
        try: get_value(response, keychain).keys()
        except: pass
        else:
            unpack(keychain, reference, response)
            _parse(keychain, visited, reference, response, records)
        finally: visited.append(list(keychain))

@timed
def get_ref(keychain, reference, response, records):
    ref_inits = get_value(reference, safe(keychain))
    if type(ref_inits) is str: ref_inits = [ref_inits]
    ref_values = []
    for ref in ref_inits:
        ref = ref.split(".")
        table, attribute = tuple(ref)
        if get_value(records, table):
            length = len(get_value(records, table)) -1
        else: length = 0
        ref = [table, length, attribute]
        value = get_value(records, ref)
        if value and value != get_value(response, keychain):
            ref = [table, length+1, attribute]
        ref_values.append(ref)
    return ref_values

@timed
def add_primary(ref, reference, response, records):
    ref_value = get_value(reference, ["uuid"])
    res_value = get_value(response, ["uuid"])
    for key in ref_value:
        table, attribute = tuple(key.split("."))
        if get_value(records, ref[:-1]):
            if ref[0] in table:
                ref[2] = attribute
                dp.new(records, ref, res_value)

@timed
def get_value_store(dictionary, glob):
    return get_value(dictionary, glob)

@timed
def store(keychain, reference, response, records): #93.45
    log.debug("Store record") #0
    ref_values = get_ref(keychain, reference, response, records) #20.26
    for ref in ref_values: #105.57
        if type(keychain[-1]) is bool: res = keychain[-1] #0
        else: res = get_value_store(response, keychain)
        if type(res) is bool: res = str(res) #0
        dp.new(records, ref, res) #0
        add_primary(list(ref), reference, response, records) #39.84
    return records

def _parse(keychain, visited, reference, response, records):
    key = str(keychain[-1]) if len(keychain) > 0 else ""
    ref_value = get_value(reference, safe(keychain))
    if "." in key:
        parse_split(keychain, visited, reference, response, records)
    elif key == "items":
        parse_items(keychain, visited, reference, response, records)
    elif key == "properties" and type(ref_value) is not dict:
        parse_properties(keychain, visited, reference, response, records)
    elif type(ref_value) is dict or ref_value is None:
        parse_dict(keychain, visited, reference, response, records)
    else: records = store(keychain, reference, response, records)

def count_elements(d):
    cnt = 0
    for e in d:
        if type(d[e]) is dict: cnt += count_elements(d[e])
        else: cnt += 1
    return cnt

def clean(records):
    marked = []
    for record_type in records:
        for record_number in records[record_type]:
            record = records[record_type][record_number]
            num_elements = count_elements(record)
            if num_elements < 2:
                marked.append([record_type,record_number])
    for mark in marked: dp.delete(records, mark)
    marked = []
    for record_type in records:
        if not records[record_type]:
            marked.append(record_type)
    for mark in marked: del records[mark]
    return records

@timed
def parse(reference, response):
    try: response = response["data"]
    except: pass
    records, keychain, visited = {}, [], []
    _parse(keychain, visited, reference, response, records)
    records = clean(records)
    log.debug("Record: {0}".format(dumps(records, indent=1)))
    log.debug("Record: {0}".format(log_records(records)))
    log.debug("Count: {0}".format(count_elements(records)))
    return records

if __name__ == "__main__":
    cm = configManager()
    ref_path = cm.crawler_ref
    json_path = "{0}acquisitions.json".format(cm.api_examples_dir)
    json_content = loads(open(json_path, encoding="utf8").read())
    parse(ref_path, json_content)
