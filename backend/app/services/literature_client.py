"""Literature retrieval client — PubMed E-utilities + Europe PMC REST API.

Fetches paper metadata (title, authors, abstract, MeSH terms) for enzyme/protein
literature. Supports keyword search, PMID resolution, DOI resolution, and MeSH queries.

Rate limits:
  - PubMed without API key: 3 req/s
  - PubMed with NCBI_API_KEY: 10 req/s
  - Europe PMC: no key needed, generous limits
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPE_PMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
_RATE_LIMIT = 10 if NCBI_API_KEY else 3  # requests per second


@dataclass
class Paper:
    """Structured paper metadata."""

    pmid: str
    doi: str | None = None
    title: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    year: int | None = None
    abstract: str | None = None
    mesh_terms: list[str] = field(default_factory=list)
    citation_count: int | None = None
    source: str = "pubmed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pmid": self.pmid,
            "doi": self.doi,
            "title": self.title,
            "authors": self.authors,
            "journal": self.journal,
            "year": self.year,
            "abstract": self.abstract,
            "mesh_terms": self.mesh_terms,
            "citation_count": self.citation_count,
        }

    @property
    def short_citation(self) -> str:
        """Short citation for LLM prompt injection."""
        first_author = self.authors[0] if self.authors else "Unknown"
        return f"{first_author} et al. ({self.year or 'N/A'}). {self.title}. {self.journal}. PMID:{self.pmid}"


class LiteratureClient:
    """Async client for PubMed + Europe PMC literature search."""

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(_RATE_LIMIT)
        self._cache: dict[str, Paper] = {}  # simple in-memory cache

    async def _get(self, url: str, params: dict[str, Any]) -> httpx.Response:
        """Rate-limited GET request."""
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=30.0) as client:
                return await client.get(url, params=params)

    # ---- PubMed E-utilities ------------------------------------------------

    async def search_pubmed(self, query: str, max_results: int = 10) -> list[Paper]:
        """Search PubMed, return list of Paper objects."""
        params: dict[str, Any] = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }
        if NCBI_API_KEY:
            params["api_key"] = NCBI_API_KEY

        try:
            resp = await self._get(f"{PUBMED_BASE}/esearch.fcgi", params)
            data = resp.json()
            pmids: list[str] = data.get("esearchresult", {}).get("idlist", [])
            if not pmids:
                return []
            return await self.fetch_pubmed(pmids)
        except Exception:
            logger.exception("PubMed search failed for query: %s", query)
            return []

    async def fetch_pubmed(self, pmids: list[str]) -> list[Paper]:
        """Fetch full metadata for a list of PMIDs."""
        # Check cache first
        uncached = [p for p in pmids if p not in self._cache]
        cached = [self._cache[p] for p in pmids if p in self._cache]

        if uncached:
            params: dict[str, Any] = {
                "db": "pubmed",
                "id": ",".join(uncached),
                "rettype": "xml",
                "retmode": "xml",
            }
            if NCBI_API_KEY:
                params["api_key"] = NCBI_API_KEY

            try:
                resp = await self._get(f"{PUBMED_BASE}/efetch.fcgi", params)
                papers = self._parse_pubmed_xml(resp.text)
                for paper in papers:
                    self._cache[paper.pmid] = paper
                cached.extend(papers)
            except Exception:
                logger.exception("PubMed efetch failed for PMIDs: %s", uncached)

        # Return in original order
        result_map = {p.pmid: p for p in cached}
        return [result_map[p] for p in pmids if p in result_map]

    def _parse_pubmed_xml(self, xml_text: str) -> list[Paper]:
        """Parse PubMed efetch XML response."""
        papers: list[Paper] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            logger.exception("Failed to parse PubMed XML response")
            return papers

        for article in root.findall(".//PubmedArticle"):
            try:
                medline = article.find("MedlineCitation")
                if medline is None:
                    continue

                pmid_el = medline.find("PMID")
                if pmid_el is None or not pmid_el.text:
                    continue
                pmid = pmid_el.text

                art = medline.find("Article")
                if art is None:
                    continue

                # Title
                title_el = art.find("ArticleTitle")
                title = title_el.text if title_el is not None and title_el.text else ""

                # Journal
                journal_el = art.find("Journal/JournalIssue/Journal")
                journal = ""
                if journal_el is not None:
                    journal = journal_el.text or journal_el.get("ISOAbbreviation", "")

                # Year
                year = self._extract_year(art)

                # Authors
                authors = self._extract_authors(art)

                # Abstract
                abstract = self._extract_abstract(art)

                # DOI
                doi = self._extract_doi(article)

                # MeSH terms
                mesh_terms = self._extract_mesh_terms(medline)

                papers.append(
                    Paper(
                        pmid=pmid,
                        doi=doi,
                        title=title,
                        authors=authors,
                        journal=journal,
                        year=year,
                        abstract=abstract,
                        mesh_terms=mesh_terms,
                        source="pubmed",
                    )
                )
            except Exception:
                logger.debug("Failed to parse one PubMed article")
                continue

        return papers

    # ---- XML extraction helpers -------------------------------------------

    @staticmethod
    def _extract_year(art: ElementTree.Element) -> int | None:
        """Extract publication year from Article element."""
        pub_date = art.find("Journal/JournalIssue/PubDate")
        if pub_date is None:
            return None
        year_el = pub_date.find("Year")
        if year_el is not None and year_el.text:
            return int(year_el.text)
        medline_date = pub_date.find("MedlineDate")
        if medline_date is not None and medline_date.text:
            match = re.search(r"\d{4}", medline_date.text)
            if match:
                return int(match.group())
        return None

    @staticmethod
    def _extract_authors(art: ElementTree.Element) -> list[str]:
        """Extract author list from Article element."""
        authors: list[str] = []
        author_list = art.find("AuthorList")
        if author_list is not None:
            for author in author_list.findall("Author"):
                last = author.findtext("LastName", "")
                first = author.findtext("ForeName", "")
                if last:
                    authors.append(f"{last} {first}".strip())
        return authors

    @staticmethod
    def _extract_abstract(art: ElementTree.Element) -> str | None:
        """Extract abstract text from Article element."""
        abstract_el = art.find("Abstract/AbstractText")
        if abstract_el is None:
            return None
        # Some abstracts have structured children (Label + text segments)
        if abstract_el.text:
            return abstract_el.text
        text = ElementTree.tostring(abstract_el, encoding="unicode", method="text").strip()
        return text or None

    @staticmethod
    def _extract_doi(article: ElementTree.Element) -> str | None:
        """Extract DOI from ArticleIdList."""
        for aid in article.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                return aid.text
        return None

    @staticmethod
    def _extract_mesh_terms(medline: ElementTree.Element) -> list[str]:
        """Extract MeSH descriptor terms from MedlineCitation."""
        terms: list[str] = []
        for mesh in medline.findall("MeshHeadingList/MeshHeading/DescriptorName"):
            if mesh.text:
                terms.append(mesh.text)
        return terms

    # ---- Europe PMC -------------------------------------------------------

    async def search_europe_pmc(self, query: str, max_results: int = 10) -> list[Paper]:
        """Search Europe PMC (40M+ articles, free, no API key needed)."""
        params: dict[str, Any] = {
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": max_results,
            "sort": "RELEVANCE",
        }
        try:
            resp = await self._get(f"{EUROPE_PMC_BASE}/search", params)
            data = resp.json()
            results = data.get("resultList", {}).get("result", [])
            papers: list[Paper] = []
            for r in results:
                pmid = r.get("pmid", "")
                if not pmid:
                    continue
                papers.append(
                    Paper(
                        pmid=pmid,
                        doi=r.get("doi"),
                        title=r.get("title", ""),
                        authors=[
                            a.get("fullName", "")
                            for a in r.get("authorList", {}).get("author", [])
                        ],
                        journal=r.get("journalTitle", ""),
                        year=int(r["pubYear"]) if r.get("pubYear") else None,
                        abstract=r.get("abstractText"),
                        mesh_terms=[],  # Europe PMC doesn't return MeSH in basic search
                        citation_count=r.get("citedByCount"),
                        source="europe_pmc",
                    )
                )
            return papers
        except Exception:
            logger.exception("Europe PMC search failed for query: %s", query)
            return []

    # ---- Combined search --------------------------------------------------

    async def search_by_protein(
        self,
        protein_name: str,
        ec_number: str | None = None,
        max_results: int = 5,
    ) -> list[Paper]:
        """Search literature by protein name and optionally EC number.

        Constructs a targeted PubMed query using MeSH terms.
        Falls back to Europe PMC if PubMed returns nothing.
        """
        query_parts = [f'"{protein_name}"[Title/Abstract]']
        if ec_number:
            query_parts.append(f'OR "EC {ec_number}"[Title/Abstract]')
        query_parts.append(
            'AND ("enzyme"[MeSH Terms] OR "protein engineering"[Title/Abstract] '
            'OR "directed evolution"[Title/Abstract] OR "enzyme kinetics"[Title/Abstract])'
        )
        query = " ".join(query_parts)

        papers = await self.search_pubmed(query, max_results)
        if not papers:
            # Fallback to Europe PMC with simpler query
            eu_query = f'"{protein_name}" AND (enzyme OR "protein engineering")'
            if ec_number:
                eu_query += f' OR "EC {ec_number}"'
            papers = await self.search_europe_pmc(eu_query, max_results)

        return papers[:max_results]

    # ---- Resolution -------------------------------------------------------

    async def resolve_pmid(self, pmid: str) -> Paper | None:
        """Resolve a single PMID to full Paper metadata."""
        if pmid in self._cache:
            return self._cache[pmid]
        papers = await self.fetch_pubmed([pmid])
        return papers[0] if papers else None

    async def resolve_doi(self, doi: str) -> Paper | None:
        """Resolve a DOI to Paper metadata via Europe PMC."""
        try:
            resp = await self._get(
                f"{EUROPE_PMC_BASE}/search",
                {
                    "query": f'DOI:"{doi}"',
                    "format": "json",
                    "resultType": "core",
                    "pageSize": 1,
                },
            )
            data = resp.json()
            results = data.get("resultList", {}).get("result", [])
            if results:
                r = results[0]
                return Paper(
                    pmid=r.get("pmid", ""),
                    doi=doi,
                    title=r.get("title", ""),
                    authors=[
                        a.get("fullName", "")
                        for a in r.get("authorList", {}).get("author", [])
                    ],
                    journal=r.get("journalTitle", ""),
                    year=int(r["pubYear"]) if r.get("pubYear") else None,
                    abstract=r.get("abstractText"),
                    source="europe_pmc",
                )
        except Exception:
            logger.exception("DOI resolution failed: %s", doi)
        return None

    # ---- Formatting -------------------------------------------------------

    @staticmethod
    def format_citations(papers: list[Paper]) -> str:
        """Format papers as citation list for LLM prompt injection."""
        if not papers:
            return "No related literature found."

        lines: list[str] = []
        for i, p in enumerate(papers, 1):
            lines.append(f"{i}. {p.short_citation}")
            if p.abstract:
                # Truncate abstract to ~200 chars for prompt
                abstract_short = p.abstract[:200] + "..." if len(p.abstract) > 200 else p.abstract
                lines.append(f"   Abstract: {abstract_short}")
            lines.append("")
        return "\n".join(lines)


def parse_literature_ref(ref: str) -> tuple[str, str] | None:
    """Parse a literature_ref string into (type, id) tuple.

    Handles formats like:
    - "PMID:12345" → ("pmid", "12345")
    - "doi:10.1234/abc" → ("doi", "10.1234/abc")
    - "10.1234/abc" → ("doi", "10.1234/abc")
    - "12345" → ("pmid", "12345")
    """
    if not ref or not ref.strip():
        return None

    ref = ref.strip()

    # PMID:xxx
    if ref.upper().startswith("PMID:"):
        return ("pmid", ref[5:].strip())

    # doi:xxx or DOI:xxx
    if ref.lower().startswith("doi:"):
        return ("doi", ref[4:].strip())

    # Starts with 10. → DOI
    if ref.startswith("10."):
        return ("doi", ref)

    # Pure digits → PMID
    if ref.isdigit():
        return ("pmid", ref)

    return None
