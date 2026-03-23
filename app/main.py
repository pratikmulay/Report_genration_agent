"""
Report Synthesis Agent — FastAPI main application.
Aggregates specialist agent outputs, generates narratives via LLM,
and exports enterprise-quality PDF/DOCX/PPTX documents.
"""

import logging
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import (
    AgentOutputBundle,
    ReportRequest,
    SummaryRequest,
    NarrativeSections,
    ReportMetadata,
    ReportResponse,
    HealthResponse,
)
from app.narrative import generate_all_narratives, write_executive_summary
from app.storage import get_storage
from app.cache import store_report_metadata, get_report_metadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Report Synthesis Agent",
    description=(
        "GEMRSLIZE Agent 07 — Final output layer. "
        "Aggregates structured results from all specialist agents, "
        "generates narrative sections via LLM, and exports enterprise-quality documents."
    ),
    version="1.0.0",
)

# Mount static files for local development
try:
    app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")
except Exception:
    logger.warning("Static files directory not found, skipping mount")


# ---------------------------------------------------------------------------
# Helper: export dispatch
# ---------------------------------------------------------------------------

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "html": "text/html",
}


async def _export_report(
    narratives: NarrativeSections,
    request: ReportRequest,
) -> ReportMetadata:
    """Generate the export file and store it."""
    report_id = str(uuid.uuid4())
    fmt = request.export_format
    bundle = request.bundle

    # Build kwargs shared across exporters
    export_kwargs = dict(
        narratives=narratives,
        charts=bundle.charts,
        branding=request.branding,
        report_style=request.report_style,
        user_query=bundle.user_query,
        include_charts=request.include_charts,
    )

    file_bytes: bytes | None = None
    content_type = CONTENT_TYPES.get(fmt, "application/json")

    if fmt == "pdf":
        from app.exporters.pdf_exporter import export_pdf
        file_bytes = export_pdf(**export_kwargs)

    elif fmt == "docx":
        from app.exporters.docx_exporter import export_docx
        file_bytes = export_docx(**export_kwargs, sql_results=bundle.sql_results)

    elif fmt == "pptx":
        from app.exporters.pptx_exporter import export_pptx
        file_bytes = export_pptx(**export_kwargs)

    elif fmt == "html":
        from app.exporters.pdf_exporter import _get_template_env
        from app.models import BrandingConfig
        env = _get_template_env()
        template = env.get_template("base_report.html.j2")
        brand = request.branding or BrandingConfig()
        chart_data = []
        if request.include_charts and bundle.charts:
            for c in bundle.charts:
                chart_data.append({
                    "title": c.get("title", "Chart"),
                    "image_base64": c.get("image_base64", c.get("png_base64", "")),
                    "description": c.get("description", ""),
                })
        html_str = template.render(
            narratives=narratives,
            charts=chart_data,
            branding=brand,
            report_style=request.report_style,
            user_query=bundle.user_query,
            include_charts=request.include_charts and bool(chart_data),
        )
        file_bytes = html_str.encode("utf-8")

    # Store file
    metadata = ReportMetadata(
        report_id=report_id,
        format=fmt,
        style=request.report_style,
        user_query=bundle.user_query,
        sections_generated=[
            s for s, v in narratives.model_dump().items() if v is not None
        ],
    )

    if file_bytes and fmt != "json":
        ext = fmt
        filename = f"report_{report_id}.{ext}"
        storage = get_storage()
        result = await storage.save(file_bytes, filename, content_type)
        metadata.file_path = result.get("file_path")
        metadata.download_url = result.get("download_url")
        metadata.content_base64 = result.get("content_base64")

    # Cache metadata
    await store_report_metadata(report_id, metadata)

    return metadata


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check():
    """Service health check."""
    return HealthResponse(
        llm_provider=settings.LLM_PROVIDER,
        storage_type=settings.STORAGE_TYPE,
    )


@app.post("/report", response_model=ReportResponse, tags=["report"])
async def generate_report(request: ReportRequest):
    """
    Generate a full analysis report from agent outputs.
    Writes narrative sections via LLM and exports to the requested format.
    """
    try:
        logger.info(
            f"Generating {request.report_style} report in {request.export_format} format"
        )

        # 1. Generate narratives
        narratives = await generate_all_narratives(request.bundle)

        # 2. If JSON-only, return narratives directly
        if request.export_format == "json":
            report_id = str(uuid.uuid4())
            metadata = ReportMetadata(
                report_id=report_id,
                format="json",
                style=request.report_style,
                user_query=request.bundle.user_query,
                sections_generated=[
                    s for s, v in narratives.model_dump().items() if v is not None
                ],
            )
            await store_report_metadata(report_id, metadata)

            return ReportResponse(
                report_id=report_id,
                format="json",
                style=request.report_style,
                created_at=metadata.created_at,
                narratives=narratives,
                metadata={"sections_generated": metadata.sections_generated},
            )

        # 3. Export to file format
        metadata = await _export_report(narratives, request)

        return ReportResponse(
            report_id=metadata.report_id,
            format=metadata.format,
            style=metadata.style,
            created_at=metadata.created_at,
            download_url=metadata.download_url,
            content_base64=metadata.content_base64,
            narratives=narratives,
            metadata={"sections_generated": metadata.sections_generated},
        )

    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@app.post("/summary", response_model=ReportResponse, tags=["report"])
async def generate_summary(request: SummaryRequest):
    """Generate executive summary only (short form)."""
    try:
        bundle = request.bundle
        section_texts = {}

        # Build minimal context from available data
        if bundle.context_summary:
            section_texts["data_overview"] = str(bundle.context_summary)
        if bundle.sql_results:
            section_texts["sql_findings"] = str(bundle.sql_results[:5])
        if bundle.ml_results:
            section_texts["ml_insights"] = str(bundle.ml_results)
        if bundle.nlp_insights:
            section_texts["nlp_section"] = str(bundle.nlp_insights)

        summary = await write_executive_summary(section_texts)

        report_id = str(uuid.uuid4())
        return ReportResponse(
            report_id=report_id,
            format="json",
            style="executive",
            created_at=datetime.utcnow(),
            narratives=NarrativeSections(executive_summary=summary),
        )
    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")


@app.post("/export/pdf", response_model=ReportResponse, tags=["export"])
async def export_pdf_endpoint(request: ReportRequest):
    """Export report to PDF format."""
    request.export_format = "pdf"
    return await generate_report(request)


@app.post("/export/docx", response_model=ReportResponse, tags=["export"])
async def export_docx_endpoint(request: ReportRequest):
    """Export report to DOCX format."""
    request.export_format = "docx"
    return await generate_report(request)


@app.post("/export/pptx", response_model=ReportResponse, tags=["export"])
async def export_pptx_endpoint(request: ReportRequest):
    """Export report to PowerPoint format."""
    request.export_format = "pptx"
    return await generate_report(request)


@app.get("/report/{report_id}", response_model=ReportResponse, tags=["report"])
async def get_report(report_id: str):
    """Retrieve a cached report by ID."""
    metadata = await get_report_metadata(report_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Report not found or expired")

    return ReportResponse(
        report_id=metadata.report_id,
        format=metadata.format,
        style=metadata.style,
        created_at=metadata.created_at,
        download_url=metadata.download_url,
        content_base64=metadata.content_base64,
    )
