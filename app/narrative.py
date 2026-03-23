"""
Narrative generation module.
Each section has a tailored LLM prompt and writer function.
Sections are skipped when their input data is None.
"""

import json
import logging
from typing import Optional

from app.llm_client import llm_client
from app.models import AgentOutputBundle, NarrativeSections

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts per section
# ---------------------------------------------------------------------------

SYSTEM_PROMPTS = {
    "data_overview": (
        "You are a professional data analyst writing a report for business stakeholders. "
        "Write in clear, non-technical language. Avoid jargon. "
        "Focus on what the data represents and its quality/completeness."
    ),
    "sql_findings": (
        "You are a senior data analyst writing the SQL findings section of an enterprise report. "
        "Describe query results, identify patterns, and explain business implications. "
        "Use specific numbers when available. Write 2-3 concise paragraphs."
    ),
    "ml_insights": (
        "You are a machine learning expert writing for a business audience. "
        "Explain what the model discovered, its accuracy and key metrics, "
        "and recommend concrete business actions based on the findings."
    ),
    "nlp_section": (
        "You are a text analytics specialist writing the NLP insights section. "
        "Describe sentiment patterns, key themes, entity frequencies, and "
        "what these text patterns mean for the business."
    ),
    "executive_summary": (
        "You are a C-suite advisor writing an executive summary. "
        "Lead with the single most impactful finding. Be concise and actionable. "
        "Limit to exactly 150 words. No bullet points — write flowing prose."
    ),
}

# ---------------------------------------------------------------------------
# User prompt builders
# ---------------------------------------------------------------------------


def _build_data_overview_prompt(context_summary: dict) -> str:
    return (
        "Write a 2-paragraph non-technical description of the following dataset "
        "structure and quality assessment. Describe what the data contains, "
        "its size, and any quality issues noted.\n\n"
        f"Dataset Information:\n{json.dumps(context_summary, indent=2, default=str)}"
    )


def _build_sql_findings_prompt(sql_results: list[dict]) -> str:
    results_str = json.dumps(sql_results[:10], indent=2, default=str)  # cap at 10
    return (
        "Write 2-3 paragraphs analyzing the following SQL query results. "
        "Identify patterns, notable values, and business implications.\n\n"
        f"Query Results:\n{results_str}"
    )


def _build_ml_insights_prompt(ml_results: dict) -> str:
    return (
        "Write 2-3 paragraphs about the following machine learning results. "
        "Explain what the model found, its performance metrics, feature importance, "
        "and what specific actions the business should take based on these findings.\n\n"
        f"ML Results:\n{json.dumps(ml_results, indent=2, default=str)}"
    )


def _build_nlp_section_prompt(nlp_insights: dict) -> str:
    return (
        "Write 2-3 paragraphs about the following NLP analysis results. "
        "Describe sentiment distributions, key themes discovered, important entities, "
        "and what these text patterns reveal about the business context.\n\n"
        f"NLP Insights:\n{json.dumps(nlp_insights, indent=2, default=str)}"
    )


def _build_executive_summary_prompt(sections: dict[str, str]) -> str:
    combined = "\n\n".join(
        f"### {name.replace('_', ' ').title()}\n{text}"
        for name, text in sections.items()
        if text
    )
    return (
        "Write a 150-word executive summary for a C-suite audience. "
        "Lead with the most impactful finding from the analysis below. "
        "Be concise, data-driven, and actionable.\n\n"
        f"Report Sections:\n{combined}"
    )


# ---------------------------------------------------------------------------
# Section writers
# ---------------------------------------------------------------------------


async def write_data_overview(context_summary: Optional[dict]) -> Optional[str]:
    """Generate data overview narrative. Returns None if no data."""
    if context_summary is None:
        logger.info("Skipping data_overview — no context_summary provided")
        return None

    prompt = _build_data_overview_prompt(context_summary)
    return await llm_client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPTS["data_overview"],
        max_tokens=800,
    )


async def write_sql_findings(sql_results: Optional[list[dict]]) -> Optional[str]:
    """Generate SQL findings narrative. Returns None if no data."""
    if not sql_results:
        logger.info("Skipping sql_findings — no sql_results provided")
        return None

    prompt = _build_sql_findings_prompt(sql_results)
    return await llm_client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPTS["sql_findings"],
        max_tokens=1000,
    )


async def write_ml_insights(ml_results: Optional[dict]) -> Optional[str]:
    """Generate ML insights narrative. Returns None if no data."""
    if ml_results is None:
        logger.info("Skipping ml_insights — no ml_results provided")
        return None

    prompt = _build_ml_insights_prompt(ml_results)
    return await llm_client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPTS["ml_insights"],
        max_tokens=1000,
    )


async def write_nlp_section(nlp_insights: Optional[dict]) -> Optional[str]:
    """Generate NLP section narrative. Returns None if no data."""
    if nlp_insights is None:
        logger.info("Skipping nlp_section — no nlp_insights provided")
        return None

    prompt = _build_nlp_section_prompt(nlp_insights)
    return await llm_client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPTS["nlp_section"],
        max_tokens=1000,
    )


async def write_executive_summary(sections: dict[str, str]) -> Optional[str]:
    """Generate executive summary from all completed sections."""
    active_sections = {k: v for k, v in sections.items() if v}
    if not active_sections:
        logger.warning("No sections available for executive summary")
        return None

    prompt = _build_executive_summary_prompt(active_sections)
    return await llm_client.generate(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPTS["executive_summary"],
        max_tokens=500,
    )


async def generate_all_narratives(bundle: AgentOutputBundle) -> NarrativeSections:
    """Generate all narrative sections from an agent output bundle."""

    # Generate individual sections (each call is independent)
    data_overview = await write_data_overview(bundle.context_summary)
    sql_findings = await write_sql_findings(bundle.sql_results)
    ml_insights = await write_ml_insights(bundle.ml_results)
    nlp_section = await write_nlp_section(bundle.nlp_insights)

    # Executive summary uses all generated sections
    section_texts = {
        "data_overview": data_overview,
        "sql_findings": sql_findings,
        "ml_insights": ml_insights,
        "nlp_section": nlp_section,
    }
    executive_summary = await write_executive_summary(section_texts)

    return NarrativeSections(
        data_overview=data_overview,
        sql_findings=sql_findings,
        ml_insights=ml_insights,
        nlp_section=nlp_section,
        executive_summary=executive_summary,
    )
