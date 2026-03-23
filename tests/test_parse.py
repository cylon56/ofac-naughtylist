"""Tests for src/parse.py — XML parsing and address extraction."""

import os

import pytest

from src.parse import SanctionedAddress, get_namespace, parse_sdn_xml

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_sdn_advanced.xml")


class TestGetNamespace:
    def test_extracts_namespace(self):
        import xml.etree.ElementTree as ET
        tree = ET.parse(FIXTURE_PATH)
        root = tree.getroot()
        ns = get_namespace(root)
        assert "ns" in ns
        assert "sanctionslistservice.ofac.treas.gov" in ns["ns"]

    def test_no_namespace(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring("<Root><Child/></Root>")
        ns = get_namespace(root)
        assert ns == {}


class TestParseSdnXml:
    @pytest.fixture
    def addresses(self):
        return parse_sdn_xml(FIXTURE_PATH)

    def test_returns_list_of_sanctioned_addresses(self, addresses):
        assert isinstance(addresses, list)
        assert all(isinstance(a, SanctionedAddress) for a in addresses)

    def test_extracts_correct_count(self, addresses):
        # 3 from entity 1 + 4 from entity 2 + 5 from entity 3 + 1 from entity 4 + 1 from entity 5 + 1 from entity 6 = 15
        assert len(addresses) == 15

    def test_extracts_eth_addresses(self, addresses):
        eth_addrs = [a for a in addresses if a.ofac_ticker == "ETH"]
        assert len(eth_addrs) == 3  # 2 from LAZARUS + 1 from GARANTEX
        assert any(a.address == "0x7F367cC41522cE07553e823bf3be79A889DEbe1B" for a in eth_addrs)

    def test_entity_metadata_linked(self, addresses):
        lazarus_addrs = [a for a in addresses if a.entity_id == 39498]
        assert len(lazarus_addrs) == 3
        for a in lazarus_addrs:
            assert a.entity_name == "LAZARUS GROUP"
            assert "CYBER2" in a.programs
            assert "DPRK3" in a.programs
            assert a.date_listed == "2022-04-14"

    def test_xbt_addresses(self, addresses):
        xbt_addrs = [a for a in addresses if a.ofac_ticker == "XBT"]
        assert len(xbt_addrs) == 2
        assert any(a.address.startswith("bc1") for a in xbt_addrs)
        assert any(a.address.startswith("1A1z") for a in xbt_addrs)

    def test_multi_ticker_address(self, addresses):
        """Same address listed under ETH and USDT should produce separate records."""
        dup_addr = "0xd882cFc20F52f2599D84b8e8D58C7FB62cfE344b"
        dup_records = [a for a in addresses if a.address == dup_addr]
        assert len(dup_records) == 3  # ETH from entity 1, ETH + USDT from entity 2
        tickers = {a.ofac_ticker for a in dup_records}
        assert "ETH" in tickers
        assert "USDT" in tickers

    def test_tron_address(self, addresses):
        usdt_addrs = [a for a in addresses if a.ofac_ticker == "USDT"]
        tron_addrs = [a for a in usdt_addrs if a.address.startswith("T")]
        assert len(tron_addrs) == 1
        assert tron_addrs[0].address == "TN2YVFiBnEhM2DFoDqGGoenYbGe8uVJJEY"

    def test_unknown_ticker(self, addresses):
        unknown = [a for a in addresses if a.ofac_ticker == "NEWTICKER"]
        assert len(unknown) == 1
        assert unknown[0].entity_name == "UNKNOWN TICKER ENTITY"

    def test_feature_ids_extracted(self, addresses):
        lazarus_eth = [a for a in addresses if a.entity_id == 39498 and a.ofac_ticker == "ETH"]
        feature_ids = {a.feature_id for a in lazarus_eth}
        assert 52341 in feature_ids
        assert 52342 in feature_ids

    def test_addresses_stripped(self, addresses):
        """All addresses should have no leading/trailing whitespace."""
        for a in addresses:
            assert a.address == a.address.strip()

    def test_various_chains(self, addresses):
        """Entity 3 has XMR, LTC, DASH, ZEC, XRP addresses."""
        entity3 = [a for a in addresses if a.entity_id == 50001]
        assert len(entity3) == 5
        tickers = {a.ofac_ticker for a in entity3}
        assert tickers == {"XMR", "LTC", "DASH", "ZEC", "XRP"}
