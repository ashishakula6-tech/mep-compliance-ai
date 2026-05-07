import re
import json
from pathlib import Path


# Maps keywords found in text → parameter names that match rules.json
PARAMETER_PATTERNS = {
    "duct_clearance_mm": [
        r"duct\s+clearance[:\s=]+(\d+(?:\.\d+)?)\s*mm",
        r"clearance[:\s=]+(\d+(?:\.\d+)?)\s*mm",
        r"duct.*?(\d+(?:\.\d+)?)\s*mm\s+clearance",
    ],
    "supply_air_temp_c": [
        r"supply\s+air\s+temp(?:erature)?[:\s=]+(\d+(?:\.\d+)?)\s*°?c",
        r"supply\s+temp[:\s=]+(\d+(?:\.\d+)?)",
        r"sat[:\s=]+(\d+(?:\.\d+)?)",
    ],
    "fresh_air_rate_percent": [
        r"fresh\s+air[:\s=]+(\d+(?:\.\d+)?)\s*%",
        r"outdoor\s+air\s+rate[:\s=]+(\d+(?:\.\d+)?)\s*%",
        r"oa\s+rate[:\s=]+(\d+(?:\.\d+)?)\s*%",
    ],
    "panel_spacing_mm": [
        r"panel\s+spacing[:\s=]+(\d+(?:\.\d+)?)\s*mm",
        r"clearance\s+(?:in\s+front\s+of\s+)?panel[:\s=]+(\d+(?:\.\d+)?)\s*mm",
        r"working\s+space[:\s=]+(\d+(?:\.\d+)?)\s*mm",
    ],
    "cable_tray_fill_percent": [
        r"cable\s+tray\s+fill[:\s=]+(\d+(?:\.\d+)?)\s*%",
        r"tray\s+fill[:\s=]+(\d+(?:\.\d+)?)\s*%",
        r"fill\s+ratio[:\s=]+(\d+(?:\.\d+)?)\s*%",
    ],
    "conduit_diameter_mm": [
        r"conduit\s+diameter[:\s=]+(\d+(?:\.\d+)?)\s*mm",
        r"conduit\s+size[:\s=]+(\d+(?:\.\d+)?)\s*mm",
    ],
    "pipe_slope_mm_per_m": [
        r"pipe\s+slope[:\s=]+(\d+(?:\.\d+)?)\s*mm\s*/\s*m",
        r"drainage\s+slope[:\s=]+(\d+(?:\.\d+)?)",
        r"fall[:\s=]+(\d+(?:\.\d+)?)\s*mm\s*/\s*m",
    ],
    "hot_water_temp_c": [
        r"hot\s+water\s+temp(?:erature)?[:\s=]+(\d+(?:\.\d+)?)\s*°?c",
        r"hwt[:\s=]+(\d+(?:\.\d+)?)",
        r"hot\s+water\s+set\s*point[:\s=]+(\d+(?:\.\d+)?)",
    ],
    "cold_water_pressure_kpa": [
        r"cold\s+water\s+pressure[:\s=]+(\d+(?:\.\d+)?)\s*kpa",
        r"supply\s+pressure[:\s=]+(\d+(?:\.\d+)?)\s*kpa",
        r"cwp[:\s=]+(\d+(?:\.\d+)?)",
    ],
    "sprinkler_spacing_m": [
        r"sprinkler\s+spacing[:\s=]+(\d+(?:\.\d+)?)\s*m",
        r"head\s+spacing[:\s=]+(\d+(?:\.\d+)?)\s*m",
        r"sprinkler.*?(\d+(?:\.\d+)?)\s*m\s+spacing",
    ],
    "fire_pipe_pressure_kpa": [
        r"fire\s+(?:main\s+)?pressure[:\s=]+(\d+(?:\.\d+)?)\s*kpa",
        r"suppression\s+pressure[:\s=]+(\d+(?:\.\d+)?)\s*kpa",
        r"fire\s+pipe.*?(\d+(?:\.\d+)?)\s*kpa",
    ],
}


def extract_data_from_file(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        return {}

    suffix = path.suffix.lower()

    # JSON input — direct parameter map
    if suffix == ".json":
        with open(file_path) as f:
            data = json.load(f)
        fields = {k: v for k, v in data.items() if not k.startswith("_")}
        data["_meta"] = {
            "method": "json_direct",
            "format": "JSON",
            "confidence": "high",
            "fields_found": len(fields),
            "total_possible": len(PARAMETER_PATTERNS),
            "document_type": "Structured Data",
            "needs_ocr": False,
        }
        return data

    # Text / spec sheet — regex extraction
    if suffix in (".txt", ".csv", ".md"):
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        text = raw.lower()
        extracted = _extract_from_text(text)
        n = len(extracted)
        extracted["_meta"] = {
            "method": "regex_nlp",
            "format": suffix[1:].upper(),
            "confidence": "high" if n >= 5 else "medium" if n >= 2 else "low",
            "fields_found": n,
            "total_possible": len(PARAMETER_PATTERNS),
            "char_count": len(raw),
            "document_type": _detect_doc_type(text),
            "needs_ocr": False,
        }
        return extracted

    # PDF — extract raw text then regex
    if suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            pages = len(reader.pages)
            page_texts = [page.extract_text() or "" for page in reader.pages]
            text = " ".join(page_texts)
            has_text = len(text.strip()) > 100
            extracted = _extract_from_text(text.lower())
            n = len(extracted)
            extracted["_meta"] = {
                "method": "pdf_text_extraction" if has_text else "pdf_no_text",
                "format": "PDF",
                "confidence": "high" if n >= 5 else "medium" if has_text else "low",
                "fields_found": n,
                "total_possible": len(PARAMETER_PATTERNS),
                "pages": pages,
                "document_type": _detect_doc_type(text.lower()),
                "needs_ocr": not has_text,
            }
            if not has_text:
                extracted["_meta"]["ocr_hint"] = (
                    "This PDF contains scanned images with no embedded text. "
                    "Convert to searchable PDF using Adobe Acrobat or an OCR tool (e.g. Tesseract) before uploading."
                )
            return extracted
        except ImportError:
            return {"_error": "pypdf not installed — upload .txt or .json files"}
        except Exception as e:
            return {"_error": str(e)}

    return {}


def _detect_doc_type(text: str) -> str:
    scores = {
        "HVAC": sum(1 for k in ["hvac", "duct", "supply air", "return air", "chiller", "ahu", "air handling"] if k in text),
        "Electrical": sum(1 for k in ["electrical", "panel", "cable tray", "conduit", "circuit", "switchboard", "busbar"] if k in text),
        "Plumbing": sum(1 for k in ["plumbing", "drain", "pipe slope", "hot water", "cold water", "sanitary", "sewage"] if k in text),
        "Fire Protection": sum(1 for k in ["fire", "sprinkler", "suppression", "nfpa", "standpipe", "deluge"] if k in text),
    }
    total = sum(scores.values())
    if total == 0:
        return "Unknown"
    top = max(scores, key=scores.get)
    if scores[top] >= total * 0.65:
        return top
    return "Mixed MEP"


def _extract_from_text(text: str) -> dict:
    extracted = {}
    for param, patterns in PARAMETER_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted[param] = float(match.group(1))
                break
    return extracted
