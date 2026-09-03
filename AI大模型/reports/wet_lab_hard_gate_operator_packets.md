# Wet-Lab Hard-Gate Operator Packets

Generated: 2026-09-03T07:33:45.129259+00:00

These packets organize manual wet-lab authorization work. They do not write decisions or labels.

## Summary

- Packet rows: 12
- Completion ready rows: 0
- Variants: {'D105N': 4, 'E331Q': 4, 'S265T': 4}
- Head counts: {'activity_risk': 9, 'stability': 3}
- Safe for model claim: false

## Packets

| order | variant | metric | head | ratio | priority | missing fields |
|---:|---|---|---|---:|---|---:|
| 1 | E331Q | 酸性保持率_pH4.8/pH6.0(%) | activity_risk | 1.4081632653061225 | critical_tradeoff_review | 11 |
| 2 | E331Q | 热稳定性_85C_3min(%) | stability | 0.6074766355140186 | critical_tradeoff_review | 11 |
| 3 | E331Q | pH6.0绝对酶活(U/mL) | activity_risk | 0.75696316262354 | critical_tradeoff_review | 11 |
| 4 | E331Q | pH4.8绝对酶活(U/mL) | activity_risk | 1.0731481481481482 | critical_tradeoff_review | 11 |
| 5 | D105N | pH4.8绝对酶活(U/mL) | activity_risk | 1.3944444444444444 | medium_mixed_benefit_review | 0 |
| 6 | D105N | 酸性保持率_pH4.8/pH6.0(%) | activity_risk | 1.2040816326530612 | medium_mixed_benefit_review | 0 |
| 7 | D105N | pH6.0绝对酶活(U/mL) | activity_risk | 1.1500449236298294 | medium_mixed_benefit_review | 0 |
| 8 | D105N | 热稳定性_85C_3min(%) | stability | 1.0467289719626167 | medium_mixed_benefit_review | 0 |
| 9 | S265T | 热稳定性_85C_3min(%) | stability | 0.7570093457943925 | standard_multi_property_review | 0 |
| 10 | S265T | 酸性保持率_pH4.8/pH6.0(%) | activity_risk | 1.0408163265306123 | standard_multi_property_review | 0 |
| 11 | S265T | pH6.0绝对酶活(U/mL) | activity_risk | 0.9613656783468104 | standard_multi_property_review | 0 |
| 12 | S265T | pH4.8绝对酶活(U/mL) | activity_risk | 1.0175925925925926 | standard_multi_property_review | 0 |

## Policy

Fail-closed wet-lab operator packets only. They do not write authorization decisions, preflight rows, apply-plan rows, experiment feedback records, head labels, training rows, model claims, deployments, syncs, or release readiness.
