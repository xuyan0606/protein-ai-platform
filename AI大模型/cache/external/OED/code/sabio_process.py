#!/usr/bin/python
# coding: utf-8
# Date: 2024-04-19

import os
import pandas as pd
from os.path import join


def process_km(datasets_dir, sub_dir, typeFile) :
    filenames = os.listdir('../complementaryData/data_sabio_EC')
    # print(len(filenames)) # 8236 EC files

    # create empty pandas DataFrame
    columns = ["SUBSTRATES", "PRODUCTS", "EnzymeType", "PubMedID", "ORGANISM", "UNIPROT", "EC", "PH", "Temperature",
                                       "SUBSTRATE", "KM VALUE", "UNIT"]
    sabio_df = pd.DataFrame(columns = columns)
    i = 0
    data_list = list()
    for filename in filenames :
        # print(filename[:-4])  # This is EC Number

        # filename = "1.1.1.6.txt"  # One example
        with open("../complementaryData/data_sabio_EC/%s" % filename, 'r', encoding="utf-8") as infile :
            lines = infile.readlines()

        for line in lines[1:] :
            data = line.strip().split('\t')
            try :
                if data[10].lower() == 'km' and data[12] :
                    # print(data)
                    i += 1
                    # print(i)
                    new_row = data[1:10] + data[11:13] + [data[-1]]
                    # print(new_row)
                    data_list.append(new_row)
            except :
                continue

    sabio_df = pd.DataFrame(data_list, columns = columns)
    sabio_df.to_csv(join(datasets_dir, sub_dir, "sabio_df_%s_download.csv" % typeFile), index=False)

def process_kcat(datasets_dir, sub_dir, typeFile) :
    filenames = os.listdir('../complementaryData/data_sabio_EC')
    # print(len(filenames)) # 8236 EC files

    # create empty pandas DataFrame
    columns = ["SUBSTRATES", "PRODUCTS", "EnzymeType", "PubMedID", "ORGANISM", "UNIPROT", "EC", "PH", "Temperature",
                                       "SUBSTRATE", "KCAT VALUE", "UNIT"]
    sabio_df = pd.DataFrame(columns = columns)
    i = 0
    data_list = list()
    for filename in filenames :
        # print(filename[:-4])  # This is EC Number

        # filename = "1.1.1.6.txt"  # One example
        with open("../complementaryData/data_sabio_EC/%s" % filename, 'r', encoding="utf-8") as infile :
            lines = infile.readlines()

        for line in lines[1:] :
            data = line.strip().split('\t')
            try :
                if data[10].lower() == 'kcat' and data[12] :
                    # print(data)
                    i += 1
                    # print(i)
                    entryID = data[0]
                    for line in lines[1:] :
                        data2 = line.strip().split('\t')
                        if data2[0] == entryID and data2[10].lower() == "km" :
                            substrate = data2[11]
                            new_row = data[1:10] + [substrate, data[12], data[-1]]
                            # print(new_row)
                            data_list.append(new_row)
            except :
                continue

    sabio_df = pd.DataFrame(data_list, columns = columns)
    sabio_df.to_csv(join(datasets_dir, sub_dir, "sabio_df_%s_download.csv" % typeFile), index=False)

# This script is to calculate kcat/km if one entry has specific kcat and km
def calculate_kcatkm() :
    filenames = os.listdir('../complementaryData/data_sabio_EC')
    # print(len(filenames)) # 8236 EC files

    additional_kcatkm = list()
    for filename in filenames :
        data_df = pd.read_csv("../complementaryData/data_sabio_EC/%s" % filename, delimiter="\t")
        grouped = data_df.groupby("EntryID")

        for name, group in grouped :
            # print(f"Group: {name}")
            if "kcat/km" not in group['parameter.type'].str.lower().values :
                if "kcat" in group['parameter.type'].str.lower().values and "km" in group['parameter.type'].str.lower().values :
                    kcat_index = group.index[group['parameter.type'].str.lower() == 'kcat'].tolist()
                    km_index = group.index[group['parameter.type'].str.lower() == 'km'].tolist()
                    # print(data_df.iloc[kcat_index[0], :10])
                    if data_df.iloc[kcat_index[0], :10].equals(data_df.iloc[km_index[0], :10]):
                        kcat_value = data_df.loc[kcat_index[0], 'parameter.startValue']
                        km_value = data_df.loc[km_index[0], 'parameter.startValue']
                        # print(type(kcat_value))  # <class 'numpy.float64'>
                        # print(kcat_value)
                        # print(km_value)
                        kcat_unit = data_df.loc[kcat_index[0], 'parameter.unit']
                        km_unit = data_df.loc[km_index[0], 'parameter.unit']
                        # print(type(kcat_unit))   # <class 'str'>
                        # print(kcat_unit)
                        if kcat_unit == 's^(-1)' and km_unit in ['M', 'mol'] :
                            if kcat_value > 0 and km_value > 0 :
                                kcat_km = kcat_value / km_value
                                # print(kcat_km)
                                substrate = data_df.loc[km_index[0], 'parameter.associatedSpecies']
                                new_row = data_df.iloc[km_index[0], 1:10].tolist() + [substrate, str(kcat_km), 'M^(-1)*s^(-1)']
                                # print(new_row)
                                additional_kcatkm.append(new_row)

    return additional_kcatkm

def process_kcatkm(datasets_dir, sub_dir, typeFile) :
    filenames = os.listdir('../complementaryData/data_sabio_EC')
    # print(len(filenames)) # 8236 EC files

    # create empty pandas DataFrame
    columns = ["SUBSTRATES", "PRODUCTS", "EnzymeType", "PubMedID", "ORGANISM", "UNIPROT", "EC", "PH", "Temperature",
                                       "SUBSTRATE", "KCAT/KM VALUE", "UNIT"]
    sabio_df = pd.DataFrame(columns = columns)
    i = 0
    data_list = list()
    for filename in filenames :
        # print(filename[:-4])  # This is EC Number

        # filename = "1.1.1.6.txt"  # One example
        with open("../complementaryData/data_sabio_EC/%s" % filename, 'r', encoding="utf-8") as infile :
            lines = infile.readlines()

        for line in lines[1:] :
            data = line.strip().split('\t')
            try :
                if data[10].lower() == 'kcat/km' and data[12] :
                    # print(data)
                    i += 1
                    # print(i)
                    new_row = data[1:10] + data[11:13] + [data[-1]]
                    # print(new_row)
                    # print(data[12])
                    # print(type(data[12]))

                    data_list.append(new_row)
            except :
                continue

    sabio_df = pd.DataFrame(data_list, columns = columns)
    print("Sabio_df with kcat/Km:", len(sabio_df))  # 18971
    additional_kcatkm = calculate_kcatkm()          # 7253
    print("Additional kcat/Km:", len(additional_kcatkm))
    new_df = pd.DataFrame(additional_kcatkm, columns = columns)
    # print(len(new_df))

    sabio_df = pd.concat([sabio_df, new_df], ignore_index=True)
    print("Total kcat/Km in Sabio-RK database:", len(sabio_df))  # 26224
    sabio_df.to_csv(join(datasets_dir, sub_dir, "sabio_df_%s_download.csv" % typeFile), index=False)


if __name__ == '__main__' :
    datasets_dir = "../complementaryData"
    sub_dir = "data_sabio"
    process_km(datasets_dir, sub_dir, typeFile="KM")
    process_kcat(datasets_dir, sub_dir, typeFile="KCAT")
    process_kcatkm(datasets_dir, sub_dir, typeFile="KCATKM")


