"""Generate JSON output files from categorized addresses."""

import json
import logging
import os
from datetime import datetime, timezone

from src.categorize import CategorizedAddress

logger = logging.getLogger(__name__)


def generate_output(
    categorized: dict[str, list[CategorizedAddress]],
    output_dir: str = "data",
    source_list: str = "SDN",
    source_xml_url: str = "https://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml",
) -> None:
    """
    Write per-chain JSON files, all_addresses.json, and metadata.json.

    Args:
        categorized: Output from categorize.py.
        output_dir: Root output directory.
        source_list: "SDN" or "CONSOLIDATED".
        source_xml_url: URL used to download the source XML.
    """
    chains_dir = os.path.join(output_dir, "chains")
    os.makedirs(chains_dir, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    all_addresses = []
    chain_counts = {}
    total_entity_ids = set()
    all_tickers = set()

    for chain, addresses in sorted(categorized.items()):
        chain_counts[chain] = len(addresses)

        # Build per-chain file
        chain_addresses = []
        for addr in addresses:
            total_entity_ids.add(addr.entity_id)
            for t in addr.ofac_tickers:
                all_tickers.add(t)

            entry = {
                "address": addr.address,
                "ofac_tickers": addr.ofac_tickers,
                "evm_compatible": addr.evm_compatible,
                "entity_id": addr.entity_id,
                "entity_name": addr.entity_name,
                "programs": addr.programs,
                "date_listed": addr.date_listed,
                "source_feature_ids": addr.source_feature_ids,
            }
            chain_addresses.append(entry)

            # Add to combined list
            all_addresses.append({
                "address": addr.address,
                "chain": chain,
                "ofac_tickers": addr.ofac_tickers,
                "entity_id": addr.entity_id,
                "entity_name": addr.entity_name,
                "programs": addr.programs,
                "date_listed": addr.date_listed,
            })

        chain_file = {
            "chain": chain,
            "source_list": source_list,
            "last_updated": now,
            "source_xml_url": source_xml_url,
            "address_count": len(chain_addresses),
            "addresses": chain_addresses,
        }

        chain_path = os.path.join(chains_dir, f"{chain}.json")
        with open(chain_path, "w") as f:
            json.dump(chain_file, f, indent=2, sort_keys=True)

    # Write all_addresses.json
    total_count = sum(chain_counts.values())
    all_addresses.sort(key=lambda a: (a["chain"], a["address"]))
    all_file = {
        "source_list": source_list,
        "last_updated": now,
        "total_address_count": total_count,
        "addresses": all_addresses,
    }
    with open(os.path.join(output_dir, "all_addresses.json"), "w") as f:
        json.dump(all_file, f, indent=2, sort_keys=True)

    # Write metadata.json
    metadata = {
        "last_updated": now,
        "source_list": source_list,
        "source_xml_url": source_xml_url,
        "total_addresses": total_count,
        "total_unique_entities": len(total_entity_ids),
        "chains": chain_counts,
        "ofac_tickers_found": sorted(all_tickers),
        "schema_version": "1.0.0",
    }
    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)

    # Remove stale chain files from previous runs
    current_chains = {f"{chain}.json" for chain in categorized}
    for filename in os.listdir(chains_dir):
        if filename.endswith(".json") and filename not in current_chains:
            stale_path = os.path.join(chains_dir, filename)
            logger.info("Removing stale chain file: %s", filename)
            os.remove(stale_path)
