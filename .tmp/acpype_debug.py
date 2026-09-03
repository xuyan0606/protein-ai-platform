import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

import app.tools.ligand_preprocess as lp


async def main() -> None:
    sdf = Path("/workspace/Structure2D_COMPOUND_CID_5478883.sdf").read_text()
    gen = await lp._run_obabel_gen3d(sdf_text=sdf, job_id="debug", timeout_seconds=120, store_outputs=False)
    print("gen", gen.get("status"), gen.get("error"), gen.get("inspection", {}).get("inferred_dimension"))
    ligand = gen.get("_pipeline_sdf_text") or gen.get("output_sdf", {}).get("text") or sdf
    with tempfile.TemporaryDirectory(prefix="acpype-debug-") as tmp:
        workdir = Path(tmp)
        (workdir / "ligand_3d.sdf").write_text(ligand, encoding="utf-8")
        obabel = shutil.which("obabel")
        acpype = shutil.which("acpype") or "/opt/venv/bin/acpype"
        print("workdir", workdir, "obabel", obabel, "acpype", acpype)
        mol2 = subprocess.run(
            [obabel, "ligand_3d.sdf", "-O", "ligand.mol2", "--partialcharge", "gasteiger"],
            cwd=workdir,
            text=True,
            capture_output=True,
            check=False,
        )
        print("mol2 rc", mol2.returncode)
        print((mol2.stdout + mol2.stderr)[-1200:])
        res = subprocess.run(
            [acpype, "-i", "ligand.mol2", "-b", "ligand", "-c", "gas", "-n", "0", "-a", "gaff2", "-o", "gmx", "-d"],
            cwd=workdir,
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
        print("acpype rc", res.returncode)
        print("stdout<<<")
        print(res.stdout[-12000:])
        print("stderr<<<")
        print(res.stderr[-12000:])
        print("files", [str(path.relative_to(workdir)) for path in workdir.rglob("*")][:120])


asyncio.run(main())
