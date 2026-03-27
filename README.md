![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg)

# DNA Codon Translator

If we wanted to be fancy, we can call this a silicon ribosome. But it's honestly just a cool LUT with some tricks and book keeping.

Cells translate RNA into proteins using ribosomes. This chip does the same process, just with opinionated verilog.
You put in a stream of 2-bit nucleotides, and digital logic will group them into codons, look up the matching amino acid, and track open reading frames.

This happens synchronously and we handle one codon for every three shift-enable pulses.

## Quick Biology Background

DNA gets transcribed into mRNA (to act as a working copy used to make proteins). The ribosome reads that mRNA three nucleotides at a time. Each of these triplets are referred to as **codons**, with each codon mapping to one of 20 possible amino acids (or a stop signal). That mapping is known as the **standard genetic code**, a 64-entry lookup table that all known life shares.

We focus on implementing this table while also making sure to track open reading frames (ORF). Translation starts at AUG (methionine, the start codon) and will run until a stop codon (UAA, UAG, or UGA) shows up.

## Architecture

We can break the whole thing down into three blocks:

**Shift register and counter**: A 4-bit shift reg takes the first two nucleotides of each codon while a 2-bit counter (`nuc_cnt`) tracks position 0, 1, or 2 within that triplet. When the third nucleotide comes in, the full 6-bit codon gets latched to `codon_q`. When this happens, `codon_rdy` pulses high for a cycle.

**A LUT for the codons**: This is just what it sounds like. A combinational module maps 6-bit codons to 5-bit amino acid indices (0–19 for the amino acids, 20 for stop). What is really cool about this though is that instead of a flat 64-entry case statement, we can be smart here and exploit the degeneracy structure of the genetic code. Doing this saves a lot on gate count. This is how it's done:

The genetic code is redundant by design. 64 codons map to only 21 outputs (20 amino acids + stop), so many codons that share a two-nucleotide prefix produce the same result. We exploit this in three possible situations.

- **Four-fold degenerate** (8 prefixes): In this case, the third nucleotide is completely irrelevant. Take Alanine for example. All four of GC\* produce this. The LUT only needs to check the first four bits and can throw away the rest. This covers GC\*(Ala), CG\*(Arg), GG\*(Gly), CU\*(Leu), CC\*(Pro), UC\*(Ser), AC\*(Thr), and GU\*(Val).

- **Two-fold degenerate** (6 prefixes): This is where the third nucleotide *almost* doesn't matter. This will depend on whether it's a purine (A/G, bit 0 = 0) or a pyrimidine (U/C, bit 0 = 1). So a single "wobble bit" resolves the pair. For instance, CA + purine = Glutamine, CA + pyrimidine = Histidine.

- **Irregular** (2 prefixes): AU\* and UG\* break this pattern and will need full 6-bit decode. AUG is Methionine (and the start codon), while AUU/AUC/AUA are all Isoleucine. UGA is a stop codon, UGG is Tryptophan, and UGU/UGC are Cysteine.

With this in mind, instead of having to handle 64 case branches, the `codon_lut` module only handles 16.

**ORF tracker**: This is pretty important. Without it, all this data would be meaningless. We watch the translated stream for AUG (start) and stop codons. `orf_open` goes high when a start codon is seen and drops when a stop codon appears. We track how many codons have been translated since the last reset with a saturating 4-bit counter that maxes out at 15.

## Nucleotide Encoding

| Symbol | Bits |
|--------|------|
| A | `00` |
| C | `01` |
| G | `10` |
| U | `11` |

## Pin Interface

### Inputs (`ui_in`)

| Bits | Signal | Description |
|------|--------|-------------|
| [1:0] | `nuc_data` | 2-bit nucleotide value |
| [2] | `shift_en` | Accept nucleotide on rising clock edge |
| [3] | `frame_rst` | Clear all states |
| [7:4] | `N/A` | Unused |

### Outputs (`uo_out`)

| Bits | Signal | Description |
|------|--------|-------------|
| [4:0] | `amino_idx` | Amino acid index (0–19) or stop (20) |
| [5] | `is_stop` | Flag when the current codon is a stop |
| [6] | `codon_rdy` | One cycle pulse when a codon is fully translated |
| [7] | `orf_open` | High while inside a start to stop reading frame |

### Bidirectional (`uio_out`, active as outputs)

| Bits | Signal | Description |
|------|--------|-------------|
| [1:0] | `nuc_cnt` | Current nucleotide position in the codon (0, 1, or 2) |
| [5:2] | `codon_num` | Number of codons translated since reset (saturates at 15) |
| [7:6] | `N/A` | Unused |

## Amino Acid Index Reference

| # | Amino Acid | Code | | # | Amino Acid | Code |
|---|------------|------|-|---|------------|------|
| 0 | Alanine | A | | 10 | Leucine | L |
| 1 | Arginine | R | | 11 | Lysine | K |
| 2 | Asparagine | N | | 12 | Methionine | M |
| 3 | Aspartate | D | | 13 | Phenylalanine | F |
| 4 | Cysteine | C | | 14 | Proline | P |
| 5 | Glutamine | Q | | 15 | Serine | S |
| 6 | Glutamate | E | | 16 | Threonine | T |
| 7 | Glycine | G | | 17 | Tryptophan | W |
| 8 | Histidine | H | | 18 | Tyrosine | Y |
| 9 | Isoleucine | I | | 19 | Valine | V |
| | | | | 20 | Stop | * |


## Testing

The cocotb testbench lives in `test/test.py`. 
Feel free to run it yourself with `make` inside the `test/` directory.

**test_reset**: All outputs zero after reset.

**test_all_64_codons**: Every single codon in the standard genetic code. Checks amino acid index, stop flag, and ready signal for all 64. This is the main one that focuses on functional correctness.

**test_orf_tracking**: We feed AUG -> GCU -> UAA and verify that `orf_open` rises on the start codon and falls on the stop.

**test_frame_reset**: Shift a partial codon (2 nucleotides), hit `frame_rst`, and confirm that the reading frame and codon counter both zero out cleanly. Then we translate a fresh codon to make sure nothing's broken.

**test_codon_counter**: Translate 17 consecutive codons and check that the 4-bit counter increments correctly then saturates at 15.

**test_biological_sequence**: Another sanity check. We translate a real peptide end to end: Met -> Trp -> Phe -> Stop.

**test_continuous_streaming**: Nucleotides get shifted every single clock cycle with zero idle gaps. Confirms the design handles back-to-back operation without choking.

## External Hardware

None required. Nucleotide sequences go in through `ui_in` with amino acid translations coming out on `uo_out`.

[A more brief README-like doc is in the info.md file](docs/info.md)

> This project was built on top of the TinyTapeout template, and was my submission for the open ended HW6/7 assignments in CSE222A at the University of California, Santa Cruz. Thank you for checking out my project!
