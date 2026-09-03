#!/usr/bin/python
# coding: utf-8
# Date: 2024-08-26

import re
import time
import requests
import pandas as pd
from os.path import join


def process_string(string) :
    if string[0] == "<":
        string = string[string.find(">")+1:]
    span_end = string.find("</span>")
    if span_end != -1:
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

def brenda_ec_lit(datasets_dir, brenda_dir) :
    categories = ["KCAT", "KM", "KCATKM"]
    deduplicated_dfs = list()
    for typeFile in categories :
        print("This is for", typeFile)
        brenda_df = pd.read_csv(join(datasets_dir, brenda_dir, "brenda_df_%s_download.csv" % typeFile))
        new_df = brenda_df[["EC", "LITERATURE"]].drop_duplicates(keep="first").reset_index(drop=True)
        print(len(new_df))
        # print(new_df.head())
        deduplicated_dfs.append(new_df)
    combined_df = pd.concat(deduplicated_dfs, ignore_index=True)
    combined_df = combined_df.drop_duplicates(keep="first").reset_index(drop=True)
    combined_df["LITERATURE"] = combined_df.apply(process_literature, axis=1)
    combined_df.reset_index(drop=True, inplace=True)
    print("Combined data:", len(combined_df))  # 41054
    # for literature in combined_df["LITERATURE"].tolist() :
    #     print(literature)

    combined_df.to_csv(join(datasets_dir, brenda_dir, "EC_Literature.csv"), index=False)

def get_brenda_pmid(datasets_dir, brenda_dir) :
    brenda_df = pd.read_csv(join(datasets_dir, brenda_dir, "EC_Literature.csv"))
    liturl = "https://brenda-enzymes.org/literature.php?e="
    brenda_df['PubMedID'] = ""

    for i in range(len(brenda_df)) :
        print(i)
        pmid_list = list()
        current_row = brenda_df.iloc[i]
        EC = current_row["EC"]
        Lit_IDs = current_row["LITERATURE"].split(",")
        print(EC)
        print(Lit_IDs)

        # if there are multiple literature values, the PMID for each one should be recorded 
        for Lit in Lit_IDs :
            response = requests.get(f'{liturl}{EC}&r={Lit}')
            if response.status_code == 200 :
                html = response.text
                # print(html)

                # Extract PubMed ID(s) from the HTML
                pmid_matches = re.findall(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', html)
                if pmid_matches :
                    # print(pmid_matches)
                    pmid_list.extend(pmid_matches)

        print(pmid_list)
        if pmid_list :
            brenda_df.at[i, 'PubMedID'] = ",".join(pmid_list)
        else :
            brenda_df.at[i, 'PubMedID'] = "N/A"

        if i % 1000 == 0 :
            time.sleep(10)

    return brenda_df

def remove_duplicates(infile, outfile) :
    brenda_df = pd.read_csv(join(datasets_dir, brenda_dir, infile))
    n_old = len(brenda_df)
    print("Total entries in the origninal file", n_old)
    brenda_df = brenda_df.drop_duplicates(keep="first").reset_index(drop=True)
    print("We remove %s out of %s data entries, because they are duplicates."
          % (n_old - len(brenda_df), n_old))
    brenda_df.to_csv(join(datasets_dir, brenda_dir, outfile), index=False)


if __name__ == '__main__' :
    datasets_dir = "../complementaryData"
    brenda_dir = "data_brenda"
    brenda_ec_lit(datasets_dir, brenda_dir)
    brenda_updated_df = get_brenda_pmid(datasets_dir, brenda_dir)
    brenda_updated_df.to_csv(join(datasets_dir, brenda_dir, "EC_Literature_PMID_v1.csv"), index=False)
    remove_duplicates("EC_Literature_PMID_v1.csv", "EC_Literature_PMID.csv")  # 1443 duplicates


