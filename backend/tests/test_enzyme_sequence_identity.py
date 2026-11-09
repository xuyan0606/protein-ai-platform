"""External identity lookup must verify WT and positions before transferring sites."""
import httpx
import pytest

from app.tools.enzyme_sequence_identity import enzyme_sequence_identity
from app.tools.enzyme_identity_profile import enzyme_identity_profile

SEQ = 'ACDEFGHIKLMNPQRSTVWY'


def transport(monkeypatch, *, mismatch=False, offline=False):
    calls = []
    async def handle(request):
        calls.append(str(request.url))
        if offline:
            raise httpx.ConnectError('offline', request=request)
        if 'search.rcsb.org' in str(request.url):
            return httpx.Response(200, json={'result_set': [{'identifier': '1ABC_1', 'score': 1}]})
        if 'data.rcsb.org' in str(request.url):
            return httpx.Response(200, json={'rcsb_polymer_entity_container_identifiers': {
                'reference_sequence_identifiers': [{'database_name': 'UniProt', 'database_accession': 'P12345'}]}})
        if 'rest.uniprot.org' in str(request.url):
            return httpx.Response(200, json={'entryType': 'UniProtKB reviewed (Swiss-Prot)',
                'sequence': {'value': 'MM'+('V'+SEQ[1:] if mismatch else SEQ)+'KK'},
                'proteinDescription': {'recommendedName': {'fullName': {'value': 'Test hydrolase'}}},
                'features': [{'type': 'Active site', 'description': 'Catalytic acid',
                    'location': {'start': {'value': 5}, 'end': {'value': 5}},
                    'evidences': [{'evidenceCode': 'ECO:0000269'}]}]})
        if 'ebi.ac.uk' in str(request.url):
            return httpx.Response(200, json={'results': [{'metadata': {'accession': 'IPR000001', 'name': 'Test family', 'type': 'family'},
                'proteins': [{'entry_protein_locations': [{'fragments': [{'start': 1, 'end': 24}]}]}]}]})
        raise AssertionError(str(request.url))
    original = httpx.AsyncClient
    def client(*args, **kwargs):
        kwargs['transport'] = httpx.MockTransport(handle)
        return original(*args, **kwargs)
    monkeypatch.setattr(httpx, 'AsyncClient', client)
    return calls


@pytest.mark.asyncio
async def test_sequence_search_finds_reference_and_projects_exact_subsequence_only(monkeypatch):
    calls = transport(monkeypatch)
    r = await enzyme_sequence_identity(SEQ)
    assert r['sequence_mapping']['reference_start'] == 3
    residues = r['evidence_bundle']['catalytic_sites']['curated_sites'][0]['residues']
    assert residues[0]['position'] == 3 and residues[0]['residue'] == 'D'
    profile = enzyme_identity_profile(SEQ, evidence_bundle=r['evidence_bundle'])
    assert 3 in profile['protected_positions']
    assert not any('blast' in url.lower() for url in calls)


@pytest.mark.asyncio
async def test_similar_reference_never_supplies_input_site_numbers(monkeypatch):
    transport(monkeypatch, mismatch=True)
    r = await enzyme_sequence_identity(SEQ)
    assert not r['evidence_bundle']
    assert any('not transferred' in x for x in r['limitations'])


@pytest.mark.asyncio
async def test_unavailable_reference_keeps_exploration_available(monkeypatch):
    transport(monkeypatch, offline=True)
    r = await enzyme_sequence_identity(SEQ)
    assert r['status'] == 'partial' and not r['evidence_bundle']
    assert r['evidence_level'].startswith('research_only')
