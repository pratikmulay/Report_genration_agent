"""
Sample script to run the Report Synthesis Agent generator without needing an active LLM.
It mocks the `generate_all_narratives` call so it works out-of-the-box,
runs against the FastAPI server, and saves demo files.
"""

import asyncio
import base64
import json
import os
from pathlib import Path
import httpx
from datetime import datetime
from uvicorn import Server, Config

from app.models import ReportRequest, AgentOutputBundle, BrandingConfig

# Sample Data (same as test fixtures for brevity)
SAMPLE_BUNDLE = {
    "context_summary": {
        "dataset_name": "ecommerce_sales_2024",
        "rows": 50000,
        "quality_score": 0.95
    },
    "sql_results": [
        {"region": "North", "total_sales": 2500000, "growth_pct": 12.5},
        {"region": "South", "total_sales": 1800000, "growth_pct": -3.2},
    ],
    "ml_results": {
        "model_type": "Random Forest Classifier",
        "accuracy": 0.89,
        "predictions": {"churn_risk_high": 234, "churn_risk_low": 1266}
    },
    "nlp_insights": {
        "sentiment": {"positive": 0.45, "neutral": 0.35, "negative": 0.20},
        "key_themes": ["product quality", "delivery speed"]
    },
    "charts": [
        {
            "title": "Sales by Region",
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
            "description": "Regional sales comparison chart (White Pixel Demo)"
        }
    ],
    "user_query": "Analyze sales performance and predict churn risk",
    "analysis_timestamp": datetime.utcnow().isoformat()
}

BRANDING = {
    "company_name": "Global Analytics Partner",
    "primary_color": "#2563EB", # Blue
}


async def run_server():
    """Run uvicorn server in the background."""
    config = Config("app.main:app", host="127.0.0.1", port=8006, log_level="error")
    server = Server(config=config)
    
    # We mock the generate_all_narratives in the app so we don't need real API keys for the demo
    from app import main
    from app.models import NarrativeSections
    
    async def mock_generate(*args, **kwargs):
        return NarrativeSections(
            data_overview="The dataset 'ecommerce_sales_2024' contains 50,000 highly accurate records.",
            sql_findings="The North region outperformed others with $2.5M in sales and 12.5% growth.",
            ml_insights="Our model achieved 89% accuracy, identifying 234 high-risk churn customers.",
            nlp_section="Sentiment is largely positive (45%), focusing heavily on delivery speed.",
            executive_summary="Strong Northern growth offset by Southern decline. 234 high-risk churn customers identified alongside positive sentiment regarding delivery."
        )
    
    main.generate_all_narratives = mock_generate
    
    server_task = asyncio.create_task(server.serve())
    await asyncio.sleep(2)  # Give server time to start
    return server_task, server


async def run_demo():
    print("Starting local Report Synthesis Agent Server for Demo...")
    task, server = await run_server()
    
    print("\n--- Running Exports ---")
    
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8006", timeout=30.0) as client:
        
        # 1. JSON Report
        print("\n1. Generating JSON Report...")
        res = await client.post("/report", json={
            "bundle": SAMPLE_BUNDLE,
            "export_format": "json"
        })
        print(f"Status: {res.status_code}")
        print(f"JSON Response:\n{json.dumps(res.json(), indent=2)}")
        
        # 2. DOCX Report
        print("\n2. Generating DOCX Report...")
        res = await client.post("/export/docx", json={
            "bundle": SAMPLE_BUNDLE,
            "branding": BRANDING
        })
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            b64_content = data.get("content_base64")
            if b64_content:
                Path("demo_report.docx").write_bytes(base64.b64decode(b64_content))
                print(f"-> Saved DOCX to: {os.path.abspath('demo_report.docx')}")
                
        # 3. PPTX Report
        print("\n3. Generating PPTX Presentation...")
        res = await client.post("/export/pptx", json={
            "bundle": SAMPLE_BUNDLE,
            "branding": BRANDING
        })
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            b64_content = data.get("content_base64")
            if b64_content:
                Path("demo_presentation.pptx").write_bytes(base64.b64decode(b64_content))
                print(f"-> Saved PPTX to: {os.path.abspath('demo_presentation.pptx')}")
                
        # 4. HTML Generation (PDF backend relies on system libraries, so we generate HTML to verify template logic)
        print("\n4. Generating HTML Report (Template test)...")
        res = await client.post("/report", json={
            "bundle": SAMPLE_BUNDLE,
            "branding": BRANDING,
            "export_format": "html"
        })
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            b64_content = data.get("content_base64")
            if b64_content:
                Path("demo_report.html").write_bytes(base64.b64decode(b64_content))
                print(f"-> Saved HTML template render to: {os.path.abspath('demo_report.html')}")

    print("\nShutting down server...")
    server.should_exit = True
    await task
    print("Demo Complete!")

if __name__ == "__main__":
    asyncio.run(run_demo())
