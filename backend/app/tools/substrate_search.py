"""Read-only PubChem substrate lookup with explicit evidence boundaries."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from app.tools.registry import ToolRegistry


PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"


async def substrate_search(query: str, namespace: str = "name", limit: int = 10) -> dict:
    value = " ".join(str(query or "").split())
    if not value:
        raise ValueError("MISSING_SUBSTRATE_QUERY: provide a name, SMILES, or InChIKey")
    if len(value) > 256:
        raise ValueError("INVALID_SUBSTRATE_QUERY: maximum length is 256 characters")
    if namespace not in {"name", "smiles", "inchikey"}:
        raise ValueError("UNSUPPORTED_SUBSTRATE_NAMESPACE: use name, smiles, or inchikey")
    if not 1 <= int(limit) <= 50:
        raise ValueError("INVALID_LIMIT: expected 1-50")

    property_url = (
        f"{PUBCHEM}/{'name' if namespace == 'name' else namespace}/"
        f"{quote(value, safe='')}/property/Title,IUPACName,CanonicalSMILES,InChIKey/JSON"
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(property_url)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "status": "blocked_substrate_database_unavailable",
            "query": value,
            "namespace": namespace,
            "results": [],
            "blocked_reason": f"PubChem lookup failed: {type(exc).__name__}",
        }

    properties = payload.get("PropertyTable", {}).get("Properties", [])[: int(limit)]
    results = [
        {
            "cid": item.get("CID"),
            "title": item.get("Title"),
            "iupac_name": item.get("IUPACName"),
            "canonical_smiles": item.get("ConnectivitySMILES") or item.get("CanonicalSMILES"),
            "inchikey": item.get("InChIKey"),
        }
        for item in properties
    ]
    return {
        "status": "completed_substrate_lookup",
        "database": "PubChem",
        "query": value,
        "namespace": namespace,
        "results": results,
        "evidence_level": "database_record",
        "scientific_boundary": "Compound identity records do not establish enzyme activity, Km, specificity, or assay compatibility.",
    }


ToolRegistry.register(
    name="substrate_search",
    description="Search PubChem for auditable substrate compound identity records; does not infer enzyme kinetics.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "namespace": {"type": "string", "enum": ["name", "smiles", "inchikey"], "default": "name"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
        },
        "required": ["query"],
    },
    handler=substrate_search,
    is_async=True,
    category="substrate",
    timeout_seconds=20,
)
