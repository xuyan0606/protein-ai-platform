"""Bounded enclosed van der Waals voids; no energetic/ligand-pocket claims."""
from __future__ import annotations

import math
from collections import deque


def detect_enclosed_cavities(atoms, *, spacing=1.0, minimum_volume=15.0, max_grid_points=1200000):
    result = {'method':'enclosed_vdw_grid_v1', 'spacing_angstrom':spacing,
              'minimum_volume_angstrom3':minimum_volume, 'mutant_geometry_validated':False,
              'cavities':[], 'limitations':['Grid-resolution dependent enclosed voids only; open pockets are exterior.',
                  'No solvent probe dilation, mutant rotamer optimization, or energetic validation.']}
    if not atoms:
        return {**result, 'status':'blocked', 'reason':'no_heavy_atoms'}
    if not isinstance(spacing,(int,float)) or not math.isfinite(spacing) or not .5 <= spacing <= 2.:
        return {**result, 'status':'blocked', 'reason':'invalid_grid_spacing'}
    points = [a['coordinates'] for a in atoms]
    if any(len(p)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in p) for p in points):
        return {**result, 'status':'blocked', 'reason':'invalid_atom_coordinates'}
    origin = [math.floor(min(p[k] for p in points)-4.) for k in range(3)]
    shape = [math.ceil((max(p[k] for p in points)+4.-origin[k])/spacing)+1 for k in range(3)]
    nx,ny,nz = shape
    size = nx*ny*nz
    result['grid_points'] = size
    if size > max_grid_points:
        return {**result,'status':'blocked','reason':'cavity_grid_budget_exceeded'}
    grid = bytearray(size)
    yz = ny*nz
    radii = {'C':1.70,'N':1.55,'O':1.52,'S':1.80,'P':1.80}
    buckets = {}
    for atom in atoms:
        xyz = atom['coordinates']
        radius = radii.get(atom.get('element'),1.80)
        cell=tuple(math.floor(x/4.) for x in xyz)
        buckets.setdefault(cell,[]).append(atom)
        spans=[range(max(0,math.ceil((xyz[k]-radius-origin[k])/spacing)),
                     min(shape[k]-1,math.floor((xyz[k]+radius-origin[k])/spacing))+1) for k in range(3)]
        for i in spans[0]:
            for j in spans[1]:
                for k in spans[2]:
                    if sum((origin[a]+v*spacing-xyz[a])**2 for a,v in enumerate((i,j,k))) <= radius*radius:
                        grid[i*yz+j*nz+k]=1
    # Padding guarantees index zero is exterior. Flood through face neighbours.
    def neighbours(index):
        i,rem=divmod(index,yz)
        j,k=divmod(rem,nz)
        if i>0: yield index-yz
        if i+1<nx: yield index+yz
        if j>0: yield index-nz
        if j+1<ny: yield index+nz
        if k>0: yield index-1
        if k+1<nz: yield index+1
    queue=deque([0])
    grid[0]=2
    while queue:
        for n in neighbours(queue.popleft()):
            if grid[n]==0:
                grid[n]=2
                queue.append(n)
    for seed in range(size):
        if grid[seed]:
            continue
        queue=deque([seed])
        grid[seed]=3
        component=[]
        while queue:
            index=queue.popleft()
            component.append(index)
            for n in neighbours(index):
                if grid[n]==0:
                    grid[n]=3
                    queue.append(n)
        volume=len(component)*spacing**3
        if volume <= minimum_volume:
            continue
        centres=[]
        lining=set()
        for index in component:
            i,rem=divmod(index,yz)
            j,k=divmod(rem,nz)
            xyz=tuple(origin[a]+v*spacing for a,v in enumerate((i,j,k)))
            centres.append(xyz)
            cell=tuple(math.floor(x/4.) for x in xyz)
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for dz in (-1,0,1):
                        for atom in buckets.get((cell[0]+dx,cell[1]+dy,cell[2]+dz),[]):
                            if math.dist(xyz,atom['coordinates'])<=4. and 'residue_number' in atom:
                                lining.add((atom['chain_id'],atom['residue_number'],atom.get('insertion_code') or None))
        result['cavities'].append({'cavity_id':f'void_{len(result["cavities"])+1}',
            'volume_angstrom3':round(volume,3), 'voxel_count':len(component),
            'centroid_angstrom':[round(sum(p[k] for p in centres)/len(centres),3) for k in range(3)],
            'lining_residue_keys':[list(key) for key in sorted(lining,key=str)]})
    result['cavities'].sort(key=lambda c:(-c['volume_angstrom3'],c['cavity_id']))
    return {**result,'status':'completed'}
