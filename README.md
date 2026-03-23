# ofac-naughtylist

> "We have Chainalysis at home."

An open-source tool that automatically extracts, categorizes, and publishes OFAC-sanctioned digital currency addresses organized by blockchain network. Runs as a daily GitHub Actions cron job, parses the official OFAC SDN Advanced XML file, infers the blockchain chain from address format, and commits structured JSON output directly to the repository.

Unlike [0xB10C/ofac-sanctioned-digital-currency-addresses](https://github.com/0xB10C/ofac-sanctioned-digital-currency-addresses) which organizes by ticker (ETH.txt, XBT.txt, USDT.txt), this tool categorizes by **chain** (ethereum.json, bitcoin.json, tron.json) — which is what compliance engines and on-chain screening tools actually need.

## Quick start

Fetch the latest sanctioned addresses for any chain:

```bash
# Ethereum addresses
curl https://raw.githubusercontent.com/cylon56/ofac-naughtylist/main/data/chains/ethereum.json

# Bitcoin addresses
curl https://raw.githubusercontent.com/cylon56/ofac-naughtylist/main/data/chains/bitcoin.json

# All addresses across all chains
curl https://raw.githubusercontent.com/cylon56/ofac-naughtylist/main/data/all_addresses.json
```

## Supported chains

| Chain | File |
|-------|------|
| Ethereum | `data/chains/ethereum.json` |
| Bitcoin | `data/chains/bitcoin.json` |
| Tron | `data/chains/tron.json` |
| Arbitrum | `data/chains/arbitrum.json` |
| BSC | `data/chains/bsc.json` |
| Litecoin | `data/chains/litecoin.json` |
| Monero | `data/chains/monero.json` |
| Zcash | `data/chains/zcash.json` |
| Dash | `data/chains/dash.json` |
| Bitcoin Cash | `data/chains/bitcoin_cash.json` |
| Bitcoin SV | `data/chains/bitcoin_sv.json` |
| Bitcoin Gold | `data/chains/bitcoin_gold.json` |
| Ethereum Classic | `data/chains/ethereum_classic.json` |
| Ripple | `data/chains/ripple.json` |
| Verge | `data/chains/verge.json` |

Addresses that can't be mapped to a known chain are placed in `data/chains/unknown.json`.

## Output schema

Each per-chain JSON file contains:

```json
{
  "chain": "ethereum",
  "source_list": "SDN",
  "last_updated": "2026-03-23T00:00:00Z",
  "source_xml_url": "https://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml",
  "address_count": 312,
  "addresses": [
    {
      "address": "0x7F367cC41522cE07553e823bf3be79A889DEbe1B",
      "ofac_tickers": ["ETH"],
      "evm_compatible": false,
      "entity_id": 39498,
      "entity_name": "LAZARUS GROUP",
      "programs": ["CYBER2", "DPRK3"],
      "date_listed": "2022-04-14",
      "source_feature_ids": [52341]
    }
  ]
}
```

See `data/metadata.json` for aggregate statistics and schema version.

## How it works

1. **Daily cron** (00:00 UTC) triggers the GitHub Actions workflow
2. **Download** the SDN Advanced XML (~80MB) from OFAC
3. **Parse** XML to extract all "Digital Currency Address" features with entity metadata
4. **Categorize** each address by chain using ticker mapping + address format inference
5. **Generate** per-chain JSON files, combined file, and metadata
6. **Commit** changes to `data/` if anything changed

## Running locally

Requires Python 3.11+.

```bash
git clone https://github.com/cylon56/ofac-naughtylist.git
cd ofac-naughtylist
pip install -r requirements.txt

# Run full pipeline (downloads ~80MB XML from OFAC, writes to data/)
python -m src.main

# Run with a local XML file (skip download)
python -m src.main --xml ./sdn_advanced.xml

# Write output to a custom directory
python -m src.main --output-dir ./my-output

# Verbose logging (shows discovered tickers, parse progress)
python -m src.main -v

# See all options
python -m src.main --help
```

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

The test suite uses a small hand-crafted XML fixture (`tests/fixtures/sample_sdn_advanced.xml`) covering multi-ticker deduplication, multi-chain token inference, unknown ticker fallback, and all supported address formats. No network access required.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The main contribution surface is `config/chain_mapping.yaml` for adding new chains and tickers.

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md). This tool is NOT a substitute for a comprehensive sanctions compliance program.

## License

[MIT](LICENSE)
