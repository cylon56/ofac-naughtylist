"""Tests for src/output.py — JSON output generation."""

import json
import os
import tempfile

import pytest

from src.categorize import categorize_addresses, load_chain_mapping
from src.output import generate_output
from src.parse import parse_sdn_xml

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_sdn_advanced.xml")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "chain_mapping.yaml")


@pytest.fixture
def output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        raw = parse_sdn_xml(FIXTURE_PATH)
        mapping = load_chain_mapping(CONFIG_PATH)
        categorized = categorize_addresses(raw, mapping)
        generate_output(categorized, output_dir=tmpdir)
        yield tmpdir


class TestPerChainFiles:
    def test_chain_files_created(self, output_dir):
        chains_dir = os.path.join(output_dir, "chains")
        files = os.listdir(chains_dir)
        assert "ethereum.json" in files
        assert "bitcoin.json" in files
        assert "tron.json" in files
        assert "unknown.json" in files

    def test_chain_file_schema(self, output_dir):
        with open(os.path.join(output_dir, "chains", "ethereum.json")) as f:
            data = json.load(f)

        assert data["chain"] == "ethereum"
        assert data["source_list"] == "SDN"
        assert "last_updated" not in data
        assert "source_xml_url" in data
        assert data["address_count"] == len(data["addresses"])
        assert data["address_count"] > 0

        for addr in data["addresses"]:
            assert "address" in addr
            assert "ofac_tickers" in addr
            assert "evm_compatible" in addr
            assert "entity_id" in addr
            assert "entity_name" in addr
            assert "programs" in addr
            assert "date_listed" in addr
            assert "source_feature_ids" in addr

    def test_chain_file_address_fields(self, output_dir):
        with open(os.path.join(output_dir, "chains", "bitcoin.json")) as f:
            data = json.load(f)

        for addr in data["addresses"]:
            assert isinstance(addr["address"], str)
            assert isinstance(addr["ofac_tickers"], list)
            assert isinstance(addr["evm_compatible"], bool)
            assert isinstance(addr["entity_id"], int)
            assert isinstance(addr["entity_name"], str)
            assert isinstance(addr["programs"], list)
            assert isinstance(addr["date_listed"], str)
            assert isinstance(addr["source_feature_ids"], list)


class TestAllAddresses:
    def test_all_addresses_created(self, output_dir):
        path = os.path.join(output_dir, "all_addresses.json")
        assert os.path.exists(path)

    def test_all_addresses_schema(self, output_dir):
        with open(os.path.join(output_dir, "all_addresses.json")) as f:
            data = json.load(f)

        assert "source_list" in data
        assert "last_updated" not in data
        assert "total_address_count" in data
        assert "addresses" in data
        assert data["total_address_count"] == len(data["addresses"])

    def test_all_addresses_has_chain_field(self, output_dir):
        with open(os.path.join(output_dir, "all_addresses.json")) as f:
            data = json.load(f)

        for addr in data["addresses"]:
            assert "chain" in addr
            assert isinstance(addr["chain"], str)

    def test_all_addresses_union_of_chains(self, output_dir):
        """all_addresses.json should be the union of all chain files."""
        chains_dir = os.path.join(output_dir, "chains")
        total_from_chains = 0
        for fname in os.listdir(chains_dir):
            with open(os.path.join(chains_dir, fname)) as f:
                chain_data = json.load(f)
                total_from_chains += chain_data["address_count"]

        with open(os.path.join(output_dir, "all_addresses.json")) as f:
            all_data = json.load(f)

        assert all_data["total_address_count"] == total_from_chains


class TestMetadata:
    def test_metadata_created(self, output_dir):
        path = os.path.join(output_dir, "metadata.json")
        assert os.path.exists(path)

    def test_metadata_schema(self, output_dir):
        with open(os.path.join(output_dir, "metadata.json")) as f:
            data = json.load(f)

        assert "last_checked" in data
        assert "last_updated" in data
        assert "source_list" in data
        assert "source_xml_url" in data
        assert "total_addresses" in data
        assert "total_unique_entities" in data
        assert "chains" in data
        assert "ofac_tickers_found" in data
        assert "schema_version" in data
        assert data["schema_version"] == "1.0.0"

    def test_metadata_counts_match(self, output_dir):
        with open(os.path.join(output_dir, "metadata.json")) as f:
            meta = json.load(f)

        with open(os.path.join(output_dir, "all_addresses.json")) as f:
            all_data = json.load(f)

        assert meta["total_addresses"] == all_data["total_address_count"]

    def test_metadata_chain_counts(self, output_dir):
        with open(os.path.join(output_dir, "metadata.json")) as f:
            meta = json.load(f)

        chains_dir = os.path.join(output_dir, "chains")
        for chain, count in meta["chains"].items():
            with open(os.path.join(chains_dir, f"{chain}.json")) as f:
                chain_data = json.load(f)
            assert chain_data["address_count"] == count


class TestEmptyChain:
    def test_empty_chain_produces_empty_array(self):
        """A chain with 0 addresses should produce a file with empty addresses array."""
        from src.categorize import CategorizedAddress
        with tempfile.TemporaryDirectory() as tmpdir:
            # Pass empty categorized dict with one empty chain
            categorized = {"ethereum": []}
            generate_output(categorized, output_dir=tmpdir)
            with open(os.path.join(tmpdir, "chains", "ethereum.json")) as f:
                data = json.load(f)
            assert data["addresses"] == []
            assert data["address_count"] == 0
