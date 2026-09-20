# Prototype Contract Corpus

The prototype does not use CUAD because it is a US-law contract dataset. The current demo contracts are the Indian-law scenarios seeded in `contracts.db` and the test fixtures.

The Indian legal grounding source is documented in `raw/open-india-law-readme.md`. It contains judgments and legislation, not commercial contract inputs. Use a small selected statutory subset at runtime rather than downloading the complete corpus.

## Official Indian contract PDFs

The demo corpus includes official Indian public-private partnership agreements from the Government of India's PPP portal:

- `official/model_concession_4_laning.pdf` — Model Concession Agreement for 4-laning of National Highways.
- `official/pune_metro_signed_concession.pdf` — Signed Pune Metro concession agreement.

Source index: https://www.pppinindia.gov.in/model_concession_agreement and https://www.pppinindia.gov.in/signed_concession_agreements

These are government-hosted public documents and should remain attributed to the PPP India portal. They are infrastructure concession agreements, so they are suitable for ingestion and cross-clause demonstrations but are not a representative benchmark of all Indian commercial contracts.

PDF inputs are converted with PyMuPDF. Scanned pages use the local Tesseract OCR fallback when available. To create a Markdown extraction:

```bash
venv/bin/python scripts/pdf_to_markdown.py path/to/contract.pdf output/contract.md
```