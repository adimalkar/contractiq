"""Contract comparison endpoint for clause-level diffing and alignment analysis."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.api.dependencies import get_db_session, get_embedder
from termnova.api.schemas import CompareRequest, CompareResponse
from termnova.comparison.report import ComparisonReportGenerator
from termnova.pipeline.embedder import EmbeddingService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/compare", tags=["Contract Comparison"])


@router.post("", response_model=CompareResponse)
async def compare_contracts(
    payload: CompareRequest,
    session: AsyncSession = Depends(get_db_session),
    embedder: EmbeddingService = Depends(get_embedder),
) -> CompareResponse:
    """Compare two contracts side-by-side with clause alignment and inline diffing."""
    if payload.document_a_id == payload.document_b_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot compare a document against itself. Please select two distinct documents.",
        )

    generator = ComparisonReportGenerator(session, embedder=embedder)
    try:
        report = await generator.compare_documents(payload.document_a_id, payload.document_b_id)
        return CompareResponse.model_validate(report)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve)) from ve
    except Exception as e:
        logger.error("Contract comparison failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while comparing contracts: {str(e)}",
        ) from e
