import pandas as pd
import numpy as np
import os
from pathlib import Path

out_dir = Path("D:/work buddy data/2026-07-14-14-30-22/突变体数据标准化_交付包_修订版")
out_dir.mkdir(parents=True, exist_ok=True)

# ===========================
# 0. Metadata
# ===========================
METADATA = {
    "enzyme_name": "酸性蛋白酶",
    "expression_system": "毕赤酵母分泌表达",
    "host_organism": "毕赤酵母 (Pichia pastoris)",
    "sample_source": "发酵上清液（分泌表达，无细胞破碎步骤）",
    "assay_method": "蛋白酶国标法（福林酚法）",
    "assay_standard": "GB/T 23527",
    "thermal_stability_condition": "80°C, 3min",
    "optimization_target": "提高热稳定性 + 提高比活力（单点突变难以双正，需多轮改造）",
    "data_source": "上交大数据",
    "processing_date": "2026-07-14",
    "processing_note": "分泌表达体系，酶分泌至上清后直接稀释测定，无破碎步骤。低酶活混杂因素为表达水平/上样量/稀释倍数差异，非破碎效果。",
}

# ===========================
# 1. Source data
# ===========================

# Batch 1 一轮突变体 - 一次反馈 (from Excel Sheet1)
# Columns: 突变体, 酶活相对比例(%), 比活力, 80℃,3min耐温性
batch1_round1 = {
    "P236T": {"rel_activity_pct": 0.6 * 100, "specific_activity": 41.42, "therm_resid_80c": 0.4632 * 100},
    "P236Q": {"rel_activity_pct": 0.55 * 100, "specific_activity": 35.79, "therm_resid_80c": 0.5161 * 100},
    "T332S": {"rel_activity_pct": 0.48 * 100, "specific_activity": 53.52, "therm_resid_80c": 0.7438 * 100},
    "N340D": {"rel_activity_pct": 0.67 * 100, "specific_activity": 58.94, "therm_resid_80c": 0.5927 * 100},
    "P380T": {"rel_activity_pct": 0.32 * 100, "specific_activity": 36.42, "therm_resid_80c": 0.8867 * 100},
    "E240S": {"rel_activity_pct": 0.66 * 100, "specific_activity": 84.11, "therm_resid_80c": 0.4841 * 100},
    "K293S": {"rel_activity_pct": 0.32 * 100, "specific_activity": 20.45, "therm_resid_80c": 0.8761 * 100},
    "I356L": {"rel_activity_pct": 0.60 * 100, "specific_activity": 46.21, "therm_resid_80c": 0.7169 * 100},
    "F361L": {"rel_activity_pct": 0.65 * 100, "specific_activity": 51.24, "therm_resid_80c": 0.7046 * 100},
    "T376S": {"rel_activity_pct": 0.63 * 100, "specific_activity": 52.25, "therm_resid_80c": 0.7374 * 100},
    "WT": {"rel_activity_pct": 1.00 * 100, "specific_activity": 100.00, "therm_resid_80c": 0.28 * 100},
}

# Batch 1 一轮突变体 - 二次反馈 (from Excel Sheet2, authoritative)
batch1_round2 = {
    "P236T": {"rel_activity_pct": 50.71, "therm_resid_80c": 48.54},
    "P236Q": {"rel_activity_pct": 45.40, "therm_resid_80c": 53.57},
    "K293S": {"rel_activity_pct": 26.22, "therm_resid_80c": 89.97},
    "T332S": {"rel_activity_pct": 50.76, "therm_resid_80c": 73.00},
    "N340D": {"rel_activity_pct": 62.97, "therm_resid_80c": 63.00},
    "P380T": {"rel_activity_pct": 34.21, "therm_resid_80c": 88.67},
    "E240S": {"rel_activity_pct": 75.06, "therm_resid_80c": 48.41},
    "I356L": {"rel_activity_pct": 53.11, "therm_resid_80c": 71.69},
    "F361L": {"rel_activity_pct": 58.12, "therm_resid_80c": 72.55},
    "T376S": {"rel_activity_pct": 57.62, "therm_resid_80c": 67.73},
    "WT": {"rel_activity_pct": 100.00, "therm_resid_80c": 29.47},
}

# Batch 2 二轮突变体 (from Image2)
batch2 = {
    "WT": {"rel_activity_pct": 100.00, "therm_resid_80c": 49.50},
    "T32A": {"rel_activity_pct": 103.20, "therm_resid_80c": 43.85},
    "S60T": {"rel_activity_pct": 104.20, "therm_resid_80c": 41.30},
    "E103Q": {"rel_activity_pct": 93.10, "therm_resid_80c": 44.80},
    "W124F": {"rel_activity_pct": 97.72, "therm_resid_80c": 60.90},
    "L174I": {"rel_activity_pct": 88.80, "therm_resid_80c": 55.80},
    "T191K": {"rel_activity_pct": 107.50, "therm_resid_80c": 41.30},
    "K212R": {"rel_activity_pct": 103.40, "therm_resid_80c": 41.10},
    "A215T": {"rel_activity_pct": 106.50, "therm_resid_80c": 48.00},
    "S272A": {"rel_activity_pct": 127.30, "therm_resid_80c": 40.90},
    "P338T": {"rel_activity_pct": 142.20, "therm_resid_80c": 27.70},
}

# Batch 1 二次反馈 - 详细Sheet1 (raw, includes 比活力)
batch1_round2_detail = {
    "P236T": {"rel_activity_pct": 0.507120 * 100, "specific_activity": 0.41424 * 100, "therm_resid_80c": 0.507553 * 100, "therm_resid_80c_2": 0.485376 * 100},
    "P236Q": {"rel_activity_pct": 0.453961 * 100, "specific_activity": 0.357923 * 100, "therm_resid_80c": 0.555362 * 100, "therm_resid_80c_2": 0.535731 * 100},
    "WT": {"rel_activity_pct": 1.000000 * 100, "specific_activity": 1.00 * 100, "therm_resid_80c": 0.309345 * 100, "therm_resid_80c_2": 0.294672 * 100},
    "T332S": {"rel_activity_pct": 0.507608 * 100, "specific_activity": 0.535217 * 100, "therm_resid_80c": 0.5000 * 100, "therm_resid_80c_2": 0.621900 * 100},
    "N340D": {"rel_activity_pct": 0.629724 * 100, "specific_activity": 0.589448 * 100, "therm_resid_80c": 0.538924 * 100, "therm_resid_80c_2": 0.565812 * 100},
    "P380T": {"rel_activity_pct": 0.342090 * 100, "specific_activity": 0.36418 * 100, "therm_resid_80c": 0.485681 * 100, "therm_resid_80c_2": 0.686191 * 100},
    "E240S": {"rel_activity_pct": 0.750554 * 100, "specific_activity": 0.841108 * 100, "therm_resid_80c": 0.302225 * 100, "therm_resid_80c_2": 0.393163 * 100},
    "K293S": {"rel_activity_pct": 0.262244 * 100, "specific_activity": 0.204489 * 100, "therm_resid_80c": 0.923233 * 100, "therm_resid_80c_2": 0.899667 * 100},
    "I356L": {"rel_activity_pct": 0.531058 * 100, "specific_activity": 0.462116 * 100, "therm_resid_80c": 0.456446 * 100, "therm_resid_80c_2": 0.586673 * 100},
    "F361L": {"rel_activity_pct": 0.581217 * 100, "specific_activity": 0.512434 * 100, "therm_resid_80c": 0.445012 * 100, "therm_resid_80c_2": 0.574806 * 100},
    "T376S": {"rel_activity_pct": 0.576249 * 100, "specific_activity": 0.522497 * 100, "therm_resid_80c": 0.473035 * 100, "therm_resid_80c_2": 0.605218 * 100},
}

# ===========================
# 2. Build sample registry and batch-control mapping
# ===========================

samples = []
sample_id_counter = 1

def add_samples(batch_data, batch_id, batch_name, experiment_round, is_b2=False):
    global sample_id_counter
    for variant in batch_data.keys():
        sample_id = f"s{sample_id_counter:03d}"
        samples.append({
            "sample_id": sample_id,
            "batch_id": batch_id,
            "batch_name": batch_name,
            "variant_name": variant,
            "is_control": 1 if variant == "WT" else 0,
            "experiment_round": experiment_round,
            "assay_person": "上交大数据",
            "replicate_status": "single",
            "confidence_tier": "B" if is_b2 else "A",
            "analysis_use_level": "primary",
            "source_file": "上交大数据一轮两次数据集.xlsx" if not is_b2 else "上交大数据一次复反馈.png",
            "source_location": f"{batch_name}/{experiment_round}",
        })
        sample_id_counter += 1

add_samples(batch1_round1, "batch_1", "一轮突变体", "一次反馈", is_b2=False)
add_samples(batch1_round2, "batch_1", "一轮突变体", "二次反馈", is_b2=False)
add_samples(batch2, "batch_2", "二轮突变体", "一次反馈", is_b2=True)

sample_df = pd.DataFrame(samples)

# Build control mapping
sample_df["control_sample_id"] = sample_df.apply(
    lambda row: sample_df[(sample_df["batch_id"] == row["batch_id"]) & (sample_df["is_control"] == 1) & (sample_df["experiment_round"] == row["experiment_round"])]["sample_id"].values[0],
    axis=1
)

sample_df["control_batch_id"] = sample_df["batch_id"]

# 05_样本与批次对应表
sample_df_out = sample_df[[
    "sample_id", "batch_id", "batch_name", "variant_name", "is_control",
    "control_sample_id", "control_batch_id", "assay_person", "experiment_round",
    "replicate_status", "confidence_tier", "analysis_use_level"
]]
sample_df_out.to_csv(out_dir / "05_样本与批次对应表.csv", index=False, encoding="utf-8-sig")

# 06_批次与对照映射表
batch_control = []
for batch_id in sample_df["batch_id"].unique():
    batch_name = sample_df[sample_df["batch_id"] == batch_id]["batch_name"].iloc[0]
    for exp_round in sample_df[sample_df["batch_id"] == batch_id]["experiment_round"].unique():
        ctrl = sample_df[(sample_df["batch_id"] == batch_id) & (sample_df["is_control"] == 1) & (sample_df["experiment_round"] == exp_round)].iloc[0]
        batch_control.append({
            "batch_id": batch_id,
            "batch_name": batch_name,
            "experiment_round": exp_round,
            "control_sample_id": ctrl["sample_id"],
            "control_variant_name": ctrl["variant_name"],
            "source_file": ctrl["source_file"],
            "source_location": ctrl["source_location"],
            "confidence_tier": ctrl["confidence_tier"],
        })

batch_control_df = pd.DataFrame(batch_control)
batch_control_df.to_csv(out_dir / "06_批次与对照映射表.csv", index=False, encoding="utf-8-sig")

print("05_样本与批次对应表.csv written")
print("06_批次与对照映射表.csv written")

# ===========================
# 3. Build raw measurement fact table
# ===========================

measurements = []
measurement_id_counter = 1

metric_defs = {
    "rel_activity_pct": {"metric_name": "酶活相对百分比", "metric_code": "rel_activity_pct", "metric_group": "酶活", "unit_original": "%", "unit_standardized": "%"},
    "specific_activity": {"metric_name": "比活力", "metric_code": "specific_activity", "metric_group": "酶活", "unit_original": "U/mg", "unit_standardized": "U/mg"},
    "therm_resid_80c": {"metric_name": "80°C，3min耐温性", "metric_code": "therm_resid_80c", "metric_group": "热稳定性", "unit_original": "%", "unit_standardized": "%"},
    "therm_resid_80c_2": {"metric_name": "80°C，3min耐温性_复测", "metric_code": "therm_resid_80c_2", "metric_group": "热稳定性", "unit_original": "%", "unit_standardized": "%"},
}

def add_measurements(batch_data, batch_id, experiment_round, metric_keys):
    global measurement_id_counter
    for variant, vals in batch_data.items():
        sample_row = sample_df[(sample_df["batch_id"] == batch_id) & (sample_df["variant_name"] == variant) & (sample_df["experiment_round"] == experiment_round)].iloc[0]
        for mk in metric_keys:
            if mk not in vals:
                continue
            md = metric_defs[mk]
            measurements.append({
                "measurement_id": f"m{measurement_id_counter:03d}",
                "sample_id": sample_row["sample_id"],
                "batch_id": batch_id,
                "variant_name": variant,
                "source_file": sample_row["source_file"],
                "source_location": sample_row["source_location"],
                "assay_person": sample_row["assay_person"],
                "experiment_round": experiment_round,
                "replicate_status": "single",
                "confidence_tier": sample_row["confidence_tier"],
                "metric_name": md["metric_name"],
                "metric_code": md["metric_code"],
                "metric_group": md["metric_group"],
                "condition_name": "80°C,3min" if md["metric_group"] == "热稳定性" else "标准反应条件",
                "raw_value_text": str(vals[mk]),
                "raw_value_numeric": vals[mk],
                "unit_original": md["unit_original"],
                "unit_standardized": md["unit_standardized"],
                "control_compare_scope": "within_batch_round",
            })
            measurement_id_counter += 1

add_measurements(batch1_round1, "batch_1", "一次反馈", ["rel_activity_pct", "specific_activity", "therm_resid_80c"])
add_measurements(batch1_round2, "batch_1", "二次反馈", ["rel_activity_pct", "therm_resid_80c"])
add_measurements(batch1_round2_detail, "batch_1", "二次反馈", ["specific_activity", "therm_resid_80c_2"])
add_measurements(batch2, "batch_2", "一次反馈", ["rel_activity_pct", "therm_resid_80c"])

measurement_df = pd.DataFrame(measurements)
measurement_df.to_csv(out_dir / "04_原始测量事实表.csv", index=False, encoding="utf-8-sig")
print("04_原始测量事实表.csv written")

# ===========================
# 4. Build derived comparison table
# ===========================

derived = []
derived_id_counter = 1

primary_metrics = ["rel_activity_pct", "therm_resid_80c"]

for _, m in measurement_df.iterrows():
    if m["metric_code"] not in primary_metrics:
        continue
    sample_row = sample_df[sample_df["sample_id"] == m["sample_id"]].iloc[0]
    control_sample_id = sample_row["control_sample_id"]
    control_measurement = measurement_df[
        (measurement_df["sample_id"] == control_sample_id) &
        (measurement_df["metric_code"] == m["metric_code"]) &
        (measurement_df["experiment_round"] == m["experiment_round"])
    ]
    if control_measurement.empty:
        control_measurement = measurement_df[
            (measurement_df["sample_id"] == control_sample_id) &
            (measurement_df["metric_code"] == m["metric_code"])
        ]
    if control_measurement.empty:
        continue
    ctrl = control_measurement.iloc[0]
    raw = m["raw_value_numeric"]
    ctrl_val = ctrl["raw_value_numeric"]
    ratio = raw / ctrl_val if ctrl_val != 0 else None
    delta = raw - ctrl_val
    pct_change = (raw - ctrl_val) / ctrl_val * 100 if ctrl_val != 0 else None

    direction = "neutral"
    if m["metric_group"] == "酶活":
        if ratio and ratio > 1.1:
            direction = "up"
        elif ratio and ratio < 0.9:
            direction = "down"
    elif m["metric_group"] == "热稳定性":
        if ratio and ratio > 1.1:
            direction = "up"
        elif ratio and ratio < 0.9:
            direction = "down"

    derived.append({
        "derived_id": f"d{derived_id_counter:03d}",
        "measurement_id": m["measurement_id"],
        "sample_id": m["sample_id"],
        "batch_id": m["batch_id"],
        "experiment_round": m["experiment_round"],
        "control_sample_id": control_sample_id,
        "metric_name": m["metric_name"],
        "raw_value_numeric": raw,
        "control_value_numeric": ctrl_val,
        "vs_control_ratio": round(ratio, 4) if ratio is not None else None,
        "vs_control_delta": round(delta, 4),
        "vs_control_pct_change": round(pct_change, 2) if pct_change is not None else None,
        "compare_direction": direction,
        "rank_within_batch": None,
        "confidence_tier": m["confidence_tier"],
    })
    derived_id_counter += 1

derived_df = pd.DataFrame(derived)

for batch_id in derived_df["batch_id"].unique():
    for exp_round in derived_df[derived_df["batch_id"] == batch_id]["experiment_round"].unique():
        for metric in ["酶活相对百分比", "80°C，3min耐温性"]:
            mask = (derived_df["batch_id"] == batch_id) & (derived_df["experiment_round"] == exp_round) & (derived_df["metric_name"] == metric)
            derived_df.loc[mask, "rank_within_batch"] = derived_df.loc[mask, "raw_value_numeric"].rank(method="min", ascending=False).astype(int)

for i, row in derived_df.iterrows():
    sample = sample_df[sample_df["sample_id"] == row["sample_id"]].iloc[0]
    if sample["is_control"] == 1:
        derived_df.at[i, "rank_within_batch"] = None

ranked_derived = derived_df[[
    "derived_id", "measurement_id", "sample_id", "batch_id", "experiment_round", "control_sample_id",
    "metric_name", "raw_value_numeric", "control_value_numeric", "vs_control_ratio",
    "vs_control_delta", "vs_control_pct_change", "compare_direction", "rank_within_batch", "confidence_tier"
]]
ranked_derived.to_csv(out_dir / "03_相对对照派生分析表.csv", index=False, encoding="utf-8-sig")
print("03_相对对照派生分析表.csv written")

# ===========================
# 5. Build per-measurement judgement table
# ===========================

judgements = []
judgement_id_counter = 1

for _, d in derived_df.iterrows():
    sample = sample_df[sample_df["sample_id"] == d["sample_id"]].iloc[0]
    variant = sample["variant_name"]
    metric = d["metric_name"]
    ratio = d["vs_control_ratio"]
    pct_change = d["vs_control_pct_change"]

    if sample["is_control"] == 1:
        effect = "control_baseline"
        confounding = "no"
        basis = "本批次对照样本"
        priority = "none"
    elif metric == "酶活相对百分比":
        if ratio is None:
            effect = "uncertain"
            confounding = "unknown"
            basis = "缺少对照值"
            priority = "medium"
        elif ratio > 1.2:
            effect = "positive_enhanced"
            confounding = "no"
            basis = f"酶活较WT提升 {pct_change:.1f}%"
            priority = "low"
        elif ratio > 1.05:
            effect = "positive_mild"
            confounding = "no"
            basis = f"酶活较WT略升 {pct_change:.1f}%"
            priority = "low"
        elif ratio < 0.3:
            effect = "confirmed_loss"
            confounding = "no"
            basis = f"酶活较WT大幅下降 {pct_change:.1f}%"
            priority = "low"
        elif ratio < 0.9:
            effect = "suspected_negative"
            confounding = "possible_expression_variation"
            basis = f"酶活较WT下降 {pct_change:.1f}%，可能受表达水平/上样量/稀释倍数差异影响，需复测确认"
            priority = "medium"
        else:
            effect = "neutral"
            confounding = "no"
            basis = f"酶活与WT接近 ({pct_change:+.1f}%)"
            priority = "low"
    elif metric == "80°C，3min耐温性":
        if ratio is None:
            effect = "uncertain"
            confounding = "unknown"
            basis = "缺少对照值"
            priority = "medium"
        elif ratio > 1.2:
            effect = "positive_enhanced"
            confounding = "no"
            basis = f"80°C残率较WT显著提升 {pct_change:.1f}%"
            priority = "low"
        elif ratio > 1.05:
            effect = "positive_mild"
            confounding = "no"
            basis = f"80°C残率较WT略升 {pct_change:.1f}%"
            priority = "low"
        elif ratio < 0.7:
            effect = "suspected_negative"
            confounding = "possible_measurement_variation"
            basis = f"80°C残率较WT明显下降 {pct_change:.1f}%，建议复测确认"
            priority = "medium"
        else:
            effect = "neutral"
            confounding = "no"
            basis = f"80°C残率与WT接近 ({pct_change:+.1f}%)"
            priority = "low"
    else:
        effect = "uncertain"
        confounding = "unknown"
        basis = "未定义判读规则"
        priority = "medium"

    judgements.append({
        "judgement_id": f"j{judgement_id_counter:03d}",
        "measurement_id": d["measurement_id"],
        "effect_judgement": effect,
        "confounding_flag": confounding,
        "judgement_basis": basis,
        "review_priority": priority,
        "confidence_tier": d["confidence_tier"],
    })
    judgement_id_counter += 1

judgement_df = pd.DataFrame(judgements)
judgement_df.to_csv(out_dir / "02_单条测量记录判读表.csv", index=False, encoding="utf-8-sig")
print("02_单条测量记录判读表.csv written")

# ===========================
# 6. Build overall judgement summary
# ===========================

overall = []

for _, s in sample_df.iterrows():
    if s["is_control"] == 1:
        overall.append({
            "sample_id": s["sample_id"],
            "batch_id": s["batch_id"],
            "variant_name": s["variant_name"],
            "experiment_round": s["experiment_round"],
            "overall_effect_judgement": "control_baseline",
            "overall_confounding_flag": "no",
            "key_evidence": "本批次对照样本",
            "target_alignment": "control",
            "multi_round_potential": "none",
            "confidence_tier": s["confidence_tier"],
            "analysis_use_level": "control",
            "primary_analysis_recommended": "作为对照比较基准",
        })
        continue

    sample_derived = derived_df[derived_df["sample_id"] == s["sample_id"]]
    activity = sample_derived[sample_derived["metric_name"] == "酶活相对百分比"]
    therm = sample_derived[sample_derived["metric_name"] == "80°C，3min耐温性"]

    act_ratio = activity["vs_control_ratio"].values[0] if not activity.empty else None
    therm_ratio = therm["vs_control_ratio"].values[0] if not therm.empty else None
    act_pct = activity["vs_control_pct_change"].values[0] if not activity.empty else None
    therm_pct = therm["vs_control_pct_change"].values[0] if not therm.empty else None

    # Determine overall effect
    if act_ratio is not None and act_ratio > 1.2 and therm_ratio is not None and therm_ratio > 1.2:
        overall_effect = "positive_enhanced_activity_and_stability"
    elif act_ratio is not None and act_ratio > 1.2 and therm_ratio is not None and therm_ratio < 0.7:
        overall_effect = "positive_activity_negative_stability"
    elif act_ratio is not None and act_ratio < 0.3:
        overall_effect = "confirmed_loss"
    elif act_ratio is not None and act_ratio > 1.2:
        overall_effect = "positive_activity_only"
    elif therm_ratio is not None and therm_ratio > 1.2:
        overall_effect = "positive_stability_only"
    elif act_ratio is not None and act_ratio < 0.9 and therm_ratio is not None and therm_ratio < 0.9:
        overall_effect = "double_negative"
    else:
        overall_effect = "neutral_or_mild"

    # Key evidence summary
    evidence_parts = []
    if act_pct is not None:
        evidence_parts.append(f"酶活{act_pct:+.1f}%")
    if therm_pct is not None:
        evidence_parts.append(f"80°C残率{therm_pct:+.1f}%")
    key_evidence = "；".join(evidence_parts)

    # Confounding flag
    if act_ratio is not None and act_ratio < 0.9 and s["experiment_round"] in ["一次反馈"]:
        confounding = "possible_expression_variation"
    else:
        confounding = "no"

    # Target alignment: optimization target = stability up + activity up
    if act_ratio is not None and therm_ratio is not None:
        if act_ratio >= 1.05 and therm_ratio >= 1.05:
            target_alignment = "dual_positive"
        elif act_ratio < 0.9 and therm_ratio > 1.1:
            target_alignment = "stability_gain_activity_loss"
        elif act_ratio > 1.1 and therm_ratio < 0.9:
            target_alignment = "activity_gain_stability_loss"
        elif 0.9 <= act_ratio <= 1.1 and 0.9 <= therm_ratio <= 1.1:
            target_alignment = "neutral"
        else:
            target_alignment = "mild_change"
    else:
        target_alignment = "insufficient_data"

    # Multi-round potential: how useful as a building block for multi-round engineering
    if target_alignment == "dual_positive":
        multi_round_potential = "high"
    elif target_alignment == "stability_gain_activity_loss":
        if act_ratio is not None and act_ratio >= 0.7:
            multi_round_potential = "high"
        else:
            multi_round_potential = "medium"
    elif target_alignment == "activity_gain_stability_loss":
        if therm_ratio is not None and therm_ratio >= 0.85:
            multi_round_potential = "high"
        else:
            multi_round_potential = "medium"
    elif target_alignment == "mild_change":
        if therm_ratio is not None and therm_ratio > 1.05:
            multi_round_potential = "medium"
        elif act_ratio is not None and act_ratio > 1.05:
            multi_round_potential = "medium"
        else:
            multi_round_potential = "low"
    else:
        multi_round_potential = "low"

    overall.append({
        "sample_id": s["sample_id"],
        "batch_id": s["batch_id"],
        "variant_name": s["variant_name"],
        "experiment_round": s["experiment_round"],
        "overall_effect_judgement": overall_effect,
        "overall_confounding_flag": confounding,
        "key_evidence": key_evidence,
        "target_alignment": target_alignment,
        "multi_round_potential": multi_round_potential,
        "confidence_tier": s["confidence_tier"],
        "analysis_use_level": "primary" if s["experiment_round"] == "二次反馈" or s["batch_id"] == "batch_2" else "secondary",
        "primary_analysis_recommended": "纳入后续分析" if overall_effect.startswith("positive") or overall_effect == "neutral_or_mild" else "谨慎评估或复测",
    })

overall_df = pd.DataFrame(overall)
overall_df.to_csv(out_dir / "01_突变体总体判断总表.csv", index=False, encoding="utf-8-sig")
print("01_突变体总体判断总表.csv written")

# ===========================
# 7. Write usage MD
# ===========================

usage_md = f"""# 00_先看这个_数据库使用说明

## 数据集元数据

| 字段 | 值 |
|------|-----|
| 酶名称 | {METADATA["enzyme_name"]} |
| 表达体系 | {METADATA["expression_system"]} |
| 宿主菌 | {METADATA["host_organism"]} |
| 样品来源 | {METADATA["sample_source"]} |
| 测定方法 | {METADATA["assay_method"]} |
| 测定标准 | {METADATA["assay_standard"]} |
| 热稳定性条件 | {METADATA["thermal_stability_condition"]} |
| 优化目标 | {METADATA["optimization_target"]} |
| 数据来源 | {METADATA["data_source"]} |
| 处理时间 | {METADATA["processing_date"]} |

> **表达体系说明：** 本数据集为毕赤酵母分泌表达体系，酶分泌至发酵上清后直接稀释测定，**无细胞破碎步骤**。低酶活记录的混杂因素为表达水平/上样量/稀释倍数差异，非破碎效果。

## 数据包来源
- 原始数据：上交大数据一轮两次数据集.xlsx
- 图片补充：上交大数据二次反馈.png、上交大数据一次复反馈.png
- 处理时间：2026-07-13（初版），2026-07-14（修订版）
- 使用 skill：mutant-data-standardization

## 数据批次划分

| 批次ID | 批次名称 | 实验轮次 | 突变体数 | 对照 |
|--------|----------|----------|----------|------|
| batch_1 | 一轮突变体 | 一次反馈 | 11 | WT |
| batch_1 | 一轮突变体 | 二次反馈 | 11 | WT |
| batch_2 | 二轮突变体 | 一次反馈 | 11 | WT |

## 核心规则
1. **批次内对照优先**：所有突变体优先与本批次同轮次的 WT 对照比较。
2. **负向结果保留**：酶活下降、热稳定性下降等负向结果全部保留。
3. **低酶活谨慎判负**：一次反馈数据可能受表达水平/上样量/稀释倍数差异影响，不直接判定为位点负效应。
4. **置信度分层**：
   - A：明确复测/结构化数据（二轮突变体、一轮二次反馈）
   - B：单轮结构化数据（一次反馈）

## 优化目标对齐说明

本项目优化目标为**提高热稳定性 + 提高比活力**。单点突变难以同时实现双正，需多轮改造。01表中`target_alignment`字段标注各突变体与优化目标的对齐情况：

| target_alignment值 | 含义 | 多轮改造潜力 |
|---------------------|------|-------------|
| dual_positive | 酶活↑且稳定性↑（理想型） | high |
| stability_gain_activity_loss | 稳定性↑但酶活↓ | high（酶活保留≥70%）/ medium |
| activity_gain_stability_loss | 酶活↑但稳定性↓ | high（稳定性保留≥85%）/ medium |
| neutral | 两项均无显著变化 | low |
| mild_change | 有轻微变化但未达阈值 | low-medium |

## 文件说明

| 文件名 | 作用 | 关键字段 |
|--------|------|----------|
| 01_突变体总体判断总表.csv | 人看总览 | variant_name, overall_effect_judgement, target_alignment, multi_round_potential |
| 02_单条测量记录判读表.csv | 每条测量结论 | measurement_id, effect_judgement, confounding_flag |
| 03_相对对照派生分析表.csv | 相对对照计算 | vs_control_ratio, vs_control_delta, vs_control_pct_change |
| 04_原始测量事实表.csv | 最底层数据 | raw_value_numeric, metric_name, unit_standardized |
| 05_样本与批次对应表.csv | 样本注册 | sample_id, batch_id, variant_name, is_control |
| 06_批次与对照映射表.csv | 批次-对照 | control_sample_id, control_variant_name |

## confounding_flag含义

| flag值 | 含义 | 适用场景 |
|--------|------|---------|
| no | 无混杂因素 | 对照样本、明确正向/负向结果 |
| possible_expression_variation | 可能受表达水平/上样量/稀释倍数差异影响 | 低酶活记录（分泌表达体系） |
| possible_measurement_variation | 可能受测定操作差异影响 | 热稳定性下降记录 |
| unknown | 未知混杂因素 | 缺少对照值等异常情况 |

## 使用建议
- AI/IT 分析：以 `04_原始测量事实表.csv` + `03_相对对照派生分析表.csv` 为主。
- 人读摘要：先看 `01_突变体总体判断总表.csv`，关注 `target_alignment` 和 `multi_round_potential` 字段。
- 跨批次比较：只能比较相对对照的比值/差值，不能直接比较原始酶活值。

## 注意事项
- 一轮突变体二次反馈同时包含 Excel Sheet2（主数据）和 Sheet1 二次反馈列（原始详细数据）。
- 二轮突变体数据来自图片，置信度标记为 B；如需提升置信度，建议复测确认。
- Sheet1 中二次反馈的 extra 80°C 列（therm_resid_80c_2）作为复测/备用数据保留，不参与主分析。
- **本数据集为毕赤酵母分泌表达，无破碎步骤。低酶活混杂因素为表达水平差异，非破碎效果。**
"""

(out_dir / "00_先看这个_数据库使用说明.md").write_text(usage_md, encoding="utf-8")
print("00_先看这个_数据库使用说明.md written")

# ===========================
# 8. Write IT delivery instructions
# ===========================

it_md = f"""# 给IT的数据交付说明

## 数据集

{METADATA["enzyme_name"]}突变体酶活数据（标准化交付包），来源为上交大数据。

## 表达体系

- **酶名称：** {METADATA["enzyme_name"]}
- **表达体系：** {METADATA["expression_system"]}
- **宿主菌：** {METADATA["host_organism"]}
- **样品来源：** {METADATA["sample_source"]}
- **测定方法：** {METADATA["assay_method"]}（{METADATA["assay_standard"]}）
- **热稳定性条件：** {METADATA["thermal_stability_condition"]}
- **优化目标：** {METADATA["optimization_target"]}

> 本数据集为毕赤酵母分泌表达体系，酶分泌至发酵上清后直接稀释测定，无细胞破碎步骤。

## 文件清单

| 文件 | 格式 | 编码 | 行数 |
|------|------|------|------|
| 00_先看这个_数据库使用说明.md | Markdown | UTF-8 | - |
| 01_突变体总体判断总表.csv | CSV | UTF-8-BOM | 34 |
| 02_单条测量记录判读表.csv | CSV | UTF-8-BOM | 67 |
| 03_相对对照派生分析表.csv | CSV | UTF-8-BOM | 67 |
| 04_原始测量事实表.csv | CSV | UTF-8-BOM | ~100 |
| 05_样本与批次对应表.csv | CSV | UTF-8-BOM | 34 |
| 06_批次与对照映射表.csv | CSV | UTF-8-BOM | 4 |
| generate_standard_package.py | Python | UTF-8 | - |

## 表结构

### 01_突变体总体判断总表
- 主键：sample_id
- 粒度：每个样本一行（突变体×批次×轮次）
- 新增字段：target_alignment（优化目标对齐）、multi_round_potential（多轮改造潜力）

### 02_单条测量记录判读表
- 主键：judgement_id
- 外键：measurement_id → 04.measurement_id
- confounding_flag值域：no / possible_expression_variation / possible_measurement_variation / unknown

### 03_相对对照派生分析表
- 主键：derived_id
- 外键：measurement_id → 04.measurement_id
- 计算字段：vs_control_ratio, vs_control_delta, vs_control_pct_change

### 04_原始测量事实表
- 主键：measurement_id
- 外键：sample_id → 05.sample_id
- metric_code值域：rel_activity_pct / specific_activity / therm_resid_80c / therm_resid_80c_2

### 05_样本与批次对应表
- 主键：sample_id
- 外键：batch_id → 06.batch_id

### 06_批次与对照映射表
- 主键：batch_id + experiment_round
- 每行记录一个批次×轮次的对照样本信息

## 数据质量提示

1. 所有CSV文件使用UTF-8-BOM编码，Excel可直接打开。
2. confidence_tier字段标注数据置信度：A=结构化复测数据，B=单轮/图片数据。
3. confounding_flag标注混杂因素类型。毕赤酵母分泌表达体系中，低酶活记录标注为possible_expression_variation（表达水平差异），非破碎效果。
4. target_alignment字段标注突变体与优化目标（稳定性+比活力双提升）的对齐情况。
5. 二轮突变体（batch_2）数据来自图片截图估计值，置信度B级。

## 生成脚本

`generate_standard_package.py`为完整生成脚本，包含所有原始数据和处理逻辑。修改输出路径后可重新运行生成全部文件。
"""

(out_dir / "给IT的数据交付说明.md").write_text(it_md, encoding="utf-8")
print("给IT的数据交付说明.md written")

print(f"\nAll files generated in: {out_dir}")
