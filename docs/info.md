<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

The digital logic in this project is designed to serve as a functional equivalent to a biological ribosome.

We take in a stream of 2-bit nucleotides, group them into 3-nucleotide codons, and then output the coresponding amino acid index by referencing the standard genetic code.

### Breakdown

We can further break this design into three main blocks:
1. A **shift register and counter for the nucleotide**: The 4-bit shift register accumulates the first two nucleotodes of each codon. The counter (nuc_cnt) then uses tracks the position in the codon, which can either be 0, 1, or 2. By the time the third nucleotide arrives, the whole 6-bit codon gets latched to codon_q and the codon_rdy signal reaches logic high for exactly one cycle.

2. A **codon lookup table**: Referred to as codon_lut in the rtl, this is a curely combination module that takes the 6 bit codon from the earlier block and turns that into a 5-bit animo acid index. Instead of having to use a flat table with 64 entries, we take advantage of the biological structure of the genetic code to reduce the logic. (This would depend on 8 four-fold degenerate, 6 two-fold degenerate, and 2 irregular prefixes)

3. An **ORF (Open Reading Frame) tracker**: We monitor translated codons for the start codon AUG (Met) and any stop codon (UAA,UAG,UGA). When a start codon is seen, orf_open gets a logic high, and a logic low when the stop codon is seen instead. A saturating 4-bit counter is responsible for keeping track of how many codons have been translated since the last reset.

### Chip Pinout

While the pin interface can be found in info.yaml, here is a quick breakdown:

**Inputs** (ui_in)
- [1:0] Nucleotide data
- [2] Shift enable to accept necleotide on rising clk edge
- [3] Frame reset to clear all state synchronously

**Outputs** (uo_out)
- [4:0] Amino Acid Index
- [5] Stop codon
- [6] Codon ready flag
- [7] ORF

**Bidirectional** (uio, currently config as outputs)
- [1:0] Nucleotide position in current codon (can be 0, 1, or 2)
- [5:2] Codon counter, saturates at 15

## How to test

The cocotb testbench that can be found under test/test.py has the following 7 tests. You can run them with make in the test directory:

- test_reset: Make sure all outputs are 0 after rst
- test_all_64_codons: Translate every possible codon, check AA index, stop flag, and ready signal against the standard genetic code. This is the test most focused on functional correctness of the logic
- test_orf_tracking: We feed AUG(start), GCU(Ala), then UAA(stop) and verify that org_open goes high after AUG and low after UAA
- test_frame_reset: Shift 2 nucleotides (a partial codon), assert frame_rst, and check the reading frame counter and codon counter both reset. Then we check that the new codon translates correctly
- test_codon_counter: Translate 17 consecutive codons and check that the 4-bit counter increments correctly and saturates at 15
- test_biological_sequence: Translate a short peptide: Met-Trp-Phe-Stop
- test_continuous_streaming: Shift nucleotides every clk cycle with no idle gaps to check that the design can do operations back-to-back

## External hardware

Nucleotide sequences can be sent to the "ribosome" directly via ui_in and read as translated amino acids from the uo_out pin. No need for external hardware.

## Generative AI

I took this project as an excuse to learn something new and different, and have little background in molecular or cell biology.
I used a frontier language model to understand how a ribosome works, and also for good ideas of possible testcases to actually check that my interpreted logic in rtl wuld be correct. 