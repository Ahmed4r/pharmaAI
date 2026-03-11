"""
api.py  FastAPI backend for PharmaAI n8n integration.

Exposes three endpoints:
  POST /query        - RAG clinical query  -> StructuredClinicalResponse JSON
  POST /ocr          - Gemini OCR + safety -> structured dict
  POST /ocr/upload   - Multipart file upload variant of /ocr
  GET  /health       - liveness probe for n8n

Run:
  uvicorn api:app --host 0.0.0.0 --port 8000 --reload

n8n environment variables required:
  PHARMA_API_KEY              - optional bearer token guarding all endpoints
  GROQ_API_KEY                - Groq cloud LLM key
  TELEGRAM_CRITICAL_CHAT_ID  - Telegram chat id for MAJOR alerts
  TELEGRAM_STANDARD_CHAT_ID  - Telegram chat id for moderate/minor alerts
"""
from __future__ import annotations

import base64
import os
import re as _re
import traceback
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PharmaAI API",
    description="RAG + OCR clinical pharmacology backend for n8n orchestration.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production: list n8n host explicitly
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Optional API-key guard  (set PHARMA_API_KEY env var to enable)
# ---------------------------------------------------------------------------
_API_KEY = os.environ.get("PHARMA_API_KEY", "")


def _check_api_key(x_api_key: Optional[str] = Header(default=None)):
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header.")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    query: str = Field(..., description="Clinical question e.g. 'aspirin warfarin interaction'")
    image_url: Optional[str] = Field(
        default=None,
        description="Optional URL of a prescription image. OCR runs if provided.",
    )
    mode: Optional[str] = Field(
        default="cloud",
        description="cloud (Groq, default) or local (Ollama BioMistral)",
    )
    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq API key. Overrides GROQ_API_KEY env var.",
    )


class BnfSource(BaseModel):
    file: str
    page: int


class StructuredClinicalResponse(BaseModel):
    """Canonical structured output returned to n8n / mobile / Telegram."""
    query: str
    drug_name: list[str]                  # all generic drug names identified
    interaction_severity: str             # MAJOR | MODERATE | MINOR | NONE
    clinical_rationale_the_why: str       # pharmacological mechanism explanation
    bnf_source_page: list[BnfSource]      # BNF page citations
    full_markdown: str                    # full 4-section markdown for display
    confidence_pct: int                   # 0-100 RAG confidence
    alert_level: str                      # CRITICAL | WARNING | INFO | SAFE
    ocr_result: Optional[dict] = None     # populated when image_url supplied


class OcrRequest(BaseModel):
    image_url: Optional[str] = Field(default=None)
    image_base64: Optional[str] = Field(default=None)
    patient_weight_kg: Optional[float] = Field(default=0.0)
    groq_api_key: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Liveness probe used by n8n HTTP Request node."""
    from rag_engine import is_pdf_ready
    return {"status": "ok", "chromadb_ready": is_pdf_ready()}


@app.post(
    "/query",
    response_model=StructuredClinicalResponse,
    summary="Clinical RAG query -- returns structured pharmacology JSON",
    dependencies=[Depends(_check_api_key)],
)
async def query_endpoint(req: QueryRequest):
    """
    n8n Step 2 target.
    Returns StructuredClinicalResponse with: drug_name, interaction_severity,
    clinical_rationale_the_why, bnf_source_page, alert_level.
    """
    try:
        from chatbot import generate_response_structured
        result_dict = generate_response_structured(
            user_message=req.query,
            mode=req.mode or "cloud",
            groq_api_key=req.groq_api_key or os.environ.get("GROQ_API_KEY", ""),
        )

        # Convert bnf_source_page list[dict] -> list[BnfSource]
        result_dict["bnf_source_page"] = [
            BnfSource(file=s.get("file", "BNF80.pdf"), page=s.get("page", 0))
            for s in result_dict.get("bnf_source_page", [])
        ]

        response = StructuredClinicalResponse(**result_dict)

        # Optionally run OCR if image_url provided
        if req.image_url:
            try:
                async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                    img_resp = await client.get(req.image_url)
                    img_resp.raise_for_status()
                    img_bytes = img_resp.content
                from ocr import process_prescription_ocr, analyze_prescription_safety
                ocr_raw = process_prescription_ocr(img_bytes, filename="prescription.jpg")
                ocr_safety = analyze_prescription_safety(
                    parsed_meds=ocr_raw.get("parsed_meds", []),
                    patient=ocr_raw.get("patient", ""),
                    prescriber=ocr_raw.get("prescriber", ""),
                )
                response.ocr_result = {"ocr": ocr_raw, "safety": ocr_safety}
            except Exception as ocr_err:
                response.ocr_result = {"error": str(ocr_err)}

        return response

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/ocr",
    summary="Prescription OCR -- Gemini Vision + Groq safety analysis",
    dependencies=[Depends(_check_api_key)],
)
async def ocr_endpoint(req: OcrRequest):
    """Accepts image URL or base64 and returns OCR + safety analysis."""
    try:
        if req.image_url:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                r = await client.get(req.image_url)
                r.raise_for_status()
                img_bytes = r.content
        elif req.image_base64:
            img_bytes = base64.b64decode(req.image_base64)
        else:
            raise HTTPException(status_code=422, detail="Provide image_url or image_base64.")

        from ocr import process_prescription_ocr, analyze_prescription_safety
        ocr_raw = process_prescription_ocr(img_bytes, filename="prescription.jpg")
        safety = analyze_prescription_safety(
            parsed_meds=ocr_raw.get("parsed_meds", []),
            patient=ocr_raw.get("patient", ""),
            prescriber=ocr_raw.get("prescriber", ""),
            patient_weight_kg=req.patient_weight_kg or 0.0,
        )
        return {
            "ocr": ocr_raw,
            "safety": safety,
            "drug_names": [m.get("generic_name") or m.get("name") for m in ocr_raw.get("parsed_meds", [])],
            "has_major_interaction": any(
                i.get("severity", "").upper() == "MAJOR"
                for i in safety.get("interactions", [])
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@app.post(
    "/ocr/upload",
    summary="Prescription OCR via multipart file upload",
    dependencies=[Depends(_check_api_key)],
)
async def ocr_upload_endpoint(
    file: UploadFile = File(...),
    patient_weight_kg: float = 0.0,
    groq_api_key: Optional[str] = Header(default=None, alias="X-Groq-Key"),
):
    """Multipart upload variant of /ocr for when image URL is not available."""
    try:
        img_bytes = await file.read()
        from ocr import process_prescription_ocr, analyze_prescription_safety
        ocr_raw = process_prescription_ocr(img_bytes, filename=file.filename or "upload.jpg")
        safety = analyze_prescription_safety(
            parsed_meds=ocr_raw.get("parsed_meds", []),
            patient=ocr_raw.get("patient", ""),
            prescriber=ocr_raw.get("prescriber", ""),
            patient_weight_kg=patient_weight_kg,
        )
        return {
            "ocr": ocr_raw,
            "safety": safety,
            "drug_names": [m.get("generic_name") or m.get("name") for m in ocr_raw.get("parsed_meds", [])],
            "has_major_interaction": any(
                i.get("severity", "").upper() == "MAJOR"
                for i in safety.get("interactions", [])
            ),
        }
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))
