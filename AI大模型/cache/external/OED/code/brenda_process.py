#!/usr/bin/python
# coding: utf-8
# Date: 2024-09-05

import pandas as pd
from os.path import join


def process_string(string) :
    if string[0] == "<" :
        string = string[string.find(">")+1:]
    span_end = string.find("</span>")
    if span_end != -1 :
        string = string[:span_end]
    string = string.replace("\\", "")
    return string

def process_literature(row) :
    literature = row["LITERATURE"]
    if "<a href" in literature :
        new_literature = list()
        Literature_list = literature.split(", ")
        for Literature in Literature_list :
            if "<a href" in Literature :
                # print(Literature)
                # print(process_string(Literature))
                new_literature.append(process_string(Literature))
            else :
                new_literature.append(Literature)
        literature = ",".join(new_literature)
    return literature

# This is a try to print the PubMed ID
def get_pubmed(datasets_dir, brenda_dir) :
    EC_PMID = pd.read_csv(join(datasets_dir, brenda_dir, "EC_Literature_PMID.csv"))
    for pmid in EC_PMID["PubMedID"].tolist()[:100] :
        # print(pmid)
        if isinstance(pmid, str) and pmid != "N/A" :
            print(pmid)

def annotate_pubmed(datasets_dir, brenda_dir) :
    EC_PMID = pd.read_csv(join(datasets_dir, brenda_dir, "EC_Literature_PMID.csv"))
    categories = ["KCAT", "KM", "KCATKM"]
    for typeFile in categories :
        print("This is for", typeFile)
        brenda_df = pd.read_csv(join(datasets_dir, brenda_dir, "brenda_df_%s_download.csv" % typeFile))
        brenda_df["LITERATURE"] = brenda_df.apply(process_literature, axis=1)
        brenda_df = pd.merge(brenda_df, EC_PMID[['EC', 'LITERATURE', 'PubMedID']], on=['EC', 'LITERATURE'], how='left')
        brenda_df.reset_index(drop=True, inplace=True)

        brenda_df.to_csv(join(datasets_dir, brenda_dir, f"brenda_df_{typeFile}_process.csv"), index=False)


if __name__ == '__main__' :
    datasets_dir = "../complementaryData"
    brenda_dir = "data_brenda"
    # get_pubmed(datasets_dir, brenda_dir)
    annotate_pubmed(datasets_dir, brenda_dir)


