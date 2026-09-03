#!/usr/bin/python
# coding: utf-8
# Date: 2024-04-19

import requests


# Extract EC number list from ExPASy, which is a repository of information relative to the nomenclature of enzymes.
# Command line: 
# cd ./complementaryData
# wget -r -np ftp://ftp.expasy.org/databases/enzyme/
# mv ftp.expasy.org/databases/enzyme ./Enzyme_EC
# rm -r ftp.expasy.org
def eclist():
    with open('../complementaryData/Enzyme_EC/enzyme.dat', 'r') as outfile :
        lines = outfile.readlines()

    ec_list = list()
    for line in lines :
        if line.startswith('ID') :
            ec = line.strip().split('  ')[1][1:]
            ec_list.append(ec)
    print(len(ec_list)) # 8236

    return ec_list

def sabio_info(allEC):
    QUERY_URL = 'http://sabiork.h-its.org/sabioRestWebServices/kineticlawsExportTsv'

    # specify search fields and search terms
    # query_dict = {"Organism":'"lactococcus lactis subsp. lactis bv. diacetylactis"', "Product":'"Tyrosine"'}
    # query_dict = {"Organism":'"lactococcus lactis subsp. lactis bv. diacetylactis"',} #saccharomyces cerevisiae  escherichia coli
    # query_dict = {"ECNumber":'"1.1.1.1"',}
    i = 0
    for EC in allEC :
        i += 1
        print('This is %d ------' %i)
        print(EC)
        query_dict = {"ECNumber":'%s' %EC,}
        query_string = ' AND '.join(['%s:%s' % (k,v) for k,v in query_dict.items()])

        # specify output fields and send request
        # query = {'fields[]':['EntryID', 'Substrate', 'EnzymeType', 'PubMedID', 'Organism', 'UniprotID','ECNumber','Parameter'], 'q':query_string}
        # the 'Smiles' keyword could get all the smiles included in substrate and product
        query = {'fields[]':['EntryID', 'Substrate', 'Product', 'EnzymeType', 'PubMedID', 'Organism', 'UniprotID','ECNumber','pH', 'Temperature', 'Parameter'], 'q':query_string}

        request = requests.post(QUERY_URL, params = query)
        # request.raise_for_status()

        # results
        results = request.text
        # print(results)

        if results :
            with open('../complementaryData/data_sabio_EC/%s.txt' %EC, 'w') as ECfile :
                ECfile.write(results)


if __name__ == '__main__' :
    allEC = eclist()
    sabio_info(allEC)


