/*
 * Copyright (c) 2024 Aditya Kumar
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_dna_codon_xlator (
  input  logic [7:0] ui_in,
  output logic [7:0] uo_out,
  input  logic [7:0] uio_in,
  output logic [7:0] uio_out,
  output logic [7:0] uio_oe,
  input  logic       ena,
  input  logic       clk,
  input  logic       rst_n
);

  // input map: A=00 C=01 G=10 U=11
  logic [1:0] nuc_data;
  logic shift_en;
  logic frame_rst;
  assign nuc_data  = ui_in[1:0];
  assign shift_en  = ui_in[2];
  assign frame_rst = ui_in[3];

  logic [3:0] codon_sr; // first two nucleotides
  logic [1:0] nuc_cnt; // position in codon (0-2)
  logic [5:0] codon_q; // latched 6-bit codon
  logic codon_rdy; // valid pulse
  logic orf_open; // inside start..stop
  logic [3:0] codon_num; // translated count (saturates 15)

  // lookup
  logic [4:0] amino_idx;
  logic is_stop;
  logic is_start;
  assign is_stop = (amino_idx == 5'd20);
  assign is_start = (codon_q == 6'b00_11_10); // AUG

  codon_lut u_lut (.codon_i(codon_q), .amino_o(amino_idx));

  logic [5:0] full_codon;
  assign full_codon = {codon_sr, nuc_data};

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      codon_sr <= 4'd0;
      nuc_cnt <= 2'd0;
      codon_q <= 6'd0;
      codon_rdy <= 1'b0;
      orf_open <= 1'b0;
      codon_num <= 4'd0;
    end else if (frame_rst) begin
      codon_sr <= 4'd0;
      nuc_cnt <= 2'd0;
      codon_q <= 6'd0;
      codon_rdy <= 1'b0;
      orf_open <= 1'b0;
      codon_num <= 4'd0;
    end else begin
      codon_rdy <= 1'b0;

      if (shift_en) begin
        if (nuc_cnt == 2'd2) begin
          codon_q <= full_codon;
          codon_rdy <= 1'b1;
          nuc_cnt <= 2'd0;
          codon_sr <= 4'd0;
          if (codon_num < 4'd15) codon_num <= codon_num + 4'd1;
        end else begin
          codon_sr <= {codon_sr[1:0], nuc_data};
          nuc_cnt <= nuc_cnt + 2'd1;
        end
      end

      if (codon_rdy) begin
        if (is_start) orf_open <= 1'b1;
        if (is_stop) orf_open <= 1'b0;
      end
    end
  end

  assign uo_out = {orf_open, codon_rdy, is_stop, amino_idx};
  assign uio_out = {2'b0, codon_num, nuc_cnt};
  assign uio_oe = 8'hFF;

  logic _unused;
  assign _unused = &{ena, uio_in, ui_in[7:4], 1'b0};

endmodule


// 8 four-fold: prefix alone determines amino acid | 6 two-fold: purine/pyrimidine bit resolves pair | 2 irregular: AU*, UG* need full decode
module codon_lut (
  input  logic [5:0] codon_i, // {nuc1, nuc2, nuc3}, 2-bit each
  output logic [4:0] amino_o // 0-19 AA, 20 stop
);

  /*  0=Ala  1=Arg  2=Asn  3=Asp  4=Cys  5=Gln  6=Glu  7=Gly
      8=His  9=Ile 10=Leu 11=Lys 12=Met 13=Phe 14=Pro 15=Ser
     16=Thr 17=Trp 18=Tyr 19=Val 20=Stop 
  */

  logic [3:0] di;
  logic w0;
  assign di = codon_i[5:2]; // dinucleotide prefix
  assign w0 = codon_i[0]; // wobble: purine=0 pyrimidine=1

  always_comb begin
    case (di)
      // four fold degen
      4'b10_01: amino_o = 5'd0; // GC* -> Ala
      4'b01_10: amino_o = 5'd1; // CG* -> Arg
      4'b10_10: amino_o = 5'd7; // GG* -> Gly
      4'b01_11: amino_o = 5'd10; // CU* -> Leu
      4'b01_01: amino_o = 5'd14; // CC* -> Pro
      4'b11_01: amino_o = 5'd15; // UC* -> Ser
      4'b00_01: amino_o = 5'd16; // AC* -> Thr
      4'b10_11: amino_o = 5'd19; // GU* -> Val

      // two fold degen (wobble split)
      4'b00_00: amino_o = w0 ? 5'd2 : 5'd11; // AA -> Asn/Lys
      4'b10_00: amino_o = w0 ? 5'd3 : 5'd6; // GA -> Asp/Glu
      4'b01_00: amino_o = w0 ? 5'd8 : 5'd5; // CA -> His/Gln
      4'b00_10: amino_o = w0 ? 5'd15 : 5'd1; // AG -> Ser/Arg
      4'b11_11: amino_o = w0 ? 5'd13 : 5'd10; // UU -> Phe/Leu
      4'b11_00: amino_o = w0 ? 5'd18 : 5'd20; // UA -> Tyr/Stop

      // irregular (so full decode needed)
      4'b00_11: begin // AU*
        case (codon_i[1:0])
          2'b10: amino_o = 5'd12; // AUG -> Met
          default: amino_o = 5'd9; // AUU/C/A -> Ile
        endcase
      end
      4'b11_10: begin // UG*
        case (codon_i[1:0])
          2'b00: amino_o = 5'd20; // UGA -> Stop
          2'b10: amino_o = 5'd17; // UGG -> Trp
          default: amino_o = 5'd4; // UGU/C -> Cys
        endcase
      end

      default: amino_o = 5'd0;
    endcase
  end

endmodule