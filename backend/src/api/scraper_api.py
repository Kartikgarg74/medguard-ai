"""API routes for scraper control and status."""

from fastapi import APIRouter, BackgroundTasks

from src.orchestrator.pipeline import MedGuardPipeline

router = APIRouter(prefix="/api/scraper", tags=["scraper"])

# Singleton pipeline instance
_pipeline: MedGuardPipeline | None = None


def get_pipeline() -> MedGuardPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = MedGuardPipeline()
    return _pipeline


@router.post("/trigger")
async def trigger_scan(background_tasks: BackgroundTasks):
    """Trigger a full pipeline scan (runs in background)."""
    pipeline = get_pipeline()

    if pipeline.status.value in ["scraping", "checking", "reporting", "alerting"]:
        return {"error": "Pipeline already running", "status": pipeline.status.value}

    background_tasks.add_task(_run_pipeline, pipeline)
    return {"message": "Pipeline scan triggered", "status": "starting"}


async def _run_pipeline(pipeline: MedGuardPipeline):
    """Run pipeline in background."""
    await pipeline.run_full_scan()


@router.get("/status")
async def scraper_status():
    """Get current pipeline and agent status."""
    pipeline = get_pipeline()
    return pipeline.get_status()
