# [**OED**](https://openenzymedb.platform.moleculemaker.org/home) 

<!-- <p align="center">
  <img  src="picture/OED_overview.png" width = "800">
</p> -->
![OED Graphical Abstract](picture/OED_overview.png "OED Graphical Abstract")

## Introduction

The **Open Enzyme Database (OED)**  is a community-driven resource developed for researchers and professionals in biochemistry, molecular biology, enzymology, protein and metabolic engineering, and related fields. As a unified web-based platform for exploring enzyme data, OED provides curated information on enzyme kinetic parameters, structural data, and functional annotations. It also features state-of-the-art AI models for enzyme property prediction and cheminformatics-powered enzyme recommendations, with ongoing expansion to incorporate additional enzyme-related data such as enzyme solubility, stability, specificity, functions, and beyond. The resource is freely available at https://openenzymedb.platform.moleculemaker.org/.


## Repository Structure

```text
OED/
├── code/                 # Python scripts
├── complementaryData/    # Complementary datasets
├── data/                 # Main datasets
├── figures/              # Figures for visualizations
├── LICENSE.md            # License information
├── picture/              # Images for OED overview
├── plot/                 # Scripts for generating plots
├── README.md             # Project README file
└── requirements.txt      # Python dependencies
```


## Usage

1. Install the latest version with:
```bash
git clone https://github.com/le-yuan/OED.git
cd OED
pip install -r requirements.txt
```

2. If you want to download, process, and clean enzyme data from various sources, you can run a script such as:
```linux
python code/sabio_download.py
``` 

3. If you want to analyze and visualize data in the OED, you can run a script such as:
```linux
python plot/plot_EC_percentage.py
``` 


## Citation

If you use **OED** in your research, please cite:

> Le Yuan, David M. Bianchi, Katherine Arneson, Bingji Guo, Sara Lambert, Chris Stephens, Yash H. Wasnik, Christopher Pond, Matthew J. Berry, and Huimin Zhao. (2025). **Open Enzyme Database: A Community-wide Repository for Sharing Enzyme Data.** *Nucleic Acids Research*, gkaf1082. https://doi.org/10.1093/nar/gkaf1082


## Contact

-   Le Yuan ([@le-yuan](https://github.com/le-yuan)), University
    of Illinois Urbana-Champaign, Urbana, IL, USA

