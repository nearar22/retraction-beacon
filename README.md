# Retraction Beacon

Scientific citations can outlive the notices that invalidate them. Retraction Beacon stores a DOI once, then lets anyone refresh its publication status from two separately attributed authorities: the publisher and an independent scholarly registry.

The contract answers a narrow question: **what notice currently applies to this exact DOI, and which quoted evidence supports that status?** It does not rate research quality and it never treats silence on one page as proof that a paper is clean.

## The state machine

```text
create_record → MONITORING
                   │
                   ├─ refresh_status → revision 1..6 + source receipts
                   │                    previous revision moves to history
                   │
                   └─ archive_record → ARCHIVED
                        only owner + RETRACTED/CORRECTED result
```

Refreshes are permissionless and separated by a six-hour cooldown. The owner cannot rewrite an older result; each successful refresh receives a deterministic revision receipt. A terminal notice can be archived once, producing a receipt over the complete history.

## What validators decide

The two frozen source bodies are classified as one of:

- `RETRACTED`
- `CORRECTED`
- `EXPRESSION_OF_CONCERN`
- `NO_NOTICE`
- `UNCERTAIN`
- `SOURCE_UNAVAILABLE`

A retraction is deliberately hard to assert. Both source indexes must bind the exact DOI or unambiguous title, both must contribute exact quotes, severity must be at least 80, and the action must be `DO_NOT_CITE`.

## Consensus and deterministic guardrails

1. The contract validates normalized DOI syntax, public HTTPS URLs, and different hosts.
2. Validators retrieve the publisher and registry pages inside `strict_eq`; the content, host, URL, index, availability, and SHA-256 digest are frozen before interpretation.
3. `prompt_non_comparative` receives deterministic JSON input. Its callback performs no LLM call.
4. Independent validators re-check DOI binding, status type, date, action, severity, and quote support.
5. Deterministic code rejects unknown fields, forged quotes, duplicate evidence, wrong source indexes, unsupported terminal claims, and substantive output when a source is unavailable.
6. State changes occur only after consensus returns successfully.

## Local verification

```bash
npm install
genvm-lint contracts/retraction_beacon.py
pytest -q
```

The direct suite covers DOI normalization, duplicate IDs, URL boundaries, permissionless refresh, cooldown enforcement, revision history, owner-only archive, terminal-state enforcement, replay rejection, numeric normalization, and forged evidence rejection.

## Demo evidence warning

`demo/` contains synthetic, operator-controlled fixtures. They are mirrored on two hosts only to exercise live retrieval and consensus; they are not independent real-world authorities and must never be presented as evidence about an actual paper. A production caller is responsible for selecting the genuine publisher and an institutionally independent registry.

## Studio Next

- Chain ID: `61997`
- RPC: `https://studio-next.genlayer.com/api`

Deployment and live lifecycle evidence are added only after the exact reviewed source is deployed and exercised successfully.

### Reviewed deployment

- Contract: `0x2C22A0607655603E49EBe71e7d64857832fB1dDd`
- Deployment transaction: `0x83c70a18ab6131fb82675480b5377b162975b5608a94024f0e53ec1852037229`
- Reviewed source commit: `1f66276a1d8170d51514b5f40dbf51257eefd868`
- Result: `FINISHED_WITH_RETURN` / `MAJORITY_AGREE`

### Live lifecycle proof

- Record: `retraction-mwifd0a2`
- Create: `0x5c2320e01a601216c56e5b2c8b2346908028652df5a94ab5593837eccac822ee`
- Intelligent refresh: `0xf042a87071aa20ac588a216229e24e0a716674d5884e68fc0d829e3648732098`
- Archive: `0xf0b9a0377291a2cfe1eec4b0e5e4992248b270bc12a6d4ad614c931d2d75326f`
- Final state: `ARCHIVED` / `RETRACTED` / `DO_NOT_CITE`
- Archive receipt: `dc2e55c94edec41edadce355252af3e415024c3886034e2f22b8dfe1f2dc9639`

