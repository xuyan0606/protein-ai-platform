#!/usr/bin/python
# coding: utf-8
# Date: 2024-04-22
# Updated: 2024-09-13

import re
import ast
import numpy as np
import pandas as pd
from os.path import join
from decimal import Decimal


def getPH(row) :
    desc = row["COMMENTARY"]
    pH = ""
    # print(desc)
    if "pH" in desc :
        pH_matches = re.findall(r'pH\s+(\d+(?:\.\d+)?)', desc)
        if pH_matches:
            pH = pH_matches[0]
        # print(pH)
    return pH

def getTemperature(row):
    desc = row["COMMENTARY"]
    temperature = ""
    # print(desc)
    temperature_matches = re.findall(r'(\d+)xc2xb', desc)
    if temperature_matches:
        temperature = temperature_matches[0]
        # print(temperature)
    return temperature

def enzymeType_brenda(row) :
    desc = row["COMMENTARY"]
    enzymeType = ""
    # print(desc)
    if 'mutant' in desc or 'mutated' in desc :
        mutant = re.findall('[A-Z]\d+[A-Z]', desc)
        if len(mutant) >= 1 :
            enzymeType = "/".join(mutant)
        else :
            enzymeType = "No mutants found"
    else :
        enzymeType = "wildtype"
    # print(enzymeType)
    return enzymeType

# Usage: test_uniprot(data_df_kcat)
def test_uniprot(df) :
    # df['UNIPROT'] = df['UNIPROT'].apply(ast.literal_eval)
    df = df.head(10)
    # df = df.tail(1000)
    i = 0
    for index, row in df.iterrows() :
        uniprot = row["UNIPROT"]
        i += 1
        print(i)
        print(uniprot)
        # print(type(uniprot))  # <class 'list'>

def process_UNIPROT_ID(string):
    if string[0] == "<" or string[1] == "<":
        string = string[string.find(">")+1:]
    return string

# The uniprot_brenda function is to process UNIPROT ID shown below:
# ['P16027; <a href="javascript:Sequence2(\'P14775\')">P14775; P14774']
# ['Q00456; <a href="javascript:Sequence2(\'Q00457\')">Q00457; <a href="javascript:Sequence2(\'Q00460\')">Q00460']
# to change it to: ['Q00456', 'Q00457', 'Q00460']
# ['Q9X0C6; <a href="javascript:Sequence2(\'Q9X0C8\')">Q9X0C8', 'Q9X0C8; <a href="javascript:Sequence2(\'Q9X0C6\')">Q9X0C6']
def uniprot_brenda(row) :
    UNIPROT = row["UNIPROT"]
    UNIPROT_list = list()
    for uniprot in UNIPROT :
        UNIPROT_list += [process_UNIPROT_ID(ID) for ID in uniprot.split("; ")]
    UNIPROT_ID = ",".join(UNIPROT_list)
    return UNIPROT_ID

def replace_ranges_of_kinetics_values_with_means(df, typeValue):
    for ind in df.index:
        KINETICS = df.at[ind, typeValue]
        if "-" in KINETICS:
            KINETICS = np.mean([float(kinetics) for kinetics in KINETICS.split(" - ")])
            df.at[ind, typeValue] = float(KINETICS)
    return df

def enzymeType_sabio(row) :
    desc = row["EnzymeType"]
    # print(desc)
    if "mutant" in desc or 'mutated' in desc :
        mutant = re.findall('[A-Z]\d+[A-Z]', desc)
        if len(mutant) >= 1 :
            enzymeType = "/".join(mutant)
        else :
            enzymeType = "No mutants found"
    else :
        enzymeType = "wildtype"
    # print(enzymeType)
    return enzymeType

def uniprot_sabio(row):
    uniprot = row["UNIPROT"]
    # print(uniprot)
    if pd.isna(uniprot):
        UNIPROT_ID = ""
    else:
        UNIPROT_ID = uniprot.replace(" ", ",")
    # print(UNIPROT_ID)
    # print(type(UNIPROT_ID))
    return UNIPROT_ID

def process_values(value, max_decimals=3, threshold=0.001):
    str_value = str(value)

    # Check if the value is in scientific notation
    if 'e' in str_value or 'E' in str_value:
        # print(str_value)
        value = Decimal(value)
        str_value = str(value)
        # print(value)
        # print(str_value)
    
    # Check if the value has decimal places
    if '.' in str_value:
        decimals = len(str_value.split('.')[1])
        
        # Round to max_decimals if decimal places exceed max_decimals
        if decimals > max_decimals:
            if value >= threshold :
                return round(value, max_decimals)
            else :
                # Split into integer and fractional parts
                integer_part, fractional_part = str_value.split('.')

                # Count leading zeros in the fractional part
                leading_zeros = len(fractional_part) - len(fractional_part.lstrip('0'))

                # decimals = leading zeros + 1 for extra precision beyond leading zeros
                decimals = leading_zeros + 1

                # print(value)
                # print(decimals)
                # print(round(value, decimals))
                # Round the value based on the calculated decimals (for extra precision)
                return float(round(value, decimals))

                # print(value)
                # return round(value, extra_prec)

        else :
            return value

    # If there's no decimal part, return the value 
    return value

def process_brenda(datasets_dir, sub_dir, typeFile, typeValue) :
    brenda_df_data = pd.read_csv(join(datasets_dir, sub_dir, "brenda_df_%s_process.csv" % typeFile))
    # brenda_df_data = brenda_df_data.head(1000)
    brenda_df_data = brenda_df_data.drop(brenda_df_data.columns[0], axis=1)
    print("Process %s in BRENDA:" % typeFile.lower())

    brenda_df_data['PH'] = brenda_df_data.apply(getPH, axis=1)
    brenda_df_data['Temperature'] = brenda_df_data.apply(getTemperature, axis=1)
    brenda_df_data['EnzymeType'] = brenda_df_data.apply(enzymeType_brenda, axis=1)
    brenda_df_data['UNIPROT'] = brenda_df_data['UNIPROT'].apply(ast.literal_eval)
    brenda_df_data["UNIPROT"] = brenda_df_data.apply(uniprot_brenda, axis=1)
    brenda_df_data = replace_ranges_of_kinetics_values_with_means(df=brenda_df_data, typeValue=typeValue)
    brenda_df_data.drop(columns=["COMMENTARY"], inplace=True)
    brenda_df_data.drop(columns=["LITERATURE"], inplace=True)
    # new_order = ["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", typeValue, "PubMedID"]
    # brenda_df_data = brenda_df_data.reindex(columns=new_order)
    new_order = ["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "PubMedID", typeValue]
    brenda_df_data = brenda_df_data.reindex(columns=new_order)
    brenda_df_data['PubMedID'] = pd.to_numeric(brenda_df_data['PubMedID'], errors='coerce')
    brenda_df_data['PubMedID'] = brenda_df_data['PubMedID'].apply(lambda x: str(int(x)) if pd.notna(x) else '')
    
    # This error was found by chance, and we also contacted the BRENDA team about this
    mask = (
        (brenda_df_data['EC'] == '1.1.1.1') &
        (brenda_df_data['ORGANISM'] == 'Sulfolobus acidocaldarius') &
        (brenda_df_data['UNIPROT'] == 'Q4J702,Q4J9F2')
    )
    brenda_df_data.loc[mask, 'UNIPROT'] = 'Q4J702'

    n_old = len(brenda_df_data)
    brenda_df_data = brenda_df_data.loc[brenda_df_data["EnzymeType"] != "No mutants found"]
    print("We remove %s out of %s data points, because they are mutants but no mutated sites found."
          % (n_old - len(brenda_df_data), n_old))

    brenda_df_data.loc[:, typeValue] = brenda_df_data[typeValue].astype(float)
    brenda_df_data = brenda_df_data.loc[brenda_df_data[typeValue] > 0]
    # column_types = brenda_df_data.dtypes

    n_old = len(brenda_df_data)
    brenda_df_data = brenda_df_data.drop_duplicates(keep="first").reset_index(drop=True)
    print("We remove %s out of %s data points, because they are duplaictes."
          % (n_old - len(brenda_df_data), n_old))

    n_old = len(brenda_df_data)
    brenda_df_data = brenda_df_data.groupby(["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "PubMedID"], as_index=False)
    brenda_df_data = brenda_df_data[typeValue].max()
    # brenda_df_data = brenda_df_data[["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "PubMedID", typeValue]]
    print("By grouping data points with same EC number, substrate, organism and UniProt ID, this changes the number of data points from %s to %s." % (n_old, len(brenda_df_data)))

    if typeFile == "KCAT" :
        brenda_df_data["UNIT"] = "1/s"
    if typeFile == "KM" :
        brenda_df_data["UNIT"] = "mM"
    if typeFile == "KCATKM" :
        brenda_df_data["UNIT"] = "1/mM*1/s"
    brenda_df_data.reset_index(drop=True, inplace=True)
    print("Done!")

    return brenda_df_data

def process_sabio(datasets_dir, sub_dir, typeFile, typeValue) :
    # datasets_dir = "../complementaryData"
    # sub_dir = "data_sabio"
    # typeFile = "KCAT"
    # typeValue = "KCAT VALUE"
    sabio_df_data = pd.read_csv(join(datasets_dir, sub_dir, "sabio_df_%s_download.csv" % typeFile))
    # sabio_df_data = sabio_df_data.head(1000)
    print("Process %s in Sabio-RK:" % typeFile.lower())

    new_order = ["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "PubMedID", typeValue, "UNIT"]
    sabio_df_data = sabio_df_data.reindex(columns=new_order)
    sabio_df_data['PubMedID'] = pd.to_numeric(sabio_df_data['PubMedID'], errors='coerce')
    sabio_df_data['PubMedID'] = sabio_df_data['PubMedID'].apply(lambda x: str(int(x)) if pd.notna(x) else '')

    sabio_df_data.loc[:, 'PH'] = sabio_df_data['PH'].astype(str).replace('-', '')
    sabio_df_data.loc[:, 'Temperature'] = sabio_df_data['Temperature'].astype(str).replace('-', '')
    sabio_df_data['EnzymeType'] = sabio_df_data.apply(enzymeType_sabio, axis=1)
    sabio_df_data["UNIPROT"] = sabio_df_data.apply(uniprot_sabio, axis=1)

    n_old = len(sabio_df_data)
    sabio_df_data = sabio_df_data.loc[sabio_df_data["EnzymeType"] != "No mutants found"]
    print("We remove %s out of %s data points, because they are mutants but no mutated sites found."
          % (n_old - len(sabio_df_data), n_old))

    n_old = len(sabio_df_data)
    if typeFile == "KCAT" :
        sabio_df_data = sabio_df_data[sabio_df_data["UNIT"].isin(['s^(-1)'])]       
        sabio_df_data.loc[:, "UNIT"] = "1/s"
    if typeFile == "KM" :
        sabio_df_data = sabio_df_data[sabio_df_data["UNIT"].isin(['M', 'mol'])]
        sabio_df_data[typeValue] *= 1000
        sabio_df_data.loc[:, "UNIT"] = "mM"
    if typeFile == "KCATKM" :
        sabio_df_data = sabio_df_data[sabio_df_data["UNIT"].isin(['M^(-1)*s^(-1)', 'mol^(-1)*s^(-1)'])]
        sabio_df_data[typeValue] /= 1000
        sabio_df_data.loc[:, "UNIT"] = "1/mM*1/s"
    # sabio_df_data.reset_index(drop=True, inplace=True)
    print("We remove %s out of %s data points, in order to unifying the units."
          % (n_old - len(sabio_df_data), n_old))

    # Apply the processing function to the kinetics value column
    sabio_df_data.loc[:, typeValue] = sabio_df_data[typeValue].apply(lambda x: process_values(x, max_decimals=3, threshold=0.001))

    sabio_df_data.loc[:, typeValue] = sabio_df_data[typeValue].astype(float)
    sabio_df_data = sabio_df_data.loc[sabio_df_data[typeValue] > 0]
    column_types = sabio_df_data.dtypes
    # column_types

    n_old = len(sabio_df_data)
    sabio_df_data = sabio_df_data.drop_duplicates(keep="first").reset_index(drop=True)
    print("We remove %s out of %s data points, because they are duplaictes."
          % (n_old - len(sabio_df_data), n_old))

    n_old = len(sabio_df_data)
    sabio_df_data = sabio_df_data.groupby(["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "PubMedID", "UNIT"], as_index= False)
    sabio_df_data = sabio_df_data[typeValue].max()
    sabio_df_data = sabio_df_data[["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "PubMedID", typeValue, "UNIT"]]
    print("By grouping data points with same EC number, substrate, organism and UniProt ID, this changes the number of data points from %s to %s." % (n_old, len(sabio_df_data)))
    sabio_df_data.reset_index(drop=True, inplace=True)
    print("Done!")

    # # Step I: Test the duplicates screening approach
    # sabio_df_data_copy = sabio_df_data.head(30)
    # sabio_df_data_copy = sabio_df_data_copy.groupby(["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "UNIT"], as_index= False)
    # max_duplicates = sabio_df_data_copy["KCAT VALUE"].max()
    # max_duplicates = max_duplicates[["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "KCAT VALUE", "UNIT"]]
    # max_duplicates

    # # Step II: Validate what I did in step I is right
    # # Only check duplicates
    # sabio_df_data_copy = sabio_df_data.head(30)
    # duplicates = sabio_df_data_copy[sabio_df_data_copy.duplicated(subset=["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "UNIT"], keep=False)]
    # groups = duplicates.groupby(["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "UNIT"])
    # for name, group in groups:
    #     print("Group:", name)
    #     display(group.head())

    # i = 0
    # for index, row in sabio_df_data.iterrows() :
    #     Temperature = row["Temperature"]
    #     i += 1
    #     # print(i)
    #     print(Temperature)
    #     print(type(Temperature))  # <class 'str'>  In BRENDA, tem="37", while in Sabio, tem="37.0"

    return sabio_df_data

def data_combination() :
    datasets_dir = "../complementaryData"
    brenda_dir = "data_brenda"
    sabio_dir = "data_sabio"
    combine_dir = "data_combination"
    # categories = ["KCAT"]
    categories = ["KCAT", "KM", "KCATKM"]
    categories_values = {"KCAT": "KCAT VALUE", "KM": "KM VALUE", "KCATKM": "KCAT/KM VALUE"}
    for category in categories :
        typeValue = categories_values[category]
        brenda_df_data = process_brenda(datasets_dir, brenda_dir, category, typeValue)
        sabio_df_data = process_sabio(datasets_dir, sabio_dir, category, typeValue)
        data_df_kinetics = pd.concat([brenda_df_data, sabio_df_data], ignore_index=True) 
        # filtered_df = data_df_kinetics[data_df_kinetics["UNIPROT"]!=""]
        print("Data combination process: for %s" % category.lower())

        # columns_to_convert = ["PH", "Temperature", typeValue]
        # typeValue = "KCAT VALUE"
        columns_to_convert = [typeValue]
        data_df_kinetics[columns_to_convert] = data_df_kinetics[columns_to_convert].astype(float)
        data_df_kinetics["PH"] = pd.to_numeric(data_df_kinetics["PH"], errors='coerce').fillna(data_df_kinetics["PH"])
        data_df_kinetics["Temperature"] = pd.to_numeric(data_df_kinetics["Temperature"], errors='coerce').fillna(data_df_kinetics["Temperature"])
        # column_types = data_df_kinetics.dtypes

        n_old = len(data_df_kinetics)
        data_df_kinetics = data_df_kinetics.drop_duplicates(keep="first").reset_index(drop=True)
        print("We remove %s out of %s data points, because they are duplaictes."
              % (n_old - len(data_df_kinetics), n_old))

        n_old = len(data_df_kinetics)
        data_df_kinetics = data_df_kinetics.groupby(["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "PubMedID", "UNIT"], as_index= False)
        data_df_kinetics = data_df_kinetics[typeValue].max()
        data_df_kinetics = data_df_kinetics[["EC", "SUBSTRATE", "ORGANISM", "UNIPROT", "EnzymeType", "PH", "Temperature", "PubMedID", typeValue, "UNIT"]]
        print("By grouping data points with same EC number, substrate, organism and UniProt ID, this changes the number of data points from %s to %s." % (n_old, len(data_df_kinetics)))
        data_df_kinetics.reset_index(drop=True, inplace=True)
        print("Done!")

        # write output file
        data_df_kinetics.to_csv(join(datasets_dir, combine_dir, "data_df_%s.csv" % category), index=False)


if __name__ == '__main__' :
    data_combination()


