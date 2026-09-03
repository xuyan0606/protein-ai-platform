#!/usr/bin/python
# coding: utf-8
# References:
# https://zhuanlan.zhihu.com/p/72534851
# https://pythontic.com/visualization/charts/piechart

import pandas as pd
from os.path import join
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib import rc


def calculate_percentage(datasets_dir, sub_dir, typeKinetics) :
    data_df = pd.read_csv(join(datasets_dir, sub_dir, "data_df_%s.csv" % typeKinetics))
    ECNumbers = data_df["EC"].tolist()
    print("Total entries:", len(ECNumbers))
    # print(ECNumbers[:3])

    cluster_1 = [ECNumber for ECNumber in ECNumbers if ECNumber[0] == '1']
    cluster_2 = [ECNumber for ECNumber in ECNumbers if ECNumber[0] == '2']
    cluster_3 = [ECNumber for ECNumber in ECNumbers if ECNumber[0] == '3']
    cluster_4 = [ECNumber for ECNumber in ECNumbers if ECNumber[0] == '4']
    cluster_5 = [ECNumber for ECNumber in ECNumbers if ECNumber[0] == '5']
    cluster_6 = [ECNumber for ECNumber in ECNumbers if ECNumber[0] == '6']
    cluster_7 = [ECNumber for ECNumber in ECNumbers if ECNumber[0] == '7']

    total_amount = len(cluster_1) + len(cluster_2) + len(cluster_3) + len(cluster_4) + len(cluster_5) + len(cluster_6) + len(cluster_7)
    print('The total amount of senven clusters is:', total_amount)

    EC_Percentage= dict()
    EC_Percentage['EC=1.*'] = len(cluster_1)/total_amount
    EC_Percentage['EC=2.*'] = len(cluster_2)/total_amount
    EC_Percentage['EC=3.*'] = len(cluster_3)/total_amount
    EC_Percentage['EC=4.*'] = len(cluster_4)/total_amount
    EC_Percentage['EC=5.*'] = len(cluster_5)/total_amount
    EC_Percentage['EC=6.*'] = len(cluster_6)/total_amount
    EC_Percentage['EC=7.*'] = len(cluster_7)/total_amount

    return EC_Percentage

def plot(datasets_dir, sub_dir, typeKinetics) :
    EC_Percentage = calculate_percentage(datasets_dir, sub_dir, typeKinetics)

    data = pd.Series(EC_Percentage)

    # myfont=FontProperties(size=14)
    # sns.set(font=myfont.get_name())

    plt.rcParams['figure.figsize'] = (1.8, 2.5)

    # To solve the 'Helvetica' font cannot be used in PDF file
    # https://stackoverflow.com/questions/59845568/the-pdf-backend-does-not-currently-support-the-selected-font
    # rc('font',**{'family':'serif','serif':['Helvetica']})
    rc('font',**{'family':'serif','serif':['Arial']})
    plt.rcParams['pdf.fonttype'] = 42

    # plt.axes([0.12,0.12,0.83,0.83])

    lbs= data.index
    # explodes=[0.1 if i=='EC=1.*' else 0 for i in lbs]
    explodes=[0.1, 0.0, 0.0, 0.0, 0.2, 0.4, 0.8]
    # plt.pie(data, explode=explodes,labels=lbs, autopct="%1.1f%%",
    #                                 colors=sns.color_palette("muted"),startangle = 90,pctdistance = 0.6,
    #           textprops={'fontsize':14,'color':'black'})

    plt.pie(data, explode=explodes, labels=lbs, autopct="%1.2f%%",
                                    colors=sns.color_palette("muted"),startangle = 90,pctdistance = 0.6,
              textprops={'fontsize':7,'color':'black'})

    plt.axis('equal')

    plt.savefig("../figures/EC_%s_percentage.pdf" % typeKinetics.lower(), dpi=400, bbox_inches='tight')
    plt.close()


if __name__ == '__main__' :
    datasets_dir = "../data"
    sub_dir = "data_API"
    categories = ["KCAT", "KM", "KCATKM"]
    for category in categories :
        plot(datasets_dir, sub_dir, category)


