"""Cavities require a bounded enclosed void, not low RSA alone."""
import importlib.util


def detect():
    assert importlib.util.find_spec('app.services.thermal_cavity'), 'enclosed cavity detector is missing'
    from app.services.thermal_cavity import detect_enclosed_cavities
    return detect_enclosed_cavities


def shell(open_face=False):
    rows=[]
    for x in range(-5,6):
        for y in range(-5,6):
            for z in range(-5,6):
                if max(abs(x),abs(y),abs(z)) != 5 or open_face and x==5:
                    continue
                rows.append({'coordinates':(float(x),float(y),float(z)), 'element':'C',
                             'chain_id':'A','residue_number':len(rows)+1,'insertion_code':None})
    return rows


def test_closed_shell_detects_actual_grid_volume_and_surrounding_residues():
    result=detect()(shell())
    assert result['status']=='completed'
    assert result['method']=='enclosed_vdw_grid_v1'
    assert result['cavities']
    assert result['cavities'][0]['volume_angstrom3']>15
    assert result['cavities'][0]['lining_residue_keys']
    assert result['mutant_geometry_validated'] is False


def test_open_shell_is_exterior_space_instead_of_a_cavity():
    result=detect()(shell(True))
    assert result['status']=='completed' and result['cavities']==[]


def test_large_bounds_are_explicitly_blocked_instead_of_allocating_unbounded_grid():
    atoms=[{'coordinates':(0.,0.,0.),'element':'C'},
           {'coordinates':(10000.,10000.,10000.),'element':'C'}]
    result=detect()(atoms,max_grid_points=1000)
    assert result['status']=='blocked' and result['reason']=='cavity_grid_budget_exceeded'
