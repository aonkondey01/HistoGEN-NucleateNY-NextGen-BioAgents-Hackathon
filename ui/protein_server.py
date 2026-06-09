#!/usr/bin/env python3
"""HistoGen UI server — static files + Biohub protein structure proxy."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

UI_DIR = Path(__file__).resolve().parent
REPO_ROOT = UI_DIR.parent
DATA_DIR = REPO_ROOT / "data"
DEMO_DIR = REPO_ROOT / "demo"
load_dotenv(UI_DIR / ".env")

from cohort_figures import has_cohort_figures, list_figures, match_figure
from patient_data import GENE_COLORS, get_patient, load_representative_patients, nearest_patients
from phoenix_data import bundle_manifest, get_expression, has_phoenix_bundle
from protein_cache import (
    list_demo_genes,
    load_cached_structure,
    marker_for_gene,
    normalize_gene_query,
)

BIOHUB_BASE = "https://biohub.ai/esm/protein/api/v1alpha1"
UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
BIOHUB_API_KEY = os.getenv("BIOHUB_API_KEY", "").strip()
USE_PROTEIN_CACHE = os.getenv("USE_PROTEIN_CACHE", "1").strip().lower() not in {"0", "false", "no"}

app = FastAPI(title="HistoGen UI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def biohub_headers() -> dict[str, str]:
    if not BIOHUB_API_KEY:
        return {}
    return {"Authorization": f"Bearer {BIOHUB_API_KEY}"}


def md5_sequence(sequence: str) -> str:
    return hashlib.md5(sequence.upper().encode()).hexdigest()


async def resolve_gene_symbol(gene: str, organism_id: int = 9606) -> dict:
    query = f"(gene_exact:{gene}) AND (organism_id:{organism_id}) AND (reviewed:true)"
    params = {
        "query": query,
        "fields": "accession,sequence,protein_name,gene_names,organism_name",
        "format": "json",
        "size": 1,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(UNIPROT_SEARCH, params=params)
        resp.raise_for_status()
        data = resp.json()
    results = data.get("results") or []
    if not results:
        raise HTTPException(status_code=404, detail=f"No UniProt entry for gene {gene!r}")
    row = results[0]
    sequence = row["sequence"]["value"]
    return {
        "gene": gene.upper(),
        "accession": row["primaryAccession"],
        "protein_name": row.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value")
        or row.get("uniProtkbId", gene),
        "sequence_length": len(sequence),
        "organism": (row.get("organism") or {}).get("scientificName", "Homo sapiens"),
        "protein_hash": md5_sequence(sequence),
    }


async def fetch_biohub_protein(protein_hash: str, topk_features: int = 8) -> dict:
    url = f"{BIOHUB_BASE}/proteins/{protein_hash}"
    params = {"topk_features": topk_features, "fold_on_miss": True}
    async with httpx.AsyncClient(timeout=120.0, headers=biohub_headers()) as client:
        resp = await client.get(url, params=params)
        if resp.status_code == 401:
            raise HTTPException(
                status_code=502,
                detail="Biohub rejected API key — check BIOHUB_API_KEY in ui/.env",
            )
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Protein not found in ESM Atlas")
        resp.raise_for_status()
        return resp.json()


def format_structure_response(
    gene: str,
    uniprot: dict,
    atlas: dict,
    *,
    cached: bool = False,
    gigatime_channel: str | None = None,
) -> dict:
    features = []
    for feat in atlas.get("sae_features") or []:
        features.append(
            {
                "label": feat.get("label") or f"Feature {feat.get('feature_index')}",
                "description": feat.get("description"),
                "feature_index": feat.get("feature_index"),
            }
        )

    source = "ESM Atlas · Biohub Platform"
    if cached:
        source = "ESM Atlas · Biohub Platform (demo cache)"

    payload = {
        "gene": gene.upper(),
        "accession": uniprot["accession"],
        "protein_name": uniprot["protein_name"],
        "organism": uniprot["organism"],
        "sequence_length": uniprot["sequence_length"],
        "protein_hash": uniprot["protein_hash"],
        "ptm": atlas.get("ptm"),
        "mean_plddt": atlas.get("mean_plddt"),
        "folded_on_demand": atlas.get("folded_on_demand"),
        "pdb": atlas.get("pdb"),
        "sae_features": features,
        "atlas_url": f"https://biohub.ai/esm/protein/atlas/protein/{uniprot['protein_hash']}",
        "source": source,
        "cached": cached,
    }
    if gigatime_channel:
        payload["gigatime_channel"] = gigatime_channel
    return payload


async def build_structure_payload(
    gene: str,
    *,
    topk_features: int = 8,
    prefer_cache: bool = True,
) -> dict:
    canonical = normalize_gene_query(gene)
    marker = marker_for_gene(canonical)
    gigatime_channel = marker["channel"] if marker else None

    if prefer_cache and USE_PROTEIN_CACHE:
        cached = load_cached_structure(canonical)
        if cached:
            cached = dict(cached)
            cached["cached"] = True
            if gigatime_channel:
                cached.setdefault("gigatime_channel", gigatime_channel)
            return cached

    uniprot = await resolve_gene_symbol(canonical)
    atlas = await fetch_biohub_protein(uniprot["protein_hash"], topk_features)
    return format_structure_response(
        canonical,
        uniprot,
        atlas,
        cached=False,
        gigatime_channel=gigatime_channel,
    )


@app.get("/api/protein/structure")
async def protein_structure(
    gene: str = Query(..., min_length=1, max_length=32, pattern=r"^[A-Za-z0-9-]+$"),
    topk_features: int = Query(8, ge=1, le=20),
):
    """Resolve a gene symbol → UniProt sequence → Biohub ESM Atlas structure."""
    canonical = normalize_gene_query(gene)
    if not re.fullmatch(r"[A-Z0-9-]+", canonical):
        raise HTTPException(status_code=400, detail="Invalid gene symbol")

    return await build_structure_payload(canonical, topk_features=topk_features, prefer_cache=True)


@app.get("/api/protein/demo-genes")
async def protein_demo_genes():
    """List GigaTIME marker genes and whether a local demo cache file exists."""
    genes = list_demo_genes()
    cached_count = sum(1 for row in genes if row["cached"])
    return {
        "description": "GigaTIME virtual mIF markers with optional local Biohub structure cache",
        "cached_count": cached_count,
        "total": len(genes),
        "genes": genes,
    }


@app.get("/api/patients/cohort")
async def patients_cohort():
    """Return the 20 representative TCGA lung patients for the cluster graph."""
    try:
        return load_representative_patients()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/patients/{case_id}")
async def patient_detail(case_id: str):
    patient = get_patient(case_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Unknown patient case {case_id!r}")
    payload = {
        "patient": patient,
        "nearest": nearest_patients(case_id),
        "geneColors": GENE_COLORS,
        "phoenix": has_phoenix_bundle(case_id),
    }
    if payload["phoenix"]:
        payload["phoenixManifest"] = bundle_manifest(case_id)
    return payload


@app.get("/api/phoenix/{case_id}")
async def phoenix_bundle(case_id: str):
    if not has_phoenix_bundle(case_id):
        raise HTTPException(status_code=404, detail=f"No PHOENIX bundle for {case_id!r}")
    return bundle_manifest(case_id)


@app.get("/api/phoenix/{case_id}/expression")
async def phoenix_expression(
    case_id: str,
    gene: str = Query(..., min_length=1, max_length=32, pattern=r"^[A-Za-z0-9-]+$"),
):
    if not has_phoenix_bundle(case_id):
        raise HTTPException(status_code=404, detail=f"No PHOENIX bundle for {case_id!r}")
    try:
        return get_expression(case_id, gene.upper())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/agent/cohort-figures")
async def agent_cohort_figures():
    """Memorized cohort visual-report figures for the HistoGen Advisor demo."""
    if not has_cohort_figures():
        raise HTTPException(
            status_code=503,
            detail="Cohort visual report not found — checkout selected figures from representative-patient-selection branch",
        )
    return list_figures()


@app.get("/api/agent/cohort-figures/match")
async def agent_cohort_figure_match(q: str = Query(..., min_length=2, max_length=240)):
    if not has_cohort_figures():
        raise HTTPException(status_code=503, detail="Cohort visual report not available")
    result = match_figure(q)
    if not result:
        raise HTTPException(status_code=404, detail=f"No cohort figure matched {q!r}")
    return result


@app.get("/api/phoenix/{case_id}/heatmap")
async def phoenix_heatmap(case_id: str):
    if not has_phoenix_bundle(case_id):
        raise HTTPException(status_code=404, detail=f"No PHOENIX bundle for {case_id!r}")
    path = (
        DEMO_DIR
        / "data_package/per_patient"
        / case_id
        / "phoenix_spatial_heatmap.json"
    )
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Heatmap bundle missing")
    return json.loads(path.read_text(encoding="utf-8"))


if DEMO_DIR.is_dir():
    app.mount("/demo", StaticFiles(directory=str(DEMO_DIR)), name="demo")

if DATA_DIR.is_dir():
    app.mount("/data", StaticFiles(directory=str(DATA_DIR)), name="data")

app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")


if __name__ == "__main__":
    import uvicorn

    if BIOHUB_API_KEY:
        print("Biohub API key loaded from ui/.env")
    else:
        print("Warning: BIOHUB_API_KEY not set — copy ui/.env.example to ui/.env")
    if USE_PROTEIN_CACHE:
        cached = sum(1 for row in list_demo_genes() if row["cached"])
        print(f"Protein demo cache: {cached}/20 GigaTIME markers on disk")

    host = os.getenv("UI_HOST", "0.0.0.0")
    port = int(os.getenv("UI_PORT", "8080"))
    print(f"HistoGEN Advisor → http://{host}:{port}/")
    uvicorn.run("protein_server:app", host=host, port=port, reload=True)
