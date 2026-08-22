"""Upload authentic commercial contract PDFs directly to the live Render deployment."""

import asyncio
from pathlib import Path

import httpx

CONTRACTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "contracts"
REMOTE_URL = "https://termnova.onrender.com"


async def upload_all_contracts(remote_base: str = REMOTE_URL, limit: int = 30):
    pdf_files = sorted(list(CONTRACTS_DIR.glob("*.pdf")))
    if limit:
        pdf_files = pdf_files[:limit]

    print(f"Target deployment: {remote_base}")
    print(f"Found {len(pdf_files)} contract PDFs to upload...")

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Check health
        try:
            health = await client.get(f"{remote_base}/health")
            print(f"Health check: {health.status_code} -> {health.text[:100]}")
        except Exception as e:
            print(f"Failed to connect to {remote_base}: {e}")
            return

        # Check existing documents
        try:
            docs_resp = await client.get(f"{remote_base}/api/v1/documents")
            existing_filenames = {d["filename"] for d in docs_resp.json().get("documents", [])}
            print(f"Already on remote server: {len(existing_filenames)} documents")
        except Exception as e:
            print(f"Warning: could not fetch existing docs: {e}")
            existing_filenames = set()

        for idx, pdf_path in enumerate(pdf_files, 1):
            if pdf_path.name in existing_filenames:
                print(f"[{idx}/{len(pdf_files)}] ⏭️ Already uploaded: {pdf_path.name}")
                continue

            print(
                f"[{idx}/{len(pdf_files)}] 📤 Uploading & indexing {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)..."
            )
            try:
                with open(pdf_path, "rb") as f:
                    files = {"file": (pdf_path.name, f, "application/pdf")}
                    resp = await client.post(f"{remote_base}/api/v1/documents/upload", files=files)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    print(f"   ✓ Indexed: {pdf_path.name} (ID: {data.get('document_id', 'N/A')})")
                else:
                    print(f"   ✗ HTTP {resp.status_code}: {resp.text}")
            except Exception as exc:
                print(f"   ✗ Upload error: {exc}")


if __name__ == "__main__":
    asyncio.run(upload_all_contracts(limit=30))
