"""Celery background tasks for asynchronous document ingestion and vectorization."""

import asyncio
from pathlib import Path

import structlog

from contractiq.config import get_settings
from contractiq.db.connection import _create_async_engine
from contractiq.pipeline.celery_app import celery_app
from contractiq.pipeline.embedder import EmbeddingService
from contractiq.pipeline.ingestion import IngestionPipeline

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def ingest_document_task(self, file_path_str: str, document_id_str: str | None = None) -> dict:
    """Background task processing and vectorizing an uploaded contract."""
    file_path = Path(file_path_str)
    settings = get_settings()

    async def _async_run() -> dict:
        engine = _create_async_engine()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_maker = async_sessionmaker(engine, expire_on_commit=False)

        async with session_maker() as session:
            embedder = EmbeddingService(settings)
            pipeline = IngestionPipeline(session, embedder, settings)

            logger.info("Celery worker starting document ingestion", file=file_path.name)
            doc = await pipeline.ingest_file(file_path)

            return {
                "document_id": str(doc.id),
                "filename": doc.filename,
                "status": doc.processing_status,
                "page_count": doc.page_count,
            }

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_async_run())
        loop.close()
        return result
    except Exception as exc:
        logger.error("Celery ingestion task failed", error=str(exc), file=file_path_str)
        raise self.retry(exc=exc) from exc


@celery_app.task
def ingest_directory_task(directory_path_str: str) -> dict:
    """Background task processing a directory of contract files."""
    dir_path = Path(directory_path_str)
    files = (
        list(dir_path.glob("*.pdf")) + list(dir_path.glob("*.docx")) + list(dir_path.glob("*.txt"))
    )

    dispatched = []
    for f in files:
        task = ingest_document_task.delay(str(f))
        dispatched.append({"file": f.name, "task_id": task.id})

    return {
        "directory": directory_path_str,
        "files_count": len(files),
        "tasks": dispatched,
    }
