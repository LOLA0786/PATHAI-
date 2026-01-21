# PATHAI: India’s Digital Pathology Control Plane

Software-first platform for massive-scale digital pathology in India. Hybrid cloud+edge, offline-first for rural labs. Focus: WSI Viewer + IMS (PACS), AI App Store, Governance/Compliance moat.

## Architecture Principles
- **Modular/Plug-and-Play**: Each src/ subdir is self-contained with its own entrypoint.py, requirements (if unique), tests, and docs/module.md.
- **Self-Explanatory Code**: All files have docstrings, inline comments explaining WHY and HOW. No magic—explicit for 12-18+ month maintenance.
- **Scalability**: Cloud (AWS/GCP/Azure) + Edge (Docker/K8s for offline).
- **Compliance-First**: DPDP de-ID, encrypted vault, UAAL integration (from your prior repos).
- **Added Features**: Logging everywhere (structlog), monitoring hooks (Prometheus), extensible error handling.

## Quick Start
1. Install deps: `pip install -r requirements.txt`
2. Run viewer demo: `python src/viewer/entrypoint.py --help`

## Module Map
- **src/viewer**: Tile-based WSI viewer (OpenSlide streaming).
- **src/ims**: Ingestion/storage for SVS/NDPI/MRXS.
- **src/ai_app_store**: AI models (triage, quant) + GPU queue.
- **src/governance**: De-ID, audits, RBAC.
- **src/deployment**: Hybrid deploy, billing.
- **src/utils**: Shared (e.g., OCR for labels).

## Roadmap
Build step-by-step: Start with viewer/ims, add AI, then governance.

License: MIT (or your choice).
