# Official DEXPI 2.0.1 reference fixture

`reference_pid.xml` and `DEXPI_XML_Schema.xsd` are unmodified copies from the
DEXPI Initiative's Specification repository, tag `V2.0.1`, commit
`eef0f0c6e8edfe84582e7a45d109c396bdc544f8`.

Copyright DEXPI Initiative. Licensed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
The upstream [copyright/license declaration](https://gitlab.com/dexpi/Specification/-/blob/eef0f0c6e8edfe84582e7a45d109c396bdc544f8/src/documentation/index.rst)
applies to this reference material; Tuba's own source license is unchanged.

| File | Pinned upstream source | SHA-256 |
| --- | --- | --- |
| `reference_pid.xml` | [Reference P&ID](https://gitlab.com/dexpi/Specification/-/raw/eef0f0c6e8edfe84582e7a45d109c396bdc544f8/src/documentation/_static/reference_pid.xml) | `acd39c74292aef3f6f00581fc78b05814acf2318815abd28c14ebefba12fdd94` |
| `DEXPI_XML_Schema.xsd` | [XML schema](https://gitlab.com/dexpi/Specification/-/raw/eef0f0c6e8edfe84582e7a45d109c396bdc544f8/src/documentation/_static/DEXPI_XML_Schema.xsd) | `0bd6568b7c52fd59ac4ef6d8547ab2b2aa890c009a3a1bfbc5d7cc18c53b36e6` |

The example selects `PipingNetworkSegment2`: `Pipe2` connects
`Nozzle2` / `PipingNode3` on pump `P4711` to `Nozzle3` / `PipingNode4` on
heat exchanger `H1007`. The original line number, DN80, fluid code `MNb` and
piping class `75HB13` remain source metadata. The complete XML is retained so
the omitted plant context remains reviewable.

The Tuba example supplies a **separate demonstration water scenario**, physical
route, steel section, roughness, bend losses and supports. It does not simulate
the original plant service, pump or heat exchanger. No physical dimensions are
inferred from the diagram's drawing coordinates. See the
[process-network guide](../../../docs/content/process-networks.md).

The pinned fixture was checked against its pinned XSD locally. The importer
itself validates its explicitly supported segment profile, not the complete
DEXPI schema and semantic model, and never fetches XML imports or schemas.
