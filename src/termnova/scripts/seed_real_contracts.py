"""Batch database seeder that parses, embeds, and indexes authentic commercial enterprise contracts into Termnova."""

import argparse
import asyncio
import json
from pathlib import Path

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from termnova.config import get_settings
from termnova.db.connection import AsyncSessionFactory
from termnova.db.models import Document
from termnova.pipeline.ingestion import IngestionPipeline

logger = structlog.get_logger(__name__)

CONTRACTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "contracts"


async def seed_real_contracts(
    contracts_dir: Path | None = None,
    limit: int | None = None,
    force_reindex: bool = False,
    session: AsyncSession | None = None,
) -> dict[str, int]:
    """Index real commercial contracts from the dataset directory into PostgreSQL."""
    target_dir = contracts_dir or CONTRACTS_DIR
    settings = get_settings()

    if not target_dir.exists():
        logger.warning("contracts_dir_not_found", path=str(target_dir))
        return {"total_found": 0, "indexed": 0, "skipped": 0, "failed": 0}

    # Gather PDF and text files
    pdf_files = sorted(list(target_dir.glob("*.pdf")))
    txt_files = sorted(list(target_dir.glob("*.txt")))
    all_files = pdf_files + txt_files

    if limit:
        all_files = all_files[:limit]

    logger.info("seeding_real_contracts_start", count=len(all_files), dir=str(target_dir))
    print(f"Starting ingestion of {len(all_files)} real enterprise agreements into Termnova...")

    manifest_map = {}
    manifest_path = target_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest_list = json.loads(manifest_path.read_text())
            for item in manifest_list:
                manifest_map[item.get("clean_filename")] = item
        except Exception:
            pass

    stats = {"total_found": len(all_files), "indexed": 0, "skipped": 0, "failed": 0}

    async def _ingest_with_session(db_session: AsyncSession):
        pipeline = IngestionPipeline(session=db_session, settings=settings)

        for idx, file_path in enumerate(all_files, 1):
            filename = file_path.name
            meta_hint = manifest_map.get(filename, {})
            print(
                f"[{idx}/{len(all_files)}] Ingesting {filename} ({file_path.stat().st_size // 1024} KB)..."
            )

            try:
                # Check if already indexed
                if not force_reindex:
                    existing = await db_session.execute(
                        select(Document).where(Document.filename == filename)
                    )
                    if existing.scalars().first():
                        print(f"  → Skipped (Already indexed in Document Vault): {filename}")
                        stats["skipped"] += 1
                        continue

                doc = await pipeline.ingest_file(file_path=file_path, force_reindex=force_reindex)

                # Enrich metadata if manifest entry is available
                if meta_hint and doc:
                    merged = dict(doc.metadata_ or {})
                    if "company" in meta_hint:
                        merged["parties"] = [meta_hint["company"]]
                    if "contract_type" in meta_hint:
                        merged["contract_type"] = meta_hint["contract_type"]
                    if "provenance" in meta_hint:
                        merged["provenance"] = meta_hint["provenance"]
                    doc.metadata_ = merged
                    await db_session.commit()

                print(
                    f"  ✓ Successfully indexed: {filename} (Chunks: {len(doc.chunks) if doc else 0})"
                )
                stats["indexed"] += 1

            except Exception as e:
                logger.error("seed_contract_failed", filename=filename, error=str(e))
                print(f"  ✗ Failed ingesting {filename}: {e}")
                stats["failed"] += 1

    if session:
        await _ingest_with_session(session)
    else:
        factory = AsyncSessionFactory()
        async with factory() as db_session:
            await _ingest_with_session(db_session)

    print(
        f"\nSeeding complete! Indexed: {stats['indexed']}, Skipped: {stats['skipped']}, Failed: {stats['failed']}"
    )
    return stats


async def seed_if_empty(min_contracts: int = 15) -> int:
    """Convenience hook: If database has fewer than min_contracts, seed authentic contracts."""
    factory = AsyncSessionFactory()
    async with factory() as session:
        count_res = await session.execute(select(func.count(Document.id)))
        count = count_res.scalar() or 0
        if count < min_contracts:
            logger.info("database_empty_auto_seeding", existing_count=count)
            res = await seed_real_contracts(limit=min_contracts, session=session)
            return res.get("indexed", 0)
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed real commercial contracts into Termnova database."
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of contracts to ingest"
    )
    parser.add_argument(
        "--force-reindex", action="store_true", help="Force re-indexing existing files"
    )
    parser.add_argument(
        "--dir", type=str, default=str(CONTRACTS_DIR), help="Contracts directory path"
    )
    args = parser.parse_args()

    asyncio.run(
        seed_real_contracts(
            contracts_dir=Path(args.dir),
            limit=args.limit,
            force_reindex=args.force_reindex,
        )
    )
