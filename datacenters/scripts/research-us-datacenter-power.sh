#!/usr/bin/env bash
# Preview by default. Run a bounded, resumable Kimi batch and publish audited profiles locally.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

mode="${1:-preview}"
limit="${2:-25}"
if [[ "$mode" != preview && "$mode" != run ]] || [[ ! "$limit" =~ ^[0-9]+$ ]] || ((limit < 1 || limit > 100)); then
  echo "Usage: bash datacenters/scripts/research-us-datacenter-power.sh [preview|run] [1-100 facilities]" >&2
  exit 2
fi
research_dir=datacenters/research/worldwide-datacenters
python3 datacenters/prepare_worldwide_datacenter_enrichment.py
preview_args=()
if [[ "$mode" == preview ]]; then preview_args+=(--dry-run); fi
python3 datacenters/research_inventory_with_kimi.py \
  --profile worldwide-datacenter-power \
  --input "$research_dir/enrichment-input.json" \
  --checkpoint "$research_dir/kimi-power-research.jsonl" \
  --events "$research_dir/kimi-power-events.jsonl" \
  --country US --priority 1 --limit "$limit" --workers 2 \
  --primary-minimum-searches 2 --max-searches 6 --max-tier retry \
  --verbose "${preview_args[@]}"
if [[ "$mode" == preview ]]; then exit 0; fi
python3 datacenters/audit_kimi_research.py \
  --profile worldwide-datacenter-power \
  --inventory "$research_dir/enrichment-input.json" \
  --checkpoint "$research_dir/kimi-power-research.jsonl" \
  --output "$research_dir/kimi-power-audit.jsonl" \
  --repair-queue "$research_dir/kimi-power-repair-queue.json" \
  --review-queue "$research_dir/kimi-power-review-queue.json" \
  --judge --workers 4 --judge-workers 2
python3 datacenters/promote_worldwide_datacenter_enrichment.py \
  --audit "$research_dir/kimi-power-audit.jsonl" --apply
