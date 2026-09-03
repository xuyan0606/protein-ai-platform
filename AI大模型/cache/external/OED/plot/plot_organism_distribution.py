#!/usr/bin/python
# coding: utf-8

import pandas as pd
from os.path import join
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib import rc


def organism_summary(datasets_dir, sub_dir, typeFile) :
    data_df = pd.read_csv(join(datasets_dir, sub_dir, "data_df_%s.csv" % typeFile))
    organisms = data_df["ORGANISM"].tolist()
    print("Total organisms:", len(organisms))
    # print(organisms[:3])

    # Count occurrences of each species
    species_counts = {}
    for organism in organisms:
        species_counts[organism] = species_counts.get(organism, 0) + 1

    # Sort species by counts and select top 10
    sorted_species_counts = sorted(species_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    species, counts = zip(*sorted_species_counts)
    print(sorted_species_counts)

    return species, counts

def plot(datasets_dir, sub_dir, typeFile) :
    species, counts = organism_summary(datasets_dir, sub_dir, typeFile)

    # Plot barh for this
    plt.figure(figsize=(1.2, 2.3))
    rc('font',**{'family':'serif','serif':['Arial']})
    plt.rcParams['pdf.fonttype'] = 42
    plt.axes([0.12,0.12,0.83,0.83])

    plt.tick_params(direction='in')
    plt.tick_params(which='major',length=1.5)
    plt.tick_params(which='major',width=0.4)

    plt.barh(species[::-1], counts[::-1], color='#F0988C', edgecolor='black', linewidth=0.5)  # Use barh for horizontal bar plot
    if typeFile == "KCAT" :
        plt.xlabel('$k$$_\mathregular{cat}$ counts', fontsize=7)  # Y-axis label becomes count
        plt.xticks(ticks=[0, 3000, 6000, 9000, 12000], fontsize=7)
    if typeFile == "KM" :
        plt.xlabel('$K$$_\mathregular{m}$ counts', fontsize=7)  # Y-axis label becomes count
        plt.xticks(ticks=[0, 8000, 16000, 24000], fontsize=7)
    if typeFile == "KCATKM" :
        plt.xlabel('$k$$_\mathregular{cat}$/$K$$_\mathregular{m}$ counts', fontsize=7)  # Y-axis label becomes count
        plt.xticks(ticks=[0, 2000, 4000, 6000, 8000], fontsize=7)
    plt.yticks(fontsize=7, fontstyle='italic')  # Make y-axis labels italic
    # plt.grid(axis='x', linestyle='--', alpha=0.7)  # Add vertical grid lines

    ax = plt.gca()
    ax.spines['bottom'].set_linewidth(0.5)
    ax.spines['left'].set_linewidth(0.5)
    ax.spines['top'].set_linewidth(0.5)
    ax.spines['right'].set_linewidth(0.5)
    plt.savefig("../figures/organism_%s_barh.pdf" % typeFile.lower(), dpi=400, bbox_inches='tight')
    plt.close()

    # # Plot bar for this
    # plt.figure(figsize=(3.0, 1.5))
    # rc('font',**{'family':'serif','serif':['Arial']})
    # plt.rcParams['pdf.fonttype'] = 42
    # plt.axes([0.12,0.12,0.83,0.83])

    # plt.tick_params(direction='in')
    # plt.tick_params(which='major',length=1.5)
    # plt.tick_params(which='major',width=0.4)

    # plt.bar(species, counts, color='skyblue', edgecolor='black', linewidth=0.5)
    # if typeFile == "KCAT" :
    #     plt.ylabel('$k$$_\mathregular{cat}$ counts', fontsize=7)  # Y-axis label becomes count
    #     plt.yticks(ticks=[0, 1000, 2000, 3000, 4000, 5000], fontsize=7)
    # if typeFile == "KM" :
    #     plt.ylabel('$K$$_\mathregular{m}$ counts', fontsize=7)  # Y-axis label becomes count
    #     plt.yticks(ticks=[0, 2000, 4000, 6000, 8000], fontsize=7)
    # if typeFile == "KCATKM" :
    #     plt.ylabel('$k$$_\mathregular{cat}$/$K$$_\mathregular{m}$ counts', fontsize=7)  # Y-axis label becomes count
    #     plt.yticks(ticks=[0, 1000, 2000, 3000, 4000], fontsize=7)
    # plt.xticks(rotation=45, ha='right', fontsize=7, fontstyle='italic')
    # # plt.grid(axis='y', linestyle='--', alpha=0.7)

    # ax = plt.gca()
    # ax.spines['bottom'].set_linewidth(0.5)
    # ax.spines['left'].set_linewidth(0.5)
    # ax.spines['top'].set_linewidth(0.5)
    # ax.spines['right'].set_linewidth(0.5)
    # plt.savefig("../figures/organism_%s_bar.pdf" % typeFile.lower(), dpi=400, bbox_inches='tight')
    # plt.close()


if __name__ == '__main__' :
    datasets_dir = "../data"
    sub_dir = "data_API"
    categories = ["KCAT", "KM", "KCATKM"]
    for category in categories :
        print("This is for:", category.lower())
        plot(datasets_dir, sub_dir, typeFile=category)


