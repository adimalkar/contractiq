"""Download and curate authentic commercial enterprise contracts from the CUAD (Atticus Open Dataset) on Hugging Face."""

import argparse
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

# HF dataset metadata endpoint
CUAD_API_URL = "https://huggingface.co/api/datasets/theatticusproject/cuad"
HF_RAW_BASE_URL = "https://huggingface.co/datasets/theatticusproject/cuad/resolve/main/"

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "contracts"


def clean_filename(rfilename: str) -> tuple[str, dict[str, str]]:
    """Convert raw CUAD file path into a clean, professional contract filename and metadata dict.

    Raw format example:
    'CUAD_v1/full_contract_pdf/Part_I/Affiliate_Agreements/CreditcardscomInc_20070810_S-1_EX-10.33_362297_EX-10.33_Affiliate Agreement.pdf'
    """
    raw_name = rfilename.split("/")[-1]
    # Remove file extension
    base = re.sub(r"\.pdf$", "", raw_name, flags=re.I)

    parts = base.split("_")
    company_raw = parts[0] if len(parts) > 0 else "Enterprise"
    date_raw = parts[1] if len(parts) > 1 and parts[1].isdigit() else "20240101"

    # Extract contract title / type from the end
    contract_type_raw = parts[-1] if len(parts) > 0 else "Agreement"
    # Clean up company name (split PascalCase or clean)
    company = re.sub(r"([a-z])([A-Z])", r"\1 \2", company_raw)
    company = re.sub(
        r"(Inc|Corp|Llc|Ltd|Holdings|Group|Systems|Technologies|Com)$", r" \1", company, flags=re.I
    ).strip()

    # Format date YYYY-MM
    year = date_raw[:4] if len(date_raw) == 8 else "2024"

    # Clean type name
    type_slug = contract_type_raw.replace(" ", "_").replace("-", "_")
    company_slug = re.sub(r"[^a-zA-Z0-9]", "", company_raw)

    clean_name = f"{company_slug}_{type_slug}_{year}.pdf"

    # Category classification based on path / type
    cat_lower = contract_type_raw.lower() + " " + rfilename.lower()
    if "nda" in cat_lower or "confidential" in cat_lower:
        doc_type = "nda"
    elif "sow" in cat_lower or "statement of work" in cat_lower:
        doc_type = "sow"
    elif "msa" in cat_lower or "master" in cat_lower:
        doc_type = "msa"
    elif "lease" in cat_lower or "real estate" in cat_lower:
        doc_type = "lease"
    elif "vendor" in cat_lower or "supply" in cat_lower or "manufacturing" in cat_lower:
        doc_type = "vendor"
    elif "license" in cat_lower or "software" in cat_lower or "ip" in cat_lower:
        doc_type = "license"
    elif "distributor" in cat_lower or "reseller" in cat_lower:
        doc_type = "distributor"
    elif (
        "service" in cat_lower
        or "maintenance" in cat_lower
        or "hosting" in cat_lower
        or "consulting" in cat_lower
    ):
        doc_type = "service"
    elif "co_branding" in cat_lower or "strategic" in cat_lower or "affiliate" in cat_lower:
        doc_type = "partnership"
    else:
        doc_type = "commercial"

    meta = {
        "original_cuad_path": rfilename,
        "clean_filename": clean_name,
        "company": company,
        "contract_type": doc_type,
        "effective_year": year,
        "raw_title": contract_type_raw,
        "provenance": "SEC EDGAR / Atticus CUAD Dataset (CC-BY 4.0)",
    }

    return clean_name, meta


def download_cuad_contracts(
    limit: int = 50, output_dir: Path | None = None
) -> list[dict[str, str]]:
    """Fetch real contract PDFs from the CUAD dataset repository."""
    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching CUAD dataset file index from {CUAD_API_URL}...")
    req = urllib.request.Request(
        CUAD_API_URL,
        headers={"User-Agent": "Mozilla/5.0 (Termnova Enterprise Legal Dataset Curator)"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    siblings = data.get("siblings", [])
    pdf_files = [
        s["rfilename"]
        for s in siblings
        if s["rfilename"].endswith(".pdf") and "full_contract_pdf" in s["rfilename"]
    ]

    print(f"Found {len(pdf_files)} authentic commercial PDF agreements in CUAD.")

    # Group by category folder
    from collections import defaultdict

    by_cat = defaultdict(list)
    for p in pdf_files:
        parts = p.split("/")
        cat = parts[3] if len(parts) >= 4 else "Commercial"
        by_cat[cat].append(p)

    print(f"Detected {len(by_cat)} distinct commercial legal domains in dataset.")

    # Round-robin selection across all categories up to limit
    selected_files: list[str] = []
    max_per_cat = max(2, limit // len(by_cat) + 1)

    for _cat, files in sorted(by_cat.items()):
        selected_files.extend(files[:max_per_cat])

    selected_files = selected_files[:limit]
    manifest: list[dict[str, str]] = []

    print(f"Downloading {len(selected_files)} diverse real enterprise contracts into {out_dir}...")
    for idx, rfilename in enumerate(selected_files, 1):
        clean_name, meta = clean_filename(rfilename)
        dest_pdf = out_dir / clean_name

        if dest_pdf.exists() and dest_pdf.stat().st_size > 0:
            print(f"[{idx}/{len(selected_files)}] Already downloaded: {clean_name}")
            manifest.append(meta)
            continue

        encoded_path = urllib.parse.quote(rfilename)
        download_url = HF_RAW_BASE_URL + encoded_path

        try:
            dl_req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "Mozilla/5.0 (Termnova Enterprise Legal Dataset Curator)"},
            )
            with urllib.request.urlopen(dl_req, timeout=15) as dl_resp:
                content = dl_resp.read()
                dest_pdf.write_bytes(content)
                meta["file_size_bytes"] = len(content)
                manifest.append(meta)
                print(
                    f"[{idx}/{len(selected_files)}] ✓ Downloaded {clean_name} ({len(content) // 1024} KB) - {meta['company']} [{meta['contract_type'].upper()}]"
                )
        except Exception as err:
            print(f"[{idx}/{len(selected_files)}] ✗ Failed downloading {rfilename}: {err}")

    # Write manifest.json
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Saved dataset manifest ({len(manifest)} contracts) to {manifest_path}")

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download real commercial enterprise contracts from CUAD dataset."
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Number of contracts to download (default: 50)"
    )
    parser.add_argument(
        "--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Destination directory"
    )
    args = parser.parse_args()

    download_cuad_contracts(limit=args.limit, output_dir=Path(args.output_dir))
