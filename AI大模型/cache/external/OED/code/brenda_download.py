#!/usr/bin/python
# coding: utf-8
# Date: 2024-04-20

import time
import hashlib
from zeep import Client
import pandas as pd
from os.path import join
from urllib.request import urlopen, Request


headers= {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) ' 
                      'AppleWebKit/537.11 (KHTML, like Gecko) '
                      'Chrome/23.0.1271.64 Safari/537.11',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
        'Accept-Encoding': 'none',
        'Accept-Language': 'en-US,en;q=0.8',
        'Connection': 'keep-alive'}

wsdl = "https://www.brenda-enzymes.org/soap/brenda_zeep.wsdl"
email = 'YourAccount'
brenda_password = 'YourPassword'
password = hashlib.sha256(brenda_password.encode("utf-8")).hexdigest()
client = Client(wsdl)


def download_kinetics_from_Brenda(EC, typeKinetics):
    reg_url = "https://www.brenda-enzymes.org/enzyme.php?ecno=" + EC
    req = Request(url=reg_url, headers=headers) 
    html = str(urlopen(req).read())
    if typeKinetics == "KCAT" :
        html = html[html.find('<a name="TURNOVER NUMBER [1/s]"></a>') : ]
    if typeKinetics == "KM" :
        html = html[html.find('<a name="KM VALUE [mM]"></a>') : ]
    if typeKinetics == "KCAT/KM" :
        html = html[html.find('<a name="kcat/KM VALUE [1/mMs<sup>-1</sup>]"></a>') : ]
    html = html[ : html.find(" </div>\\n")]
    return(html)

def get_entry_from_html(typeKinetics, html, entry, sub_entry = 0):
    if typeKinetics == "KCAT" : # tab44r3sr0c1
        ID = "tab44r" + str(entry) + "sr" + str(sub_entry) + "c"
    if typeKinetics == "KM" :   # tab12r3sr0c1
        ID = "tab12r" + str(entry) + "sr" + str(sub_entry) + "c"
    if typeKinetics == "KCAT/KM" :  # tab305r3sr0c1
        ID = "tab305r" + str(entry) + "sr" + str(sub_entry) + "c"
    data = []
    for i in range(6):
        search_string = '<div id="'+ ID + str(i) + '" class="cell"><span>'
        pos = html.find(search_string) 
        if pos == -1: #string was not found, try again with different string
            search_string = '<div id="'+ ID + str(i) + '" class="cell notopborder">'
            pos = html.find(search_string)
            if pos == -1: #string was not found, try again with different string
                search_string = '<div id="'+ ID + str(i) + '" class="cell"><span'
                pos = html.find(search_string)
        if pos != -1: #string was found
            subtext = html[pos+len(search_string):]
            data.append(subtext[:subtext.find("\\n")])
        else: 
            return([])
    return(data)

def process_string(string):
    if string[0] == "<":
        string = string[string.find(">")+1:]
    string = string.replace("\\", "")
    string = string.replace("</a>", "")
    return(string)

def process_string_V2(string):
    if ">" in string:
        string = string[string.find(">")+1:]
    return(string)

def process_UNIPROT_string(string):
    if "</span></div><div id=" in string:
        string = string[:string.find("</span></div><div id=")]
    return(string)

def process_UNIPROT_ID(string):
    if string[0] == "<" or string[1] == "<":
        string = string[string.find(">")+1:]
    return(string)

def add_kinetics_for_EC_number(brenda_df, EC, typeKinetics):
    html = download_kinetics_from_Brenda(EC = EC, typeKinetics = typeKinetics)
    
    entry = 0
    sub_entry = 0
    found_entry = True
    while found_entry == True:

        data = get_entry_from_html(typeKinetics = typeKinetics, html = html, entry = entry, sub_entry = sub_entry)
        if data != []:
            found_entry = True
            sub_entry +=1
            
            Kinetics_value = process_string(data[0])
            UNIPROT = process_string(data[3])
            
            if UNIPROT != "-":
                UNIPROT = process_UNIPROT_string(UNIPROT)
                UNIPROT_list = [process_UNIPROT_ID(ID) for ID in UNIPROT.split(", ")]
            else:
                UNIPROT_list = []
                
            if "additional information" not in Kinetics_value:
                new_row = pd.DataFrame([{"EC": EC, typeKinetics+" VALUE" : Kinetics_value, 
                                              "SUBSTRATE": process_string_V2(process_string(data[1])),
                                              "ORGANISM": process_string_V2(process_string(data[2])),
                                              "UNIPROT": UNIPROT_list,
                                              "COMMENTARY": process_string(data[4]), "LITERATURE": process_string(data[5])}])
                brenda_df = pd.concat([brenda_df, new_row], ignore_index=True)

        elif sub_entry == 0:
            found_entry = False
        else:
            entry +=1
            sub_entry = 0
    return(brenda_df)

def ECNumber():
    parameters = (email,password)
    EC_numbers = client.service.getEcNumbersFromEcNumber(*parameters)
    print("There exist %s different EC numbers in the BRENDA database." % len(EC_numbers))  # 8424
    return EC_numbers

def main(typeKinetics) :
    # create empty pandas DataFrame
    brenda_df = pd.DataFrame(columns = ["EC", typeKinetics+" VALUE", "SUBSTRATE", "ORGANISM", "UNIPROT", "COMMENTARY",
                                       "LITERATURE"])
    count = 0
    datasets_dir = "../complementaryData"
    EC_numbers = ECNumber()  # 8424
    if typeKinetics in ["KCAT", "KM"] :
        typeFile = typeKinetics
    if typeKinetics not in ["KCAT", "KM"] :
        typeFile = typeKinetics.replace("/", "")  # For KCAT/KM

    for EC in EC_numbers :
        count += 1
        print(count)
        print(EC)
        if count % 2000 == 0 :
            time.sleep(100)

        try :
            brenda_df = add_kinetics_for_EC_number(brenda_df = brenda_df, EC = EC, typeKinetics = typeKinetics)
        except :
            continue

        if count % 100 == 0 : # save the DataFrame after 100 hundred steps:
            brenda_df.to_csv(join(datasets_dir, "data_brenda", "brenda_df_%s_download.csv" % typeFile))
        time.sleep(0.2)
        
    brenda_df.to_csv(join(datasets_dir, "data_brenda", "brenda_df_%s_download.csv" % typeFile))


if __name__ == '__main__' :
    main("KCAT")
    main("KM")
    main("KCAT/KM")


