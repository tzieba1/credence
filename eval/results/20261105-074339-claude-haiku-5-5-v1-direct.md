## claude-haiku-5-5, prompt v1, direct

18 cases, 15 fully correct (0.83), 0 failed calls. Total $0.0092, $0.0005 per document, latency p50 2202 ms, max 3606 ms.

| model | prompt | impl | issuer | holder | number | issue | expiry | scope | signatory | doc | $/doc | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | v1 | direct | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.89 | 0.94 | 0.83 | 0.0005 | 2202 |

| field | accuracy | present precision | present recall | wrong cases |
|---|---|---|---|---|
| issuer | 1.00 | 1.00 | 1.00 | - |
| holder | 1.00 | 1.00 | 1.00 | - |
| certificate_number | 1.00 | 1.00 | 1.00 | - |
| issue_date | 1.00 | 1.00 | 1.00 | - |
| expiry_date | 1.00 | 1.00 | 1.00 | - |
| scope | 0.89 | 1.00 | 1.00 | g06-letter-en-no-signatory, g13-scan-letter-fr-no-signatory |
| signatory | 0.94 | 1.00 | 1.00 | g02-classic-en-long |

| case | wrong fields | predicted | gold | failure |
|---|---|---|---|---|
| g02-classic-en-long | signatory | 'Samuel Achterberg' | 'Dr Samuel Achterberg' | - |
| g06-letter-en-no-signatory | scope | 'Operation of wastewater treatment works at Tern Valley.' | 'Operation of wastewater treatment works at Tern Valley' | - |
| g13-scan-letter-fr-no-signatory | scope | 'Construction et réparation de coques en acier.' | 'Construction et réparation de coques en acier' | - |
