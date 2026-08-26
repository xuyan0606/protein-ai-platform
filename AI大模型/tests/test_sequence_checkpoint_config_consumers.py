import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import call, patch

import torch


SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def load_script(name):
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


CONSUMERS = [
    load_script("evaluate_sequence_mlm_checkpoint"),
    load_script("build_sequence_embedding_index"),
    load_script("export_sequence_embeddings"),
]


class SequenceCheckpointConfigConsumerTests(unittest.TestCase):
    class StubEncoder:
        def __init__(self, hidden_dim):
            self.hidden_dim = hidden_dim

        def load_state_dict(self, state_dict):
            return self

        def eval(self):
            return self

        def encode(self, ids):
            return torch.zeros(self.hidden_dim)

    def run_consumer(self, consumer, checkpoint):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            checkpoint_path = root / "checkpoint.pt"
            input_path = root / "input.fasta"
            input_dir = root / "inputs"
            output_path = root / "output.json"
            input_path.write_text(">record|source=test\nA\n", encoding="utf-8")
            input_dir.mkdir()
            (input_dir / "input.fasta").write_text(">record\nA\n", encoding="utf-8")
            torch.save(checkpoint, checkpoint_path)

            if consumer.__name__ == "build_sequence_embedding_index":
                input_arguments = ["--input-dir", str(input_dir)]
            else:
                input_arguments = ["--input", str(input_path)]
            argv = [consumer.__name__, *input_arguments, "--checkpoint", str(checkpoint_path), "--output", str(output_path)]

            def build_stub(vocab_size, hidden_dim, kernel_size, residual):
                return self.StubEncoder(hidden_dim)

            with patch.object(consumer, "build_encoder", side_effect=build_stub) as build_encoder:
                with patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
                    self.assertEqual(consumer.main(), 0)
            return build_encoder.call_args_list

    def test_consumer_mains_pass_explicit_checkpoint_model_config_to_encoder(self):
        checkpoint = {
            "vocab": ["A", "<mask>", "<pad>"],
            "state_dict": {},
            "config": {"hidden_dim": 64, "kernel_size": 5, "residual": True},
        }

        for consumer in CONSUMERS:
            with self.subTest(consumer=consumer.__name__):
                actual_calls = self.run_consumer(consumer, checkpoint)
                expected_call = call(3, hidden_dim=64, kernel_size=5, residual=True)
                expected_calls = [expected_call, expected_call] if consumer.__name__ == "evaluate_sequence_mlm_checkpoint" else [expected_call]
                self.assertEqual(actual_calls, expected_calls)

    def test_export_main_passes_legacy_checkpoint_defaults_to_encoder(self):
        checkpoint = {"vocab": ["A", "<mask>", "<pad>"], "state_dict": {}}

        self.assertEqual(
            self.run_consumer(CONSUMERS[2], checkpoint),
            [call(3, hidden_dim=32, kernel_size=3, residual=False)],
        )


if __name__ == "__main__":
    unittest.main()
