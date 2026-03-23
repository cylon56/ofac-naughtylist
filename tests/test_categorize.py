"""Tests for src/categorize.py — address-to-chain mapping."""

import os

import pytest

from src.categorize import CategorizedAddress, categorize_addresses, load_chain_mapping
from src.parse import SanctionedAddress, parse_sdn_xml

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_sdn_advanced.xml")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "chain_mapping.yaml")


@pytest.fixture
def chain_mapping():
    return load_chain_mapping(CONFIG_PATH)


@pytest.fixture
def raw_addresses():
    return parse_sdn_xml(FIXTURE_PATH)


@pytest.fixture
def categorized(raw_addresses, chain_mapping):
    return categorize_addresses(raw_addresses, chain_mapping)


class TestLoadChainMapping:
    def test_loads_config(self, chain_mapping):
        assert "direct_mappings" in chain_mapping
        assert "multi_chain_tickers" in chain_mapping
        assert "address_patterns" in chain_mapping

    def test_direct_mappings(self, chain_mapping):
        dm = chain_mapping["direct_mappings"]
        assert dm["ETH"] == "ethereum"
        assert dm["XBT"] == "bitcoin"
        assert dm["TRX"] == "tron"


class TestCategorizeAddresses:
    def test_returns_dict_of_chains(self, categorized):
        assert isinstance(categorized, dict)
        for chain, addrs in categorized.items():
            assert isinstance(chain, str)
            assert all(isinstance(a, CategorizedAddress) for a in addrs)

    def test_eth_direct_mapping(self, categorized):
        """ETH-tickered addresses should go to ethereum chain."""
        assert "ethereum" in categorized
        eth_addrs = categorized["ethereum"]
        assert any(a.address == "0x7F367cC41522cE07553e823bf3be79A889DEbe1B" for a in eth_addrs)

    def test_xbt_direct_mapping(self, categorized):
        """XBT-tickered addresses should go to bitcoin chain."""
        assert "bitcoin" in categorized
        btc_addrs = categorized["bitcoin"]
        assert any(a.address.startswith("bc1") for a in btc_addrs)
        assert any(a.address.startswith("1A1z") for a in btc_addrs)

    def test_multi_ticker_deduplication(self, categorized):
        """Address listed under both ETH and USDT should appear once with both tickers."""
        eth_addrs = categorized["ethereum"]
        dup_addr = [a for a in eth_addrs if a.address == "0xd882cFc20F52f2599D84b8e8D58C7FB62cfE344b"]
        assert len(dup_addr) == 1
        assert "ETH" in dup_addr[0].ofac_tickers
        assert "USDT" in dup_addr[0].ofac_tickers

    def test_tron_usdt_address(self, categorized):
        """USDT with T-prefix address should go to tron chain."""
        assert "tron" in categorized
        tron_addrs = categorized["tron"]
        assert any(a.address == "TN2YVFiBnEhM2DFoDqGGoenYbGe8uVJJEY" for a in tron_addrs)

    def test_unknown_bucket(self, categorized):
        """Unrecognized ticker with unrecognized address format goes to unknown."""
        assert "unknown" in categorized
        unknown_addrs = categorized["unknown"]
        assert any(a.address == "someunknownaddressformat12345" for a in unknown_addrs)

    def test_evm_compatible_flag(self, categorized):
        """0x addresses should have evm_compatible=True."""
        eth_addrs = categorized["ethereum"]
        for a in eth_addrs:
            if a.address.startswith("0x"):
                assert a.evm_compatible is True

    def test_non_evm_not_compatible(self, categorized):
        """Non-0x addresses should have evm_compatible=False."""
        btc_addrs = categorized["bitcoin"]
        for a in btc_addrs:
            assert a.evm_compatible is False

    def test_deterministic_sorting(self, categorized):
        """Addresses within each chain should be sorted alphabetically."""
        for chain, addrs in categorized.items():
            addresses = [a.address for a in addrs]
            assert addresses == sorted(addresses)

    def test_usdc_0x_to_ethereum(self, categorized):
        """USDC with 0x address should go to ethereum with evm_compatible=True."""
        eth_addrs = categorized["ethereum"]
        usdc = [a for a in eth_addrs if "USDC" in a.ofac_tickers]
        assert len(usdc) == 1
        assert usdc[0].evm_compatible is True

    def test_monero_address(self, categorized):
        assert "monero" in categorized
        assert len(categorized["monero"]) == 1

    def test_litecoin_address(self, categorized):
        assert "litecoin" in categorized
        assert len(categorized["litecoin"]) == 1

    def test_dash_address(self, categorized):
        assert "dash" in categorized
        assert len(categorized["dash"]) == 1

    def test_zcash_address(self, categorized):
        assert "zcash" in categorized
        assert len(categorized["zcash"]) == 1

    def test_ripple_address(self, categorized):
        assert "ripple" in categorized
        assert len(categorized["ripple"]) == 1

    def test_solana_address(self, categorized):
        assert "solana" in categorized
        assert len(categorized["solana"]) == 1
        assert categorized["solana"][0].address == "42RLPACwZPx3vYYmxSueqsogfynBDqXK298EDsNoyoHi"

    def test_source_feature_ids_merged(self, categorized):
        """Deduplicated address should have all feature IDs merged."""
        eth_addrs = categorized["ethereum"]
        dup = [a for a in eth_addrs if a.address == "0xd882cFc20F52f2599D84b8e8D58C7FB62cfE344b"]
        assert len(dup) == 1
        # Should have feature IDs from both ETH and USDT listings
        assert len(dup[0].source_feature_ids) >= 2
