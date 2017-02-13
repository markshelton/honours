#!/Anaconda3/env/honours python

"""__main__.py"""

#standard modules
import logging
import os

#third-party modules

#local modules
import dbLoader as db

#constants
input_file = "collection/fifteen/input/2015-Dec-04_csv.zip"
extract_dir = "collection/fifteen/output/extract/"
export_dir = "collection/fifteen/output/export/"
database_file = "collection/fifteen/output/2015-Dec.db"
config_dir = "collection/fifteen/config/"

#logger
log = logging.getLogger(__name__)

def extract_filter(src, dst):
    base = os.path.basename(src)
    if base.endswith(".csv"):
        log.info("%s | Extraction", base)
        return (extract_dir+base)
    return None

def extract():
    db.clear_files(extract_dir)
    db.extract_archive(input_file, extract_dir, extract_filter)

def load():
    db.clear_files(database_file)
    db.load_files(extract_dir, database_file)

def export():
    db.clear_files(export_dir)
    db.export_files(database_file, export_dir)

def flatten():
    

def main():
    #cm = db.load_config(config_dir)
    #extract()       #Done
    #load()          #Done
    #export()         #Done
    flatten()         #Done

if __name__ == "__main__":
    main()
