# Immediate Next Step

The project is now ready for **source sampling**, not large-scale scraping.

Do not begin bulk ingestion until at least one Tier-1 market source has been validated on real payloads.

Required next outputs:

1. real sample payloads from The Odds API or equivalent multi-bookmaker historical source;
2. narrow Betfair historical soccer sample/package inspection;
3. Sportmonks/TXODDS sample or vendor confirmation of pricing/history/export options;
4. measured bookmaker/market coverage and timestamp semantics;
5. cost model for 1 season / 10 seasons / target scope.

Once one market source passes, Codex can take over the repetitive engineering loop: adapters, retries, normalization, bulk download, local storage, tests and data-quality reports.
