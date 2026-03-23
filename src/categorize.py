"""Map parsed addresses to chains using ticker mapping and address format inference."""

import logging
import re
from dataclasses import dataclass, field

import yaml

from src.parse import SanctionedAddress

logger = logging.getLogger(__name__)


@dataclass
class CategorizedAddress:
    address: str
    chain: str
    ofac_tickers: list[str]
    evm_compatible: bool
    entity_id: int
    entity_name: str
    programs: list[str]
    date_listed: str
    source_feature_ids: list[int]


def load_chain_mapping(config_path: str = "config/chain_mapping.yaml") -> dict:
    """Load the chain mapping configuration."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def categorize_addresses(
    raw_addresses: list[SanctionedAddress],
    chain_mapping: dict,
) -> dict[str, list[CategorizedAddress]]:
    """
    Categorize raw addresses into chain buckets.

    Args:
        raw_addresses: Output from parse.py.
        chain_mapping: Loaded from config/chain_mapping.yaml.

    Returns:
        Dict mapping chain name -> list of CategorizedAddress.
        Includes an "unknown" key for unmapped addresses.
    """
    direct_mappings = chain_mapping.get("direct_mappings", {})
    multi_chain_tickers = set(chain_mapping.get("multi_chain_tickers", []))
    address_patterns_raw = chain_mapping.get("address_patterns", [])
    # Precompile regex patterns for performance and early validation
    address_patterns = []
    for pat_entry in address_patterns_raw:
        try:
            address_patterns.append({
                **pat_entry,
                "_compiled": re.compile(pat_entry["pattern"]),
            })
        except re.error as e:
            logger.error("Invalid regex pattern %r: %s", pat_entry["pattern"], e)
            raise
    evm_ticker_overrides = chain_mapping.get("evm_ticker_overrides", {})

    # First pass: group by address string to deduplicate
    grouped: dict[str, dict] = {}
    for sa in raw_addresses:
        key = sa.address
        if key not in grouped:
            grouped[key] = {
                "address": sa.address,
                "ofac_tickers": [],
                "entity_id": sa.entity_id,
                "entity_name": sa.entity_name,
                "programs": list(sa.programs),
                "date_listed": sa.date_listed,
                "source_feature_ids": [],
            }
        if sa.ofac_ticker not in grouped[key]["ofac_tickers"]:
            grouped[key]["ofac_tickers"].append(sa.ofac_ticker)
        if sa.feature_id not in grouped[key]["source_feature_ids"]:
            grouped[key]["source_feature_ids"].append(sa.feature_id)

    # Second pass: determine chain for each unique address
    result: dict[str, list[CategorizedAddress]] = {}

    for addr_str, info in grouped.items():
        chain = None
        evm_compatible = False
        tickers = info["ofac_tickers"]

        # Step 1: Check direct mappings
        direct_chains = []
        for t in tickers:
            if t in direct_mappings:
                direct_chains.append(direct_mappings[t])

        if direct_chains:
            if len(set(direct_chains)) > 1:
                logger.warning(
                    "Address %s has conflicting direct chain mappings: %s. Using first.",
                    addr_str, direct_chains,
                )
            chain = direct_chains[0]
        else:
            # Step 2: All tickers are multi-chain, use address pattern inference
            for pat_entry in address_patterns:
                if pat_entry["_compiled"].match(addr_str):
                    chain = pat_entry["chain"]
                    break

            # Step 2b: For 0x addresses, check if any ticker provides more context
            if chain == "ethereum":
                for t in tickers:
                    if t in evm_ticker_overrides:
                        chain = evm_ticker_overrides[t]
                        break
                evm_compatible = True

        if chain is None:
            chain = "unknown"

        # Set evm_compatible for direct-mapped EVM chains with 0x addresses
        if chain in ("ethereum", "arbitrum", "bsc", "ethereum_classic") and addr_str.startswith("0x"):
            evm_compatible = True

        cat_addr = CategorizedAddress(
            address=info["address"],
            chain=chain,
            ofac_tickers=sorted(info["ofac_tickers"]),
            evm_compatible=evm_compatible,
            entity_id=info["entity_id"],
            entity_name=info["entity_name"],
            programs=info["programs"],
            date_listed=info["date_listed"],
            source_feature_ids=sorted(info["source_feature_ids"]),
        )

        if chain not in result:
            result[chain] = []
        result[chain].append(cat_addr)

    # Warn about unmapped tickers that ended up in "unknown"
    if "unknown" in result:
        unmapped_tickers: set[str] = set()
        for addr in result["unknown"]:
            for t in addr.ofac_tickers:
                if t not in direct_mappings and t not in multi_chain_tickers:
                    unmapped_tickers.add(t)
        if unmapped_tickers:
            logger.warning(
                "Unmapped tickers found (addresses sent to 'unknown'): %s. "
                "Consider adding them to config/chain_mapping.yaml.",
                sorted(unmapped_tickers),
            )

    # Sort addresses within each chain for deterministic output
    for chain in result:
        result[chain].sort(key=lambda a: a.address)

    return result
