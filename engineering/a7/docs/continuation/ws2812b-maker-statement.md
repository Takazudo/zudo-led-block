# WS2812B-2020-V6 T1L: unverified maker statement on #13

Status: **UNVERIFIED MAKER STATEMENT**. This is not a datasheet fact and does not change any value printed in the V1.4 datasheet. It is recorded so that the T1L owner decision (`criterion:firmware-waveforms`) can cite it.

## Record

- Where: issue #13 comment, https://github.com/Takazudo/zudo-led-block/issues/13#issuecomment-6811489780
- Author login: `YinHuaPing`. GitHub `author_association`: `NONE`, so the account has no visible link to Worldsemi. The comment signs as "Yin from Worldsemi"; this identity is not verified.
- Created: 2026-11-12T01:17:18Z (not edited as of retrieval)
- Retrieved: 2026-11-12 through the public GitHub REST API (`/repos/Takazudo/zudo-led-block/issues/comments/6811489780`)
- SHA-256 of the UTF-8 comment body below: `e2ce2695be81c441b8093cd41519bbacafcf105e9f6e1a9c5d9df1aa728fb6fd`

## What was checked

- **Datasheet identity (verified).** The owner forwarded the file `ws2812b-2020-v6-1.0.pdf`. It is 1264070 bytes with SHA-256 `b09737faa695f6acca16612d3da658da6692fbf4366047083dad84809d452bca`, byte-identical to the V1.4 English datasheet already recorded (`src-ws2812b-2020-v6-ds-p*`). On 2026-11-12 the cloud VM downloaded https://www.world-semi.com/downloads/datasheets/en/ws2812b-2020-v6-1.0.pdf (HTTP 200, application/pdf) and got the same SHA-256. No source, fact or printed value changes. The T1L row stays 580–1000 ns, and Topt stays −40 to +85 °C.
- **"No newer public revision than V1.4" (not verifiable here).** It is consistent with the live download, but absence of a newer revision cannot be proved from the cloud. The product page https://www.world-semi.com/products/ws2812b-2020-v6.html reset the connection on 2026-11-12.
- **Timing guidance (not in any Worldsemi document).** The statement says Worldsemi judges compatibility by T0H (about 325 ns, upper limit 380 ns) and the bit period (about 1250 ns, 800 kHz), and does not use T0L/T1L as a pass/fail limit. Neither the V1.4 nor the V1.0 datasheet says this. The T0H upper limit of 380 ns agrees with the printed T0H row (220–380 ns).
- **Current A5 firmware against the stated guidance (calculation only).** The A5 timing record (`engineering/a5/firmware/dist/timing.md`) gives T0H 339.806–360.825 ns and bit cell 1262.136–1340.206 ns over a ±3 % clock. The T0H range satisfies the stated T0H ≤ 380 ns. The cell is 1.0–7.2 % longer than the stated 1250 ns nominal and satisfies the printed TDATA ≥ 1.25 µs, but the statement gives no tolerance for the period, so whether it meets the stated period criterion cannot be decided from the statement. The firmware's low time (339.806–360.825 ns) still fails the printed T1L row. Nothing was measured.

## Use

- The statement may be offered as an option in the T1L owner decision, labelled unverified.
- Adopting it as the pass criterion needs written confirmation through an official Worldsemi channel, obtained by the owner. This project does not contact suppliers.
- It does not replace the waveform measurement on the purchased lot (`firmware-waveforms`), and it says nothing about a particular lot.
- No reply has been posted on #13.

## Comment body (verbatim)

```text
Hi, I’m Yin from Worldsemi.

Thank you for documenting the WS2812B-2020-V6 evidence so carefully.

The current official English datasheet is available here:
- Product page: https://www.world-semi.com/products/ws2812b-2020-v6.html
- PDF: https://www.world-semi.com/downloads/datasheets/en/ws2812b-2020-v6-1.0.pdf

Although the download filename is ws2812b-2020-v6-1.0.pdf, this is the current public file. The revision history in the document goes to V1.4. Its SHA-256 is b09737faa695f6acca16612d3da658da6692fbf4366047083dad84809d452bca, which matches the V1.4 English datasheet already in this repository. At this time there is no newer public revision than V1.4.

Regarding the T1L values discussed in this issue: for our RZ protocol, the parameters we use for compatibility are the zero-code high time (T0H) and the total bit period. We do not treat the low time (T0L / T1L) as a compatibility criterion. Therefore, both the T1L row printed in the V1.4 datasheet (580 ns–1 µs) and a shorter low time in the 220–420 ns range used by common firmware can work. This difference alone does not indicate a compatibility problem.

For practical implementation, we recommend:
- T0H ≈ 325 ns, with an upper limit of 380 ns
- bit period ≈ 1250 ns (800 kHz)

The low interval is used to complete the bit period and is not a pass/fail limit that we ask implementers to tighten.

Please feel free to use the official links above as the manufacturer source.
```
