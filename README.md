# OFAC Naughty List

The U.S. Treasury's Office of Foreign Assets Control (OFAC) publishes sanctioned digital currency addresses as part of its [Specially Designated Nationals (SDN) list](https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists). This data is freely available — but it's buried inside a ~120MB XML file alongside thousands of non-crypto sanctions entries, with no separation by blockchain network.

Commercial services like Chainalysis charge significant fees to provide this same public data in a usable format. **This tool does it for free.** It downloads the official OFAC SDN Advanced XML, parses out every "Digital Currency Address" feature along with entity metadata (name, sanctions programs, listing date), infers the blockchain network from address format and ticker context, and publishes structured, per-chain JSON files — updated daily and committed directly to this repository.

Inspired by [0xB10C/ofac-sanctioned-digital-currency-addresses](https://github.com/0xB10C/ofac-sanctioned-digital-currency-addresses), which organizes addresses by ticker symbol (ETH.txt, XBT.txt, USDT.txt). This project takes a different approach: organizing by **chain** (ethereum.json, bitcoin.json, tron.json) — which is what compliance engines and on-chain screening tools actually need. A USDT address on Tron and a USDT address on Ethereum require different screening logic, and this tool handles that distinction automatically.

## What it does

- **Downloads** the [SDN Advanced XML](https://www.treasury.gov/ofac/downloads/sanctions/1.0/sdn_advanced.xml) (~120MB) from OFAC daily
- **Extracts** all digital currency addresses by scanning the XML's `FeatureType` reference table for "Digital Currency Address" entries, then matching each `Feature` on sanctioned entity profiles to its ticker and address value
- **Resolves multi-chain tokens** like USDT and USDC (which exist on Ethereum, Tron, BSC, etc.) by inferring the correct chain from address format — a `0x` prefix means EVM, a `T` prefix means Tron, etc.
- **Publishes** per-chain JSON files with full entity metadata, ready for direct integration into compliance pipelines, smart contract allowlists, or monitoring dashboards

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

## Current sanctions snapshot

> Last updated: **2026-03-23** | **772 addresses** across **83 sanctioned entities**

| Chain | Addresses | Last Added | File |
| ----- | --------: | ---------- | ---- |
| Bitcoin | 521 | 2026-03-12 | `data/chains/bitcoin.json` |
| Tron | 124 | 2026-03-12 | `data/chains/tron.json` |
| Ethereum | 91 | 2026-03-12 | `data/chains/ethereum.json` |
| Litecoin | 10 | 2024-09-26 | `data/chains/litecoin.json` |
| Monero | 8 | 2025-03-04 | `data/chains/monero.json` |
| Bitcoin Cash | 7 | 2022-11-09 | `data/chains/bitcoin_cash.json` |
| Dash | 3 | 2021-04-15 | `data/chains/dash.json` |
| Zcash | 3 | 2021-04-15 | `data/chains/zcash.json` |
| Bitcoin Gold | 1 | 2020-09-16 | `data/chains/bitcoin_gold.json` |
| Bitcoin SV | 1 | 2020-09-10 | `data/chains/bitcoin_sv.json` |
| Ripple | 1 | 2021-11-08 | `data/chains/ripple.json` |
| Solana | 1 | 2025-11-19 | `data/chains/solana.json` |
| Verge | 1 | 2021-04-15 | `data/chains/verge.json` |

Additional supported chains (no explicit sanctions): Arbitrum, BSC, Ethereum Classic. Note that EVM addresses sanctioned on Ethereum are valid on all EVM-compatible chains — an address flagged on Ethereum should be treated as sanctioned on Arbitrum, BSC, etc. as well. Check the `evm_compatible` field in the output to identify these addresses.

Addresses that can't be mapped to a known chain are placed in `data/chains/unknown.json`.

## Output schema

Each per-chain JSON file contains:

```json
{
  "chain": "ethereum",
  "source_list": "SDN",
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

Timestamps are centralized in `data/metadata.json`:
- `last_checked`: when the OFAC source was last checked for updates
- `last_updated`: when addresses were last added or removed from the list

See `data/metadata.json` for aggregate statistics and schema version.

## How it works

1. **Daily cron** (00:00 UTC) triggers the update (GitHub Actions or Railway)
2. **Download** the SDN Advanced XML (~120MB) from OFAC
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

## Deploying on Railway

Railway can run this as a daily cron job that automatically commits updated data back to GitHub.

### Setup

1. **Create a GitHub Personal Access Token** with `contents: write` permission scoped to this repository. Go to GitHub Settings > Developer settings > Fine-grained personal access tokens.

2. **Create a new Railway project** at [railway.com](https://railway.com):
   - Click **New Project** > **Deploy from GitHub repo**
   - Select this repository
   - Railway will auto-detect the `Dockerfile` and `railway.json`

3. **Set environment variables** in the Railway service settings:

   | Variable | Value | Description |
   | -------- | ----- | ----------- |
   | `GITHUB_TOKEN` | `ghp_...` | GitHub PAT with repo write access |
   | `GITHUB_REPO` | `cylon56/ofac-naughtylist` | Owner/repo format |
   | `GITHUB_BRANCH` | `main` | Branch to push updates to |

4. **Verify cron schedule**: Railway will read `railway.json` and configure the service as a cron job running daily at 00:00 UTC. You can adjust the schedule in the Railway dashboard under Settings > Cron Schedule.

5. **Test manually**: Trigger a one-off run from the Railway dashboard to verify the pipeline works end-to-end.

### Pipeline

The `scripts/railway_cron.py` script:

1. Clones the repo (shallow) using the GitHub token
2. Runs the full OFAC pipeline
3. Commits and pushes any data changes back to the repository

### Cost

This runs as a cron job (not an always-on service), so you only pay for the ~2-3 minutes of compute per daily run. Railway's free tier is usually sufficient.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The main contribution surface is `config/chain_mapping.yaml` for adding new chains and tickers.

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md). This tool is NOT a substitute for a comprehensive sanctions compliance program.

## License

[MIT](LICENSE)
