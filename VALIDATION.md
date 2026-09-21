# Integration validation — 2026-09-21

Latest integration combines main e39c214 with customer-credit fixes d47d990.
Local Windows validation on isolated temporary databases:
- 53 unittest regression tests passed (sales, purchases, stock, pricing, credit, returns, backup, search, statistics).
- ui_smoke.py passed: login, scan, quantity, navigation including statistics, direct stock correction and ledger.
- ui_acceptance.py passed: product/family, supplier, purchase validation, stock, scan, quantity, discount, visible SOLDER/VALIDER at 1100x640, payment, receipt PDF, journal, credit deposit and settlement.
- ui_integration.py passed: 30 families, inline creation, multi-family save/reopen/remove, colour/icon editor, sale family buttons, all three statistics periods, discounted sale and partial return, negative net revenue and navigation.

Receipt PDF generation is tested; physical printing, thermal layout, Arabic receipt rendering, scanner hardware and cash drawer are not verified. No production/shop data was used or changed by these tests.
The optional TEST_TODO.bat demo uses a separate demo database. It is not a production database.

The following is historical baseline evidence; its earlier Tk/CI limitations are superseded by the local integration results above. CI results for the final commit must be checked separately.

---

# Validation ? ToDo POS 1.1.0

Executed on 2026-09-19, Windows, bundled Python 3.12.14, SQLite 3.53.1, local temporary databases.

## Automated checks

- 28 unittest regression tests passed (also discoverable by pytest).
- Coverage includes discounted/partial/duplicate returns, rollback of sale and stock, stock policy, free items, fractional quantities, pack and quantity pricing, held-ticket discount and lifecycle, closed cash sessions, live WAL backups, restore/rejection of invalid backup, barcode ambiguity, search, stock actor, role restrictions, purchases, salted/legacy PINs, cash movements, report totals and legacy migration.
- Legacy schema upgraded with a pre-migration backup; old discounted sale refunded at its net value; repeated migration preserved the data.
- All Python sources parsed successfully.
- SQLite stock updates in application source are centralized in services/inventory.py. Product creation starts from zero; its entered stock produces a ledger movement.

## Performance sample

100,000 synthetic products and 100,000 barcodes. Median timings, including connection setup:

| Operation | Median | Maximum in sample |
| --- | ---: | ---: |
| Exact reference | 5.38 ms | 7.64 ms |
| Name substring | 37.94 ms | 42.57 ms |
| Alias | 38.05 ms | 48.10 ms |
| Exact barcode through search | 6.20 ms | 11.29 ms |
| Two-character search | 5.59 ms | 9.02 ms |
| Scanner barcode lookup | 4.79 ms | 7.96 ms |
| Commit 100-item sale | 77.60 ms | 115.00 ms |

12 repetitions for lookups; 5 for sale commits. Full raw results in BENCHMARK_RESULTS.json. Run `python -B tests/benchmark.py` to reproduce locally. Performance varies with hardware, data distribution and SQLite build. Trigram FTS is used when available; older SQLite builds fall back to LIKE. These are backend timings, not GUI latency, startup, printer latency or scanner hardware tests.

## Not verified here

Tk initialization failed in the provided runtime because its Tcl loader could not access init.tcl even though Python could read the file. UI smoke testing was attempted but did not run past Tk initialization. `python -B tests/ui_smoke.py` is provided for an environment with working Tk; it checks login, scan/add, quantity, navigation and direct product-stock editing with a ledger entry. It is not a substitute for visual QA.

The complete UI, screen sizes, right-to-left display, product thumbnails, physical scanner, cash drawer and printer require testing on the target Windows machine. First start under two seconds and full visual scan latency have not been measured. This release is a test candidate, not a claim of full production acceptance.

GitHub Actions configuration is included for core tests on Windows/Ubuntu and Python 3.10/3.12. It has not been executed on GitHub in this task.
