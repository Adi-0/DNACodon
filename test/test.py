# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, Timer

# nucleotide encoding
A, C, G, U = 0, 1, 2, 3


# amino acid indices
AA = dict(
    Ala=0,  Arg=1,  Asn=2,  Asp=3,  Cys=4,
    Gln=5,  Glu=6,  Gly=7,  His=8,  Ile=9,
    Leu=10, Lys=11, Met=12, Phe=13, Pro=14,
    Ser=15, Thr=16, Trp=17, Tyr=18, Val=19,
    Stop=20,
)


# complete standard genetic code
CODON_TABLE = {
    (A,A,A): "Lys", (A,A,C): "Asn", (A,A,G): "Lys", (A,A,U): "Asn",
    (A,C,A): "Thr", (A,C,C): "Thr", (A,C,G): "Thr", (A,C,U): "Thr",
    (A,G,A): "Arg", (A,G,C): "Ser", (A,G,G): "Arg", (A,G,U): "Ser",
    (A,U,A): "Ile", (A,U,C): "Ile", (A,U,G): "Met", (A,U,U): "Ile",
    (C,A,A): "Gln", (C,A,C): "His", (C,A,G): "Gln", (C,A,U): "His",
    (C,C,A): "Pro", (C,C,C): "Pro", (C,C,G): "Pro", (C,C,U): "Pro",
    (C,G,A): "Arg", (C,G,C): "Arg", (C,G,G): "Arg", (C,G,U): "Arg",
    (C,U,A): "Leu", (C,U,C): "Leu", (C,U,G): "Leu", (C,U,U): "Leu",
    (G,A,A): "Glu", (G,A,C): "Asp", (G,A,G): "Glu", (G,A,U): "Asp",
    (G,C,A): "Ala", (G,C,C): "Ala", (G,C,G): "Ala", (G,C,U): "Ala",
    (G,G,A): "Gly", (G,G,C): "Gly", (G,G,G): "Gly", (G,G,U): "Gly",
    (G,U,A): "Val", (G,U,C): "Val", (G,U,G): "Val", (G,U,U): "Val",
    (U,A,A): "Stop",(U,A,C): "Tyr", (U,A,G): "Stop",(U,A,U): "Tyr",
    (U,C,A): "Ser", (U,C,C): "Ser", (U,C,G): "Ser", (U,C,U): "Ser",
    (U,G,A): "Stop",(U,G,C): "Cys", (U,G,G): "Trp", (U,G,U): "Cys",
    (U,U,A): "Leu", (U,U,C): "Phe", (U,U,G): "Leu", (U,U,U): "Phe",
}

NUC_NAME = {A: "A", C: "C", G: "G", U: "U"}



async def settle(dut):
    """wait for comb logic to settle after clock edge"""
    await Timer(1, unit="ns")


async def reset(dut):
    """async reset."""
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)
    await settle(dut)


async def shift_nuc(dut, nuc):
    """shift one nucleotide into the codon register"""
    dut.ui_in.value = (nuc & 0x3) | 0x4
    await ClockCycles(dut.clk, 1)
    await settle(dut)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 1)
    await settle(dut)


async def translate_codon(dut, n1, n2, n3):
    """shift 3 nucleotides, return (amino_idx, is_stop, codon_rdy)"""
    await shift_nuc(dut, n1)
    await shift_nuc(dut, n2)

    dut.ui_in.value = (n3 & 0x3) | 0x4
    await ClockCycles(dut.clk, 1)
    await settle(dut)
    dut.ui_in.value = 0

    out = int(dut.uo_out.value)
    amino = out & 0x1F
    stop = (out >> 5) & 1
    rdy = (out >> 6) & 1

    await ClockCycles(dut.clk, 1)
    await settle(dut)
    return amino, stop, rdy


# Actual Tests

@cocotb.test()
async def test_reset(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())
    await reset(dut)

    out = int(dut.uo_out.value)
    rdy = (out >> 6) & 1
    orf_open = (out >> 7) & 1
    assert rdy == 0, "codon_rdy should be 0 after reset"
    assert orf_open == 0, "orf_open should be 0 after reset"
    assert (int(dut.uio_out.value) & 0x3F) == 0, "status not zero after reset"
    dut._log.info("PASS: reset")


@cocotb.test()
async def test_all_64_codons(dut):
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    passed = 0
    for (n1, n2, n3), aa_name in CODON_TABLE.items():
        await reset(dut)
        amino, stop, rdy = await translate_codon(dut, n1, n2, n3)
        expected = AA[aa_name]
        codon_str = NUC_NAME[n1] + NUC_NAME[n2] + NUC_NAME[n3]

        assert rdy == 1, f"{codon_str}: codon_rdy not asserted"
        assert amino == expected, (
            f"{codon_str}: expected {aa_name}({expected}), got {amino}"
        )
        if aa_name == "Stop":
            assert stop == 1, f"{codon_str}: stop flag not set"
        else:
            assert stop == 0, f"{codon_str}: spurious stop flag"
        passed += 1

    dut._log.info(f"PASS: all {passed}/64 codons correct")


@cocotb.test()
async def test_orf_tracking(dut):
    """check ORF opens on AUG and closes on stop codon"""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())
    await reset(dut)

    assert (int(dut.uo_out.value) >> 7) & 1 == 0, "ORF open before start"

    # AUG -> Met
    await translate_codon(dut, A, U, G)
    await ClockCycles(dut.clk, 1)
    await settle(dut)
    assert (int(dut.uo_out.value) >> 7) & 1 == 1, "ORF not opened by AUG"

    # GCU -> Ala
    await translate_codon(dut, G, C, U)
    await ClockCycles(dut.clk, 1)
    await settle(dut)
    assert (int(dut.uo_out.value) >> 7) & 1 == 1, "ORF closed prematurely"

    # UAA -> Stop
    await translate_codon(dut, U, A, A)
    await ClockCycles(dut.clk, 1)
    await settle(dut)
    assert (int(dut.uo_out.value) >> 7) & 1 == 0, "ORF not closed by UAA"

    dut._log.info("PASS: ORF tracking (AUG -> Ala -> Stop)")


@cocotb.test()
async def test_frame_reset(dut):
    """frame_rst clears mid-codon state"""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())
    await reset(dut)

    # partial codon
    await shift_nuc(dut, G)
    await shift_nuc(dut, C)
    assert (int(dut.uio_out.value) & 0x3) == 2, "nuc_cnt should be 2"

    # assert frame_rst
    dut.ui_in.value = 0x08
    await ClockCycles(dut.clk, 1)
    await settle(dut)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 1)
    await settle(dut)

    assert (int(dut.uio_out.value) & 0x3) == 0, "nuc_cnt not reset"
    assert ((int(dut.uio_out.value) >> 2) & 0xF) == 0, "codon_num not reset"

    # translate after reset
    amino, stop, rdy = await translate_codon(dut, A, U, G)
    assert rdy == 1 and amino == AA["Met"], "Translation broken after frame_rst"
    dut._log.info("PASS: frame reset")


@cocotb.test()
async def test_codon_counter(dut):
    """codon counter increments and saturates at 15"""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())
    await reset(dut)

    for i in range(17):
        await translate_codon(dut, G, C, A)
        await ClockCycles(dut.clk, 1)
        await settle(dut)
        expected = min(i + 1, 15)
        actual = (int(dut.uio_out.value) >> 2) & 0xF
        assert actual == expected, f"Codon #{i+1}: count={actual}, expected={expected}"

    dut._log.info("PASS: codon counter with saturation")


@cocotb.test()
async def test_biological_sequence(dut):
    """translate Met-Trp-Phe-Stop"""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())
    await reset(dut)

    sequence = [
        ((A, U, G), "Met"),
        ((U, G, G), "Trp"),
        ((U, U, C), "Phe"),
        ((U, A, A), "Stop"),
    ]

    for (n1, n2, n3), expected_name in sequence:
        amino, stop, rdy = await translate_codon(dut, n1, n2, n3)
        assert rdy == 1, f"{expected_name}: codon_rdy not asserted"
        assert amino == AA[expected_name], (
            f"Expected {expected_name}({AA[expected_name]}), got {amino}"
        )

    dut._log.info("PASS: biological sequence Met-Trp-Phe-Stop")


@cocotb.test()
async def test_continuous_streaming(dut):
    """shift nucleotides every clock cycle with no gaps"""
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())
    await reset(dut)

    # AUG (Met=12), GCA (Ala=0), UAG (Stop=20)
    nucs = [A, U, G, G, C, A, U, A, G]
    expected = [AA["Met"], AA["Ala"], AA["Stop"]]
    results = []

    for nuc in nucs:
        dut.ui_in.value = (nuc & 0x3) | 0x4
        await ClockCycles(dut.clk, 1)
        await settle(dut)
        rdy = (int(dut.uo_out.value) >> 6) & 1
        if rdy:
            results.append(int(dut.uo_out.value) & 0x1F)

    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 1)

    assert results == expected, f"Streaming: got {results}, expected {expected}"
    dut._log.info("PASS: continuous streaming")