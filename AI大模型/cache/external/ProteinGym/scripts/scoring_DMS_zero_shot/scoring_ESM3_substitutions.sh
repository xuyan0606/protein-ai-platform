#!/bin/bash 

source ../zero_shot_config.sh
source activate proteingym_env

export dms_output_folder=${DMS_output_score_folder_subs}/ESM3/ 

python ../../proteingym/baselines/evoscale/compute_fitness.py \
    --model_type "esm3_open" \
    --reference_csv ${DMS_reference_file_path_subs} \
    --dms_dir ${DMS_data_folder_subs} \
    --pdb_dir ${DMS_structure_folder} \
    --output_dir ${dms_output_folder} \
    --use_structure
