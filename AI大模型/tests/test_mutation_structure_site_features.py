import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_mutation_structure_site_features.py"
SPEC = importlib.util.spec_from_file_location("site_features", SCRIPT)
site_features = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(site_features)


class MutationStructureSiteFeatureTests(unittest.TestCase):
    def test_build_feature_uses_mapped_node_and_marks_claim_gate(self):
        candidate = {
            "candidate_id": "c1", "mapping_status": "deterministic_input_candidate",
            "record_id": "stability:1", "structure_id": "1ABC", "selected_chain_id": "A",
            "pdb_author_residue_number": 10, "wild_type": "A", "mutant": "V",
            "structure_context_scope": "near_full_length_context",
        }
        graph = {
            "structure_id": "1ABC", "selected_chain_id": "A", "neighbor_cutoff_angstrom": 8.0,
            "nodes": [
                {"node_id": 0, "chain_id": "A", "author_residue_number": "10", "residue_name": "ALA"},
                {"node_id": 1, "chain_id": "A", "author_residue_number": "11", "residue_name": "GLY"},
            ],
            "edges": [{"source": 0, "target": 1, "distance_angstrom": 4.0}],
        }
        row = site_features.build_feature(candidate, graph)
        self.assertEqual(1, row["neighbor_count"])
        self.assertEqual(4.0, row["mean_neighbor_distance_angstrom"])
        self.assertFalse(row["safe_for_model_claim"])

    def test_blocked_mapping_does_not_produce_feature(self):
        self.assertIsNone(site_features.build_feature({"mapping_status": "blocked"}, {}))

    def test_pdb_neighborhood_uses_author_numbering_and_selected_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.pdb"
            path.write_text(
                "ATOM      1  CA  ALA A  10       0.000   0.000   0.000  1.00 10.00           C\n"
                "ATOM      2  CA  GLY A  11       4.000   0.000   0.000  1.00 10.00           C\n"
                "ATOM      3  CA  SER B  10       1.000   0.000   0.000  1.00 10.00           C\n"
            )
            values = site_features.pdb_neighborhood(path, "A", 10, 8.0)
        self.assertEqual([4.0], values)


if __name__ == "__main__":
    unittest.main()
