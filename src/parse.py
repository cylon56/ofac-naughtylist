"""Parse the SDN Advanced XML and extract all digital currency addresses."""

import logging
import re
from dataclasses import dataclass

import defusedxml.ElementTree as ET

logger = logging.getLogger(__name__)


@dataclass
class SanctionedAddress:
    address: str
    ofac_ticker: str
    entity_id: int
    entity_name: str
    programs: list[str]
    date_listed: str
    feature_id: int


def get_namespace(root: ET.Element) -> dict[str, str]:
    """Extract namespace from root element tag."""
    match = re.match(r'\{(.+?)\}', root.tag)
    return {'ns': match.group(1)} if match else {}


def _extract_entity_name(identity_elem: ET.Element, prefix: str) -> str:
    """Extract the primary entity name from an Identity element."""
    for alias in identity_elem.findall(f"{prefix}Alias"):
        if alias.get("Primary", "").lower() != "true":
            continue
        for doc_name in alias.findall(f"{prefix}DocumentedName"):
            parts = []
            for doc_name_part in doc_name.findall(f"{prefix}DocumentedNamePart"):
                for name_part_val in doc_name_part.findall(f"{prefix}NamePartValue"):
                    if name_part_val.text:
                        parts.append(name_part_val.text.strip())
            if parts:
                return " ".join(parts)
    return "UNKNOWN"


def _build_feature_type_map(xml_path: str, prefix: str) -> dict[str, str]:
    """
    Build a mapping of FeatureType ID -> ticker from ReferenceValueSets.

    Scans FeatureType elements whose text starts with "Digital Currency Address - "
    and extracts the ticker suffix.
    """
    dc_types: dict[str, str] = {}

    for event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == f"{prefix}FeatureType":
            name = elem.text.strip() if elem.text else ""
            if name.startswith("Digital Currency Address - "):
                ticker = name.split(" - ", 1)[1].strip()
                dc_types[elem.get("ID", "")] = ticker
            elem.clear()
        # Stop after ReferenceValueSets to avoid parsing the whole file
        elif elem.tag == f"{prefix}ReferenceValueSets":
            break

    return dc_types


def _build_sanctions_map(xml_path: str, prefix: str) -> dict[int, tuple[list[str], str]]:
    """
    Build a mapping of ProfileID -> (programs, date_listed) from SanctionsEntries.

    Programs are extracted from SanctionsMeasure/Comment elements.
    Date is extracted from EntryEvent/Date elements.
    """
    sanctions: dict[int, tuple[list[str], str]] = {}

    for event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag != f"{prefix}SanctionsEntry":
            continue

        profile_id = int(elem.get("ProfileID", "0"))

        # Extract programs from SanctionsMeasure > Comment
        programs = []
        for sm in elem.findall(f"{prefix}SanctionsMeasure"):
            comment = sm.find(f"{prefix}Comment")
            if comment is not None and comment.text and comment.text.strip():
                programs.append(comment.text.strip())

        # Extract date from EntryEvent > Date
        date_listed = ""
        entry_event = elem.find(f"{prefix}EntryEvent")
        if entry_event is not None:
            date_elem = entry_event.find(f"{prefix}Date")
            if date_elem is not None:
                year_elem = date_elem.find(f"{prefix}Year")
                month_elem = date_elem.find(f"{prefix}Month")
                day_elem = date_elem.find(f"{prefix}Day")
                year = year_elem.text if year_elem is not None and year_elem.text else "1970"
                month = month_elem.text if month_elem is not None and month_elem.text else "1"
                day = day_elem.text if day_elem is not None and day_elem.text else "1"
                date_listed = f"{year}-{int(month):02d}-{int(day):02d}"

        sanctions[profile_id] = (programs, date_listed)
        elem.clear()

    return sanctions


def parse_sdn_xml(xml_path: str) -> list[SanctionedAddress]:
    """
    Parse the SDN Advanced XML file and extract all digital currency addresses.

    The XML has three key sections:
    1. ReferenceValueSets - contains FeatureType ID -> ticker lookup table
    2. DistinctParties - contains entity profiles with digital currency features
    3. SanctionsEntries - contains programs and listing dates per profile

    Args:
        xml_path: Path to the downloaded sdn_advanced.xml file.

    Returns:
        List of SanctionedAddress objects.
    """
    results: list[SanctionedAddress] = []
    known_tickers = set()

    # Detect namespace from root element
    ns = {}
    for event, elem in ET.iterparse(xml_path, events=("start",)):
        ns = get_namespace(elem)
        break

    prefix = f"{{{ns['ns']}}}" if ns else ""

    # Build lookup tables
    dc_types = _build_feature_type_map(xml_path, prefix)
    logger.info("Found %d digital currency feature types", len(dc_types))

    sanctions_map = _build_sanctions_map(xml_path, prefix)
    logger.info("Found %d sanctions entries", len(sanctions_map))

    # Process DistinctParty elements
    for event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag != f"{prefix}DistinctParty":
            continue

        entity_id = int(elem.get("FixedRef", "0"))

        # Extract entity name from Profile > Identity
        entity_name = "UNKNOWN"
        profile = elem.find(f"{prefix}Profile")
        if profile is not None:
            identity = profile.find(f"{prefix}Identity")
            if identity is not None:
                entity_name = _extract_entity_name(identity, prefix)

        # Get programs and date from sanctions map
        programs, date_listed = sanctions_map.get(entity_id, ([], ""))

        # Extract digital currency address features
        if profile is not None:
            for feature in profile.findall(f"{prefix}Feature"):
                feature_type_id = feature.get("FeatureTypeID", "")
                if feature_type_id not in dc_types:
                    continue

                ticker = dc_types[feature_type_id]
                feature_id = int(feature.get("ID", "0"))

                if ticker not in known_tickers:
                    known_tickers.add(ticker)
                    logger.info("Discovered ticker: %s", ticker)

                for fv in feature.findall(f"{prefix}FeatureVersion"):
                    # Address is directly in VersionDetail text
                    address = ""
                    for vd in fv.findall(f"{prefix}VersionDetail"):
                        if vd.text and vd.text.strip():
                            address = vd.text.strip()
                            break

                    if not address:
                        logger.warning(
                            "Empty address for feature %d on entity %d (%s)",
                            feature_id, entity_id, entity_name
                        )
                        continue

                    results.append(SanctionedAddress(
                        address=address,
                        ofac_ticker=ticker,
                        entity_id=entity_id,
                        entity_name=entity_name,
                        programs=programs,
                        date_listed=date_listed,
                        feature_id=feature_id,
                    ))

        # Free memory
        elem.clear()

    return results
