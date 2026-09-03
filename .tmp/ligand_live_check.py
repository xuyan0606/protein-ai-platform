import asyncio, json
from pathlib import Path
import app.tools.ligand_preprocess as lp

sdf = Path('/workspace/Structure2D_COMPOUND_CID_5478883.sdf').read_text()
receptor = '''REMARK tiny receptor smoke\nATOM      1  C   REC A   1       0.000   0.000   0.000  0.00  0.00    +0.000 C \nEND\n'''

async def main():
    first = await lp.ligand_preprocess(
        sdf_data=sdf,
        receptor_pdbqt_data=receptor,
        pocket_center={'x':0,'y':0,'z':0},
        pocket_size={'x':20,'y':20,'z':20},
        stages=['preflight','generate_3d','prepare_pdbqt','vina_docking'],
        vina_exhaustiveness=1,
        vina_num_modes=1,
        store_outputs=False,
        timeout_seconds=120,
    )
    topo = await lp.ligand_preprocess(
        sdf_data=sdf,
        stages=['generate_3d','ligand_topology'],
        store_outputs=False,
        timeout_seconds=120,
    )
    print(json.dumps({
        'pipeline_status': first['status'],
        'pipeline_stages': {item['stage']: item['status'] for item in first['stage_results']},
        'docked_text': bool(next(item for item in first['stage_results'] if item['stage']=='vina_docking').get('output_pdbqt', {}).get('text')),
        'topology_status': topo['status'],
        'topology_stage': next(item for item in topo['stage_results'] if item['stage']=='ligand_topology')['status'],
        'topology_error_preview': next(item for item in topo['stage_results'] if item['stage']=='ligand_topology').get('error', '')[:220],
    }, ensure_ascii=False, indent=2, sort_keys=True))

asyncio.run(main())
