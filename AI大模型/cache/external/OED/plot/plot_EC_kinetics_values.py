#!/usr/bin/python
# coding: utf-8
# Reference:
# https://github.com/feiranl/GotEnzymes/tree/main

import numpy as np
import pandas as pd
from os.path import join
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib import rc


def EC_kinetics(datasets_dir, sub_dir, typeKinetics, typeValue) :
    EC_kcat_count = dict()
    data_df = pd.read_csv(join(datasets_dir, sub_dir, "data_df_%s.csv" % typeKinetics))

    for j in range(1,8):
        index = data_df['EC'].str.startswith(str(j)+'.',na=False)
        newdf = data_df[index] # extract lines starts with ECxxxx
        newdf = newdf[['EC', typeValue]] # extract two columns
        newdf[typeValue] = newdf[typeValue].astype(float)
        if 'EC' + str(j) not in EC_kcat_count.keys():
            EC_kcat_count['EC' + str(j)] = newdf[typeValue].values
        else:
            EC_kcat_count['EC' + str(j)] = np.append(EC_kcat_count['EC' + str(j)],newdf[typeValue].values)

    return EC_kcat_count

def plot(datasets_dir, sub_dir, typeKinetics, typeValue) :
    EC_kcat_count = EC_kinetics(datasets_dir, sub_dir, typeKinetics, typeValue)

    plt.figure(figsize=(4.3,1.8))
    rc('font',**{'family':'serif','serif':['Arial']})
    plt.rcParams['pdf.fonttype'] = 42
    plt.axes([0.12,0.12,0.83,0.83])

    # plt.rcParams['xtick.direction'] = 'in'
    # plt.rcParams['ytick.direction'] = 'in'

    plt.tick_params(direction='in')
    plt.tick_params(which='major',length=1.5)
    plt.tick_params(which='major',width=0.4)

    # plt.rc('font', family='Helvetica')

    if typeKinetics == "KCAT" :
        plt.ylabel('$k$$_\mathregular{cat}$ (s$^-$$^1$)', fontsize=7)
    if typeKinetics == "KM" :
        plt.ylabel('$K$$_\mathregular{m}$ (mM)', fontsize=7)
    if typeKinetics == "KCATKM" :
        plt.ylabel('$k$$_\mathregular{cat}$/$K$$_\mathregular{m}$ (mM$^-$$^1$*s$^-$$^1$)', fontsize=7)
    # plt.legend(frameon=False, prop={"size":6})

    ax = plt.gca()
    ax.spines['bottom'].set_linewidth(0.5)
    ax.spines['left'].set_linewidth(0.5)
    ax.spines['top'].set_linewidth(0.5)
    ax.spines['right'].set_linewidth(0.5)

    y_all = list()
    print("This is type:", typeKinetics.lower())
    for i in range(1,8):
        y = EC_kcat_count['EC' + str(i)]
        y[y == 0] = 0.00001
        y_all.append(np.log10(y))
        print('Median of the EC', str(i),': ',str(np.median(y)))
        #n,bins = distri_dig(y,'#2c7bb6','E')
        #sns.distplot(y, hist_kws={'cumulative': True, 'density': True}, kde_kws={'cumulative': True})
        #sns.ecdfplot(data=np.log10(y))

    # plot all data
    # print(len(y_all))
    print("\n")
    #print('Median of the Total: ', str(np.median(y_all))) # calculate the meadian
    # calculate ratio of values fall in 1/s to 100/s
    #cats=pd.cut(y_all,[1,100])
    #print(cats)

    #fraction = pd.value_counts(cats)/len(y_all)
    #print('Ratio in 1/s to 100/s: ', str(fraction))

    #n,bins = distri_dig(y_all,'black','Total')
    #sns.distplot(y_all, hist_kws={'cumulative': True, 'density': True}, kde_kws={'cumulative': True})
    #sns.ecdfplot(data=np.log10(y_all))
    #plt.plot(bins[:-1] + width,n,'-',color='black')
    sns.reset_defaults()
    sns.violinplot(x=None, y=None, hue=None,
                       data=y_all, order=None, hue_order=None, 
                       bw='scott', cut=2, scale='area', scale_hue=True, 
                       gridsize=100, width=0.8, inner='box', split=False,
                       dodge=True, orient=None, linewidth=None,
                       color=None, palette=None, saturation=0.75,
                       ax=None)
    sns.set_context("talk",font_scale=0.5,rc={"lines.linewidth":1})
    #plt.xticks([-6.,-4.,-2.,0.,2.,4.,6.])
    #plt.xlim([-4,5])
    #locs, labels = plt.xticks()
    #plt.xticks(locs[1:-1], np.power(10,locs)[1:-1], fontsize = 6)
    #ax = plt.gca()
    #ax.axes.yaxis.set_ticks([])
 
    #leg = plt.legend({'Total'},'Location','northwest','Fontsize',6,'FontName','Helvetica');
    #leg.ItemTokenSize = [0,5];

    plt.yticks([-6.,-4.,-2.,0.,2.,4.,6.,8.])
    plt.ylim([-6,8])
    locs, labels = plt.yticks()
    plt.yticks(locs[1:-1], np.power(10,locs)[1:-1], fontsize = 7)
    ax = plt.gca()
    labels = ax.set_xticklabels(['EC1.x.x.x','EC2.x.x.x','EC3.x.x.x','EC4.x.x.x','EC5.x.x.x','EC6.x.x.x','EC7.x.x.x'],rotation = 30,fontsize = 7)
    # plt.legend()

    rc('font',**{'family':'serif','serif':['Arial']})
    plt.rcParams['pdf.fonttype'] = 42

    plt.savefig("../figures/EC_%s_values.pdf" % typeKinetics.lower(), dpi=400, bbox_inches='tight')
    plt.close()


if __name__ == '__main__' :
    datasets_dir = "../data"
    sub_dir = "data_API"
    categories = ["KCAT", "KM", "KCATKM"]
    categories_values = {"KCAT": "KCAT VALUE", "KM": "KM VALUE", "KCATKM": "KCAT/KM VALUE"}
    for category in categories[:3] :
        plot(datasets_dir, sub_dir, category, categories_values[category])

    # Results:
    # This is type: kcat
    # Median of the EC 1 :  6.2
    # Median of the EC 2 :  1.83
    # Median of the EC 3 :  7.255
    # Median of the EC 4 :  3.2
    # Median of the EC 5 :  15.0
    # Median of the EC 6 :  1.8
    # Median of the EC 7 :  61.0

    # This is type: km
    # Median of the EC 1 :  0.1487
    # Median of the EC 2 :  0.192
    # Median of the EC 3 :  0.26
    # Median of the EC 4 :  0.32
    # Median of the EC 5 :  0.61
    # Median of the EC 6 :  0.18
    # Median of the EC 7 :  0.1

    # This is type: kcatkm
    # Median of the EC 1 :  20.833
    # Median of the EC 2 :  7.3
    # Median of the EC 3 :  26.2
    # Median of the EC 4 :  8.0
    # Median of the EC 5 :  5.39
    # Median of the EC 6 :  14.15
    # Median of the EC 7 :  525.0

