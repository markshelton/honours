#!/Anaconda3/env/honours python

"""data_preparer"""

#standard modules
import datetime
import sqlite3
import logging
import matplotlib.pyplot as plt
from collections import Counter
import string
import re
import itertools


#third party modules
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from unidecode import unidecode
import sqlalchemy
from stop_words import get_stop_words
import requests

#local modules
from logManager import logged
import dbLoader as db
import sqlManager as sm

#constants
files = {}
files["thirteen"] = {}
files["thirteen"]["database_file"] = "collection/thirteen/output/2013-Dec.db"
files["thirteen"]["flat_raw_file"] = "analysis/output/flatten/raw/thirteen.csv"
files["thirteen"]["flat_clean_file"] = "analysis/output/flatten/clean/thirteen.csv"
files["thirteen"]["flatten_config"] = "analysis/config/flatten/thirteen.sql"
files["sixteen"] = {}
files["sixteen"]["database_file"] = "collection/sixteen/output/2016-Sep.db"
files["sixteen"]["flat_raw_file"] = "analysis/output/flatten/raw/sixteen.csv"
files["sixteen"]["flat_clean_file"] = "analysis/output/flatten/clean/sixteen.csv"
files["sixteen"]["flatten_config"] = "analysis/config/flatten/sixteen.sql"

output_table = "combo"
merge_config = "analysis/config/flatten/merge.sql"
database_file = "analysis/output/combo.db"
nrows = 500

#logger
log = logging.getLogger(__name__)

@logged
def read(file,nrows=None):
    if nrows is None: df = pd.read_csv(file,low_memory=False)
    else: df = pd.read_csv(file,low_memory=False,nrows=nrows)
    return df

@logged
def clean(df):

    def handle_column(df, column, date_data=None):

        def go_filter(series, patterns, mode="included"):
            series = series.dropna()
            total = pd.Series()
            for x in patterns:
                pattern = "^{0}$".format(x)
                if mode == "excluded":
                    pattern = r"^(" + re.escape(x) + r"$).*"
                temp = series[series.str.match(pattern, as_indexer=True)]
                total = pd.concat([total, temp])
            return total

        def get_excluded():
            stop_words = get_stop_words('english')
            punctuation = list(string.punctuation)
            excluded = stop_words + punctuation
            return excluded

        def prepare_text(series, topn, sep=None):
            for punc in list(string.punctuation):
                series = series.str.replace(punc, "")
            series = series.replace(r'\s+', np.nan,regex=True)
            series = series.dropna()
            series = series.apply(lambda x: unidecode(str(x)))
            excluded = go_filter(series, get_excluded(), mode="excluded")
            series = series[series.index.difference(excluded.index)]
            return series

        def make_dummies(series, topn, sep=None, text=False):
            series_name = series.name
            series = series.str.lower()
            if sep: series = series.str.split(sep,expand=True).stack()
            if text: series = prepare_text(series, topn, sep)
            counts = series.value_counts()
            included = counts.nlargest(topn).index
            series = go_filter(series, included)
            if sep:
                series.index = pd.MultiIndex.from_tuples(series.index)
                df = series.unstack()
                df = df.apply(lambda x: sep.join(x.dropna()),axis=1)
                series = df.squeeze()
                df = series.str.get_dummies(sep=sep)
            else: df = pd.get_dummies(series)
            df = df.add_prefix(series_name+"_")
            return df

        def dropna(x):
            return pd.Series([str(y) for y in x if type(y) is dict])

        def sum_dicts(x):
            c = Counter()
            for d in x:
                d = eval(d)
                d = {k: float(v) for k,v in d.items()}
                c.update(d)
            c = dict(c)
            return c

        #todo - [a 5; b 4; a 3] // index: dummy: value
        def combine_pairs(series, sep):
            series_name = series.name
            series = series.str.split(sep,expand=True).stack()
            series = series.apply(lambda x: dict([tuple(x.split(" "))]))
            df = series.unstack()
            series = df.apply(lambda x: ",".join(dropna(x)).split(","),axis=1)
            series = series.apply(lambda x: sum_dicts(x))
            df = pd.DataFrame.from_records(series.tolist(), index=series.index)
            df = df.add_prefix(series_name+"_")
            return df

        def go_dates(series, date_data):

            def match_date_data(date, date_data):
                try:
                    date = datetime.datetime.fromtimestamp(date).strftime("%Y-%m-%d")
                    result = date_data["Close"].ix[date]
                except: result = 0
                return result

            new = series.apply(lambda x: match_date_data(x, date_data)) # BROKEN
            new.name = series.name+"_"+"SP500"+"_"+"number"
            df = pd.concat([series, new],axis=1)
            return df


        column = column.split(":")[0]
        #print(column)
        if column.startswith("keys"): temp = df[column]
        elif column.endswith("date"): temp = go_dates(df[column], date_data=date_data)
        #elif column.endswith("duration"): temp = df[column]
        #elif column.endswith("bool"): temp = df[column]
        #elif column.endswith("dummy"): temp = make_dummies(df[column],topn=5)
        #elif column.endswith("list"): temp = make_dummies(df[column],topn=5,sep=";")
        #elif column.endswith("text"): temp = make_dummies(df[column],topn=5,sep=" ",text=True)
        #elif column.endswith("number"): temp = pd.to_numeric(df[column], errors="ignore").fillna(0)
        #elif column.endswith("pair"): temp = combine_pairs(df[column],sep=";")
        else: temp = pd.DataFrame()
        return temp

    def create_durations(df):
        df.replace(0, np.nan, inplace=True)
        zipped = list(zip(df.columns, df.values.tolist()))
        input(zipped)
        combos = list(itertools.combinations(zipped, 2))
        durations = []
        for x, y in combos:
            yo = (x,y)
            input(yo)
            if x[0] != y[0]:
                values = []
                for i in range(len(x[1])):
                    value = abs(x[1][i] - y[1][i])
                    if x[1][i] - y[1][i] < 0: label = "from_{}_to_{}_duration".format(x[0], y[0])
                    else: label = "from_{}_to_{}_duration".format(y[0], x[0])
                    values.append(value)
                duration = (label, values)
                durations.append(duration)
        input(durations)
        return temp

    def get_date_data(ticker, start="19700101", end="20170301"):
        path = "https://stooq.com/q/d/l/?s={}&i=d&d1={}&d2={}".format(ticker, start, end)
        df = pd.read_csv(requests.get(path).url, index_col="Date")
        return df

    df_new = pd.DataFrame()
    #date_data = get_date_data("^spx")
    for column in df:
        temp = handle_column(df, column)#, date_data=date_data)
        if temp is not None and not temp.empty:
            df_new = pd.concat([df_new, temp],axis=1)
    df_new.columns = [unidecode(x).strip().replace(" ","-") for x in list(df_new)]
    dates = [col for col in list(df) if col.endswith("date")]
    temp = create_durations(df_new[dates])
    df_new = pd.concat([df_new, temp], axis=1)
    df_new.replace(np.nan, 0, inplace=True)
    return df_new

@logged
def flatten(database_file, script_file):
    sm.execute_script(database_file, script_file)

@logged
def flatten_file(database_file, config_file, export_file, file_name):
    flatten(database_file, config_file)
    db.export_file(database_file, export_file, file_name)

@logged
def clean_file(raw_file, clean_file,nrows=None):
    df = read(raw_file, nrows=nrows)
    df = clean(df)
    df.to_csv(clean_file, mode="w+", index=False)

@logged
def load_file(database_file, clean_file, file_name):
    df = pd.read_csv(clean_file, encoding="latin1")
    with sqlite3.connect(database_file) as conn:
        df.to_sql(file_name, conn, if_exists='append', index=False)

@logged
def merge(database_file, script_file):
    sm.execute_script(database_file, script_file)

@logged
def export_dataframe(database_file, table):
    uri = db.build_uri(database_file, table=None, db_type="sqlite")
    engine = sqlalchemy.create_engine(uri)
    with engine.connect() as conn:
        df = pd.read_sql_table(table, conn)
    return df

def main():
    #db.clear_files(database_file)
    del files['sixteen']
    for file_name, file in files.items():
        #flatten_file(file["database_file"], file["flatten_config"], file["flat_raw_file"], file_name)
        clean_file(file["flat_raw_file"], file["flat_clean_file"],nrows=nrows)
        #load_file(database_file, file["flat_clean_file"], file_name)
    #merge(database_file, merge_config)
    #df = export_dataframe(database_file, output_table)
    #print(df)

if __name__ == "__main__":
    main()


"""
match = {}
match["thirteen"] = "keys_permalink_id"
match["sixteen"] = "keys_cb_url_id"


#merge(database_file, files.keys(), output_table)
def merge(database_file, merge_tables, output_table):
    #thirteen - keys_permalink_id e.g. /company/google
    #fourteen - 
    #fifteen - 
    #sixteen - keys_cb_url_id e.g. https://www.crunchbase.com/organization/google
    df_new = df_temp
    return df_new
"""