"""Remap a verified selected chain for sequence-indexed model inference."""
import hashlib


def model_pdb(sequence, pdb_data, chain_id):
    from app.services.thermostability_workflow import structure_context
    from app.services.structure_records import pdb_records, is_protein_atom
    from app.services.pdb_parser import _AA3TO1
    _,mapping,_,blockers=structure_context(sequence,pdb_data,chain_id,[],'unknown')
    if blockers or len(mapping)!=len(sequence):
        raise ValueError('complete_verified_structure_mapping_required')
    reverse={key:pos for pos,key in mapping.items()}
    atoms,models,_=pdb_records(pdb_data)
    lines=[]
    seen=set()
    for atom in atoms:
        key=(atom['chain_id'],atom['residue_number'],atom.get('insertion_code') or None)
        if key not in reverse or atom['model_id']!=models[0] or atom['occupancy']<=0 or atom['altloc'] not in {'','A'} or not is_protein_atom(atom,_AA3TO1):
            continue
        identity=(reverse[key],atom['atom_name'])
        if identity in seen:
            continue
        seen.add(identity)
        x,y,z=atom['coordinates']
        b=atom.get('b_factor') or 0.
        lines.append(f'ATOM  {len(lines)+1:5d} {atom["atom_name"]:^4} {atom["component_id"]:3} {chain_id}{reverse[key]:4d}    '
                     f'{x:8.3f}{y:8.3f}{z:8.3f}{atom["occupancy"]:6.2f}{b:6.2f}          {atom["element"]:>2}')
    data='\n'.join(lines)+'\nTER\nEND\n'
    return data, {'coordinate_mapping':[{'input_position':p,'model_position_0based':p-1,
        'author_chain_id':key[0],'author_residue_number':key[1],'author_insertion_code':key[2]}
        for p,key in sorted(mapping.items())], 'original_structure_sha256':hashlib.sha256(pdb_data.encode()).hexdigest(),
        'model_structure_sha256':hashlib.sha256(data.encode()).hexdigest(),
        'mapping_method':'verified_exact_sequence_selected_chain_contiguous_model_copy'}
