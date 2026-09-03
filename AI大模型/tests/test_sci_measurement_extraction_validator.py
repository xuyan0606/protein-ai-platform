import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate_sci_measurement_extraction_templates.py"
SPEC = importlib.util.spec_from_file_location("sci_extract", SCRIPT)
module = importlib.util.module_from_spec(SPEC)


class SciExtractionValidatorTests(unittest.TestCase):
    def test_pending_template_is_not_training_ready(self):
        SPEC.loader.exec_module(module)
        row = {"pmcid":"PMC1","source_path":"x.xml","table_locator":"tbl1","construct":"","measurement_type":"","value":None,"unit":"","assay_condition":"","source_quote":"","reviewer":"","reviewed_at":"","status":"pending_human_extraction","training_import_allowed":False}
        result = module.validate_row(row, Path("/tmp"))
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
