"""Coordinate identities and declared connections, independent of reference IDs."""
from __future__ import annotations

import hashlib
import math
from typing import Any


def missing(value: Any) -> Any:
    return None if value is None or str(value).strip() in {'', '.', '?'} else value


def is_protein_atom(atom: dict, aa: dict) -> bool:
    """HETATM amino acids require polymer evidence, not just a residue name."""
    if atom['component_id'] not in aa:
        return False
    if atom['record'] == 'ATOM':
        return True
    if 'label_seq_id' in atom:
        return missing(atom.get('label_seq_id')) is not None
    return atom['component_id'] in {'MSE', 'SEC', 'PYL', 'HYP'}


def pdb_records(content: str) -> tuple[list[dict], list[int], list[dict]]:
    atoms, models, connections = [], [], []
    model = 1
    for line in content.splitlines():
        record = line[:6].strip()
        try:
            if record == 'MODEL':
                model = int(line[10:14])
                if model not in models:
                    models.append(model)
            elif record in {'ATOM', 'HETATM'}:
                xyz = tuple(float(line[a:b]) for a, b in ((30, 38), (38, 46), (46, 54)))
                if not all(math.isfinite(x) for x in xyz):
                    continue
                atoms.append({
                    'record': record, 'model_id': model, 'chain_id': line[21].strip() or '_',
                    'residue_number': int(line[22:26]), 'insertion_code': line[26].strip() or None,
                    'component_id': line[17:20].strip().upper(), 'atom_name': line[12:16].strip(),
                    'altloc': line[16].strip(), 'occupancy': float(line[54:60].strip() or 1),
                    'b_factor': float(line[60:66].strip() or 0), 'coordinates': xyz,
                    'element': line[76:78].strip().upper(),
                })
            elif record == 'LINK':
                partners = []
                for offset in (0, 30):
                    partners.append({
                        'chain_id': line[21+offset:22+offset].strip() or '_',
                        'residue_number': int(line[22+offset:26+offset]),
                        'insertion_code': line[26+offset:27+offset].strip() or None,
                        'component_id': line[17+offset:20+offset].strip(),
                        'atom_name': line[12+offset:16+offset].strip(),
                        'altloc': line[16+offset:17+offset].strip() or None,
                    })
                connections.append({'source_record': 'LINK', 'connection_type': 'unknown',
                    'partner_1': partners[0], 'partner_2': partners[1],
                    'symmetry_1': line[59:65].strip() or None, 'symmetry_2': line[66:72].strip() or None,
                    'distance_angstrom': float(line[73:78]) if line[73:78].strip() else None})
            elif record == 'SSBOND':
                partners = [{
                    'chain_id': line[c:c+1].strip() or '_', 'component_id': 'CYS', 'atom_name': 'SG',
                    'residue_number': int(line[a:b]), 'insertion_code': line[i:i+1].strip() or None,
                } for c, a, b, i in ((15, 17, 21, 21), (29, 31, 35, 35))]
                connections.append({'source_record': 'SSBOND', 'connection_type': 'disulf',
                    'partner_1': partners[0], 'partner_2': partners[1],
                    'symmetry_1': line[59:65].strip() or None, 'symmetry_2': line[66:72].strip() or None,
                    'distance_angstrom': float(line[73:78]) if line[73:78].strip() else None})
        except (IndexError, ValueError):
            continue
    return atoms, models or [1], connections


def cif_records(cif: dict) -> tuple[list[dict], list[int], list[dict]]:
    def column(key):
        raw = cif.get(key, [])
        return raw if isinstance(raw, list) else [raw]

    def cell(key, i, default=None):
        values = column(key)
        return missing(values[i]) if i < len(values) and missing(values[i]) is not None else default

    atoms, models, connections = [], [], []
    for i in range(len(column('_atom_site.id'))):
        try:
            model = int(cell('_atom_site.pdbx_PDB_model_num', i, 1))
            if model not in models:
                models.append(model)
            xyz = tuple(float(cell('_atom_site.Cartn_'+axis, i)) for axis in 'xyz')
            if not all(math.isfinite(x) for x in xyz):
                continue
            number = cell('_atom_site.auth_seq_id', i, cell('_atom_site.label_seq_id', i))
            atoms.append({
                'record': cell('_atom_site.group_PDB', i), 'model_id': model,
                'chain_id': cell('_atom_site.auth_asym_id', i, cell('_atom_site.label_asym_id', i, '_')),
                'residue_number': int(number) if number is not None else None,
                'insertion_code': cell('_atom_site.pdbx_PDB_ins_code', i),
                'component_id': cell('_atom_site.auth_comp_id', i, cell('_atom_site.label_comp_id', i, 'UNK')),
                'atom_name': cell('_atom_site.auth_atom_id', i, cell('_atom_site.label_atom_id', i, '')),
                'altloc': cell('_atom_site.label_alt_id', i, ''),
                'occupancy': float(cell('_atom_site.occupancy', i, 1)),
                'b_factor': float(cell('_atom_site.B_iso_or_equiv', i, 0)), 'coordinates': xyz,
                'label_asym_id': cell('_atom_site.label_asym_id', i),
                'label_seq_id': cell('_atom_site.label_seq_id', i),
                'entity_id': cell('_atom_site.label_entity_id', i),
                'element': cell('_atom_site.type_symbol', i),
            })
        except (TypeError, ValueError):
            continue
    for i in range(len(column('_struct_conn.id'))):
        # Keep malformed declarations auditable without discarding valid coordinates.
        invalid = None
        partners = []
        for n in (1, 2):
            prefix = f'_struct_conn.ptnr{n}_'
            number = cell(prefix+'auth_seq_id', i, cell(prefix+'label_seq_id', i))
            try:
                number = int(number) if number is not None else None
            except (TypeError, ValueError):
                invalid = 'Invalid struct_conn residue number'
                number = None
            partners.append({
                'chain_id': cell(prefix+'auth_asym_id', i, cell(prefix+'label_asym_id', i, '_')),
                'residue_number': number,
                'component_id': cell(prefix+'label_comp_id', i),
                'atom_name': cell(prefix+'label_atom_id', i),
                'insertion_code': cell(f'_struct_conn.pdbx_ptnr{n}_PDB_ins_code', i),
                'altloc': cell(f'_struct_conn.pdbx_ptnr{n}_label_alt_id', i),
                'label_asym_id': cell(prefix+'label_asym_id', i),
            })
        distance = cell('_struct_conn.pdbx_dist_value', i)
        try:
            distance = float(distance) if distance is not None else None
            if distance is not None and not math.isfinite(distance):
                raise ValueError('nonfinite')
        except (TypeError, ValueError):
            invalid = 'Invalid struct_conn distance'
            distance = None
        connections.append({'source_record': 'struct_conn', 'connection_id': cell('_struct_conn.id', i),
            'connection_type': 'unknown' if invalid else cell('_struct_conn.conn_type_id', i, 'unknown'),
            **({'validation_status': 'invalid', 'warning': invalid} if invalid else {}),
            'connection_role': cell('_struct_conn.pdbx_role', i),
            'partner_1': partners[0], 'partner_2': partners[1],
            'symmetry_1': cell('_struct_conn.ptnr1_symmetry', i), 'symmetry_2': cell('_struct_conn.ptnr2_symmetry', i),
            'distance_angstrom': distance})
    return atoms, models or [1], connections


def coordinate_summary(content: str, atoms: list[dict], models: list[int], connections: list[dict], aa: dict) -> dict:
    chains, components, other_polymers, seen, b_values, names = {}, {}, {}, set(), [], {}
    total_atoms = 0
    for atom in atoms:
        if atom['model_id'] != models[0] or atom['altloc'] not in {'', 'A'}:
            continue
        component = atom['component_id']
        if component in {'HOH', 'WAT', 'DOD'}:
            continue
        total_atoms += 1
        chain_id, number, insertion = atom['chain_id'], atom['residue_number'], atom['insertion_code']
        key = (chain_id, number, insertion, component, atom.get('label_asym_id'))
        if not is_protein_atom(atom, aa):
            target = other_polymers if atom['record'] == 'ATOM' or atom.get('label_seq_id') else components
            row = target.setdefault(key, {'component_id': component, 'chain_id': chain_id,
                'residue_number': number, 'insertion_code': insertion, 'atom_count': 0})
            row['atom_count'] += 1
            continue
        chain = chains.setdefault(chain_id, {'chain_id': chain_id, 'sequence': '', 'residue_count': 0,
            'atom_count': 0, 'residue_range': None, 'residues': [], 'zero_occupancy_atoms': 0})
        chain['atom_count'] += 1
        chain['zero_occupancy_atoms'] += atom['occupancy'] <= 0
        b_values.append(atom['b_factor'])
        names.setdefault(chain_id, set()).add(atom['atom_name'])
        if key not in seen:
            seen.add(key)
            chain['residue_count'] += 1
            chain['sequence'] += aa[component]
            chain['residues'].append({k: atom.get(k) for k in (
                'residue_number', 'insertion_code', 'component_id', 'label_asym_id', 'label_seq_id', 'entity_id')})
            chain['residues'][-1]['sequence_position'] = len(chain['residues'])
            if number is not None:
                old = chain['residue_range'] or [number, number]
                chain['residue_range'] = [min(old[0], number), max(old[1], number)]
    for cid, chain in chains.items():
        chain['ca_only'] = names[cid] == {'CA'}
    return {
        'content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
        'model_scope': {'selected_model': models[0], 'available_models': models, 'policy': 'first_model'},
        'conformer_policy': 'blank_or_A; alternate conformers are not combined or ensemble-averaged',
        'connections': connections, 'disulfide_count': sum(c['connection_type'] == 'disulf' for c in connections),
        'chains': sorted(chains.values(), key=lambda c: c['chain_id']),
        'nonpolymer_components': list(components.values()),
        'other_polymer_components': list(other_polymers.values()),
        'total_atoms': total_atoms, 'total_residues': sum(c['residue_count'] for c in chains.values()),
        'b_factor_stats': {'mean': round(sum(b_values)/len(b_values), 2), 'min': round(min(b_values), 2),
            'max': round(max(b_values), 2), 'atom_count': len(b_values)} if b_values else None,
        'b_factor_scope': 'protein_polymer_atoms_only; raw PDB temperature-factor column; interpretation depends on structure source' if b_values else None,
    }
