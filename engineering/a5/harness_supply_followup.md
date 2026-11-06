# A4 harness supply follow-up

**Observed 2026-11-05 UTC. Read-only procurement research; no vendor contact, reservation or order.** The frozen `io_service_audit.md/json` is unchanged. This follow-up resolves the exact Molex power-cable retail stock/price gap and records the limits of the JLC harness search.

## Procurement recommendation

Keep the current plug-in prototype architecture: **two Adafruit 4399 SH4 cables and one Molex 151340300 power cable per module**. **DigiKey has numeric stock for both exact cable assemblies exceeding the 100-module evaluation requirement.** This changes the verified purchasing route, not the selected cable geometry. A complete, stocked, equivalent 50 mm harness through JLC was not verified during the bounded search. This is a search result, not proof that JLC could never source it.

### Exact Molex power cable

The manufacturer's **151340300**, **15134-0300**, and **0151340300** are aliases for the same 50 mm, three-circuit, female-to-female PicoBlade assembly. The official product specifications identify 28AWG UL1061 wire and a 1 A contact rating. The already saved manufacturer drawing specifies 50±6 mm and **A1→B3 / A2→B2 / A3→B1**. The cable is complete, with crimped contacts installed in both housings; this is not a loose shell or individual precrimp lead.

| Supplier / exact order code | Live displayed stock | Single-unit price | Price for 100 | Evidence |
|---|---:|---:|---:|---|
| **DigiKey WM15252-ND** / 0151340300, US USD page | **17,783** | **$3.51000** | **$2.53650 each / $253.65** | Fresh anonymous product HTML, 20:45:47 UTC; web page independently refreshed |
| **DigiKey WM15252-ND**, Japan JPY page | **17,783** | **¥579** before JCT | **¥418.10 each / ¥41,810** before JCT | Refreshed product page; same shared stock, not an additional 17,783 |
| **Farnell 2671454** / 15134-0300, Japan | **5,224**, shown as UK stock | **¥793.62** before tax | **¥671.93 each / ¥67,193** before tax | Fresh anonymous product HTML, 20:45:00 UTC |

DigiKey is the preferred verified source in this comparison. The manufacturer's own Japan distributor page explicitly lists DigiKey among its e-commerce partners. Farnell supplies a second independent stock observation. The observations cover 100 required cables, but no stock has been reserved. Prices exclude shipping and applicable tax; USD and JPY displays are separate regional prices, not a currency conversion performed here. The manufacturer's production lead time is distinct from the distributor's displayed shelf stock.

Full DigiKey USD breaks from the fresh product page: 1 $3.51000; 10 $2.98500; 25 $2.79760; 50 $2.66380; 100 $2.53650; 250 $2.37768; 500 $2.26420; 1,000 $2.15618; 2,500 $2.02131. Molex's 100 mm and 150 mm relatives were not substituted: the existing 50 mm choice is available, and a longer cable would need its own routing check.

Sources:

- [Molex 151340300 official product page](https://www.molex.com/en-us/products/part-detail/151340300)
- [Molex official cable drawing](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/151/15134/151340303_sd.pdf)
- [DigiKey USD product page](https://www.digikey.com/en/products/detail/molex/0151340300/6198142)
- [DigiKey Japan product page](https://www.digikey.jp/en/products/detail/molex/0151340300/6198142)
- [Molex Japan authorized distributors and e-commerce partners](https://www.molex.com/ja-jp/contact-us/molex-japan-distributors)
- [Farnell Japan product page](https://jp.farnell.com/molex/15134-0300/-3-50mm/dp/2671454)

### SH4 lighting cables

The exact **Adafruit 4399** is also sold as **DigiKey 1528-4399-ND**. Fresh anonymous product HTML at **20:47:54 UTC** shows **12,957 In Stock** and **$0.95000 each**. The independently refreshed web page shows 12,963; the six-unit difference is retained as a live-source discrepancy, not combined into additional stock. Both observations exceed the required **200 cables for 100 modules**. The DigiKey page displays only the 1+ price, so planning arithmetic at that displayed price is **$190 for 200**; no unshown volume discount is assumed.

The original **direct Adafruit** offer remains a cheaper option: $0.95 at 1–9, $0.86 at 10–99 and $0.76 at 100+, or **$152 for 200**. Its page shows In Stock but publishes no numeric quantity, so immediate supply of 200 **from Adafruit directly remains unknown**. That channel limitation does not apply to the independently counted DigiKey stock. The existing manufacturer drawing still specifies 50±5 mm, two preterminated SH4 ends, and all four numbered cavities connected one-to-one.

For a single numerically stocked purchasing route through DigiKey, the displayed cable arithmetic is:

| Module count | SH4 cables | Molex power cables | Three-cable total, USD |
|---|---|---|---:|
| 1 | 2 × $0.95 | 1 × $3.51 | **$5.41** |
| 10 | 20 × $0.95 | 10 × $2.98500 | **$48.85** |
| 100 | 200 × $0.95 | 100 × $2.53650 | **$443.65** |

Buying the 200 SH4 cables at Adafruit's direct $0.76 tier instead would make the 100-module cable arithmetic **$405.65**, but that cheaper channel's numeric availability is unverified. All figures exclude the separate Eurorack ribbon, headers, tax, freight and additional harness items; none is a complete project quotation. No stock was reserved.

Sources: [DigiKey exact Adafruit 4399](https://www.digikey.com/en/products/detail/adafruit-industries-llc/4399/10824268), [Adafruit direct 4399](https://www.adafruit.com/product/4399). The manufacturer drawing remains in the frozen I/O audit.

## What JLC actually offers in the search results

The useful new candidate is **HanElectricity SH1.0-4P-1-100(3)-28A-UL1571 / C54529089**. Fresh anonymous JLC HTML at **20:45:16 UTC** shows **150 In Stock**, **150 Available Order Qty**, source JLCPCB, and Economic/Standard eligibility with the visible label **Wave Soldering**. Its first live tier is **$0.0826**, versus the stale search result's $0.0828. The 50+ live tier is $0.0807; the 150+ tier is $0.0795.

The actual linked product photograph was downloaded and visually inspected: **one four-position housing is crimped to four wires; the other ends are stripped/tinned**. Thus it is an assembled pigtail, not the two-ended 50 mm harness in the current BOM. The part name indicates a 100-length variant, but no dimensioned datasheet was available in the captured page, so its actual length tolerance and exact JST-mating qualification remain unverified. Product photos alone do not establish a footprint or connector fit.

A factory-soldered option could use such a pigtail on each leaf, then plug its housing into a controller header. That would require the factory to solder the bare ends, verify net/color order, provide strain relief and manage wire length/routing. JLC's published capability to solder library wire makes this a plausible **engineering-review and labor-quote option**, not an approved replacement. At two per module, the currently displayed 150 units cover at most 75 modules before attrition, below the 100-module evaluation requirement. The current four-header/two-premade-cable BOM is therefore retained.

JLC searches also returned SH-family SMT headers and the different Molex **15134-0505 / C18118584**. Neither establishes availability of the exact required power cable. A housing, board connector or wrong-circuit cable must not be counted as a ready-made replacement. No stocked exact 151340300/0151340300 JLC C-number was verified. JLC product pages also state that parts-library purchases are for PCBA and cannot be shipped separately; a library listing alone would not prove that loose harnesses can accompany the shipment.

Sources: [JLC C54529089](https://jlcpcb.com/partdetail/C54529089), [different JLC Molex cable entry](https://jlcpcb.com/partdetail/MOLEX-151340505/C18118584), [JLC international assembly capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities).

## Evidence handling

`harness_supply_followup.json` contains the compact observations, price tiers, source URLs and SHA-256 provenance. Supporting fresh captures and the inspected pigtail photo are in `harness_evidence`. Raw public HTML is intermediate evidence and need not be included in the delivery ZIP. No existing stock or price field in the frozen I/O audit was overwritten.
