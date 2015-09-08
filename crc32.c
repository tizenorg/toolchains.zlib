/* crc32.c -- compute the CRC-32 of a data stream
 * Copyright (C) 1995-2006, 2010 Mark Adler
 * For conditions of distribution and use, see copyright notice in zlib.h
 *
 * Thanks to Rodney Brown <rbrown64@csc.com.au> for his contribution of faster
 * CRC methods: exclusive-oring 32 bits of data at a time, and pre-computing
 * tables for updating the shift register in one step with three exclusive-ors
 * instead of four steps with four exclusive-ors.  This results in about a
 * factor of two increase in speed on a Power PC G4 (PPC7455) using gcc -O3.
 */

/* @(#) $Id$ */

/*
  Note on the use of DYNAMIC_CRC_TABLE: there is no mutex or semaphore
  protection on the static variables used to control the first-use generation
  of the crc tables.  Therefore, if you #define DYNAMIC_CRC_TABLE, you should
  first call get_crc_table() to initialize the tables before allowing more than
  one thread to use crc32().
 */

#ifdef MAKECRCH
#  include <stdio.h>
#  ifndef DYNAMIC_CRC_TABLE
#    define DYNAMIC_CRC_TABLE
#  endif /* !DYNAMIC_CRC_TABLE */
#endif /* MAKECRCH */

#include "zutil.h"      /* for STDC and FAR definitions */
#ifdef __ARM_HAVE_NEON
#include <arm_neon.h>
#endif

#define local static

/* Find a four-byte integer type for crc32_little() and crc32_big(). */
#ifndef NOBYFOUR
#  ifdef STDC           /* need ANSI C limits.h to determine sizes */
#    include <limits.h>
#    define BYFOUR
#    if (UINT_MAX == 0xffffffffUL)
       typedef unsigned int u4;
#    else
#      if (ULONG_MAX == 0xffffffffUL)
         typedef unsigned long u4;
#      else
#        if (USHRT_MAX == 0xffffffffUL)
           typedef unsigned short u4;
#        else
#          undef BYFOUR     /* can't find a four-byte integer type! */
#        endif
#      endif
#    endif
#  endif /* STDC */
#endif /* !NOBYFOUR */

/* Definitions for doing the crc four data bytes at a time. */
#ifdef BYFOUR
#  define REV(w) ((((w)>>24)&0xff)+(((w)>>8)&0xff00)+ \
                (((w)&0xff00)<<8)+(((w)&0xff)<<24))
   local unsigned long crc32_little OF((unsigned long,
                        const unsigned char FAR *, unsigned));
   local unsigned long crc32_big OF((unsigned long,
                        const unsigned char FAR *, unsigned));
#  define TBLS 8
#else
#  define TBLS 1
#endif /* BYFOUR */

/* Local functions for crc concatenation */
local unsigned long gf2_matrix_times OF((unsigned long *mat,
                                         unsigned long vec));
local void gf2_matrix_square OF((unsigned long *square, unsigned long *mat));
local uLong crc32_combine_(uLong crc1, uLong crc2, z_off64_t len2);


#ifdef DYNAMIC_CRC_TABLE

local volatile int crc_table_empty = 1;
local unsigned long FAR crc_table[TBLS][256];
local void make_crc_table OF((void));
#ifdef MAKECRCH
   local void write_table OF((FILE *, const unsigned long FAR *));
#endif /* MAKECRCH */
/*
  Generate tables for a byte-wise 32-bit CRC calculation on the polynomial:
  x^32+x^26+x^23+x^22+x^16+x^12+x^11+x^10+x^8+x^7+x^5+x^4+x^2+x+1.

  Polynomials over GF(2) are represented in binary, one bit per coefficient,
  with the lowest powers in the most significant bit.  Then adding polynomials
  is just exclusive-or, and multiplying a polynomial by x is a right shift by
  one.  If we call the above polynomial p, and represent a byte as the
  polynomial q, also with the lowest power in the most significant bit (so the
  byte 0xb1 is the polynomial x^7+x^3+x+1), then the CRC is (q*x^32) mod p,
  where a mod b means the remainder after dividing a by b.

  This calculation is done using the shift-register method of multiplying and
  taking the remainder.  The register is initialized to zero, and for each
  incoming bit, x^32 is added mod p to the register if the bit is a one (where
  x^32 mod p is p+x^32 = x^26+...+1), and the register is multiplied mod p by
  x (which is shifting right by one and adding x^32 mod p if the bit shifted
  out is a one).  We start with the highest power (least significant bit) of
  q and repeat for all eight bits of q.

  The first table is simply the CRC of all possible eight bit values.  This is
  all the information needed to generate CRCs on data a byte at a time for all
  combinations of CRC register values and incoming bytes.  The remaining tables
  allow for word-at-a-time CRC calculation for both big-endian and little-
  endian machines, where a word is four bytes.
*/
local void make_crc_table()
{
    unsigned long c;
    int n, k;
    unsigned long poly;                 /* polynomial exclusive-or pattern */
    /* terms of polynomial defining this crc (except x^32): */
    static volatile int first = 1;      /* flag to limit concurrent making */
    static const unsigned char p[] = {0,1,2,4,5,7,8,10,11,12,16,22,23,26};

    /* See if another task is already doing this (not thread-safe, but better
       than nothing -- significantly reduces duration of vulnerability in
       case the advice about DYNAMIC_CRC_TABLE is ignored) */
    if (first) {
        first = 0;

        /* make exclusive-or pattern from polynomial (0xedb88320UL) */
        poly = 0UL;
        for (n = 0; n < sizeof(p)/sizeof(unsigned char); n++)
            poly |= 1UL << (31 - p[n]);

        /* generate a crc for every 8-bit value */
        for (n = 0; n < 256; n++) {
            c = (unsigned long)n;
            for (k = 0; k < 8; k++)
                c = c & 1 ? poly ^ (c >> 1) : c >> 1;
            crc_table[0][n] = c;
        }

#ifdef BYFOUR
        /* generate crc for each value followed by one, two, and three zeros,
           and then the byte reversal of those as well as the first table */
        for (n = 0; n < 256; n++) {
            c = crc_table[0][n];
            crc_table[4][n] = REV(c);
            for (k = 1; k < 4; k++) {
                c = crc_table[0][c & 0xff] ^ (c >> 8);
                crc_table[k][n] = c;
                crc_table[k + 4][n] = REV(c);
            }
        }
#endif /* BYFOUR */

        crc_table_empty = 0;
    }
    else {      /* not first */
        /* wait for the other guy to finish (not efficient, but rare) */
        while (crc_table_empty)
            ;
    }

#ifdef MAKECRCH
    /* write out CRC tables to crc32.h */
    {
        FILE *out;

        out = fopen("crc32.h", "w");
        if (out == NULL) return;
        fprintf(out, "/* crc32.h -- tables for rapid CRC calculation\n");
        fprintf(out, " * Generated automatically by crc32.c\n */\n\n");
        fprintf(out, "local const unsigned long FAR ");
        fprintf(out, "crc_table[TBLS][256] =\n{\n  {\n");
        write_table(out, crc_table[0]);
#  ifdef BYFOUR
        fprintf(out, "#ifdef BYFOUR\n");
        for (k = 1; k < 8; k++) {
            fprintf(out, "  },\n  {\n");
            write_table(out, crc_table[k]);
        }
        fprintf(out, "#endif\n");
#  endif /* BYFOUR */
        fprintf(out, "  }\n};\n");
        fclose(out);
    }
#endif /* MAKECRCH */
}

#ifdef MAKECRCH
local void write_table(out, table)
    FILE *out;
    const unsigned long FAR *table;
{
    int n;

    for (n = 0; n < 256; n++)
        fprintf(out, "%s0x%08lxUL%s", n % 5 ? "" : "    ", table[n],
                n == 255 ? "\n" : (n % 5 == 4 ? ",\n" : ", "));
}
#endif /* MAKECRCH */

#else /* !DYNAMIC_CRC_TABLE */
/* ========================================================================
 * Tables of CRC-32s of all single-byte values, made by make_crc_table().
 */
#include "crc32.h"
#endif /* DYNAMIC_CRC_TABLE */

/* =========================================================================
 * This function can be used by asm versions of crc32()
 */
const unsigned long FAR * ZEXPORT get_crc_table()
{
#ifdef DYNAMIC_CRC_TABLE
    if (crc_table_empty)
        make_crc_table();
#endif /* DYNAMIC_CRC_TABLE */
    return (const unsigned long FAR *)crc_table;
}

/* ========================================================================= */
#define DO1 crc = crc_table[0][((int)crc ^ (*buf++)) & 0xff] ^ (crc >> 8)
#define DO8 DO1; DO1; DO1; DO1; DO1; DO1; DO1; DO1

/* ========================================================================= */
local unsigned long __crc32(crc, buf, len)
    unsigned long crc;
    const unsigned char FAR *buf;
    uInt len;
{
#ifdef DYNAMIC_CRC_TABLE
    if (crc_table_empty)
        make_crc_table();
#endif /* DYNAMIC_CRC_TABLE */

#ifdef BYFOUR
    if (sizeof(void *) == sizeof(ptrdiff_t)) {
        u4 endian;

        endian = 1;
        if (*((unsigned char *)(&endian)))
            return crc32_little(crc, buf, len);
        else
            return crc32_big(crc, buf, len);
    }
#endif /* BYFOUR */
    crc = crc ^ 0xffffffffUL;
    while (len >= 8) {
        DO8;
        len -= 8;
    }
    if (len) do {
        DO1;
    } while (--len);
    return crc ^ 0xffffffffUL;
}

#ifdef __ARM_HAVE_NEON
local inline uint64x1_t crc32_neon_proc_part(poly8x8_t lhs, poly8x8_t rhs1,
   poly8x8_t rhs2, poly8x8_t rhs3, poly8x8_t rhs4)
{
    poly16x8_t lm1, lm2, lm3, lm4;
    poly16x4x2_t lz1, lz2;
    uint16x4_t le1, le2;
    uint32x2_t le3;
    uint32x4_t ls1, ls2, lf1, lf2;
    uint64x2_t ls3, le4;
    uint64x1_t lf3, lf4;

    lm1 = vmull_p8(lhs, rhs1);
    lm2 = vmull_p8(lhs, rhs2);
    lz1 = vuzp_p16(vget_low_p16(lm2), vget_high_p16(lm2));
    le1 = veor_u16(vreinterpret_u16_p16(lz1.val[0]),
                   vreinterpret_u16_p16(lz1.val[1]));
    ls1 = vshll_n_u16(le1, 8);
    lf1 = veorq_u32(ls1, vreinterpretq_u32_p16(lm1));

    lm3 = vmull_p8(lhs, rhs3);
    lm4 = vmull_p8(lhs, rhs4);
    lz2 = vuzp_p16(vget_low_p16(lm4), vget_high_p16(lm4));
    le2 = veor_u16(vreinterpret_u16_p16(lz2.val[0]),
                   vreinterpret_u16_p16(lz2.val[1]));
    ls2 = vshll_n_u16(le2, 8);
    lf2 = veorq_u32(ls2, vreinterpretq_u32_p16(lm3));

    le3 = veor_u32(vget_low_u32(lf2), vget_high_u32(lf2));
    ls3 = vshll_n_u32(le3, 16);
    le4 = veorq_u64(ls3, vreinterpretq_u64_u32(lf1));
    lf3 = vreinterpret_u64_u32(veor_u32(vget_low_u32(vreinterpretq_u32_u64(le4)),
                               vget_high_u32(vreinterpretq_u32_u64(le4))));
    lf4 = vshl_n_u64(lf3, 1);
    return lf4;
}

local unsigned long crc32_neon(crc, buf, len)
    unsigned long crc;
    const unsigned char FAR *buf;
    uInt len;
{
   poly8x8_t xor_constant, lhs1, lhs2, lhs3, lhs4, rhs1, rhs2, rhs3, rhs4;
   poly8x16_t lhl1, lhl2;

   unsigned long long residues[4];
   unsigned long loop;

   if (len % 32)
       return __crc32(crc, buf, len);

   /*
    * because crc32c has an initial crc value of 0xffffffff, we need to
    * pre-fold the buffer before folding begins proper.
    * The following constant is computed by:
    * 1) finding a 8x32 bit value that gives a 0xffffffff crc (with initial value 0)
    *    (this will be 7x32 bit 0s and 1x32 bit constant)
    * 2) run a buffer fold (with 0 xor_constant) on this 8x32 bit value to get the
    *    xor_constant.
    */
   if (crc == 0)
      xor_constant = vcreate_p8(0xF344863010D12638);
   else if (crc == 0xffffffff)
      xor_constant = vcreate_p8(0);
   else
      return __crc32(crc, buf, len);

   /* k1 = x^288 mod P(x) - bit reversed */
   /* k2 = x^256 mod P(x) - bit reversed */

   rhs1 = vcreate_p8(0xED627DAE78ED02D5);  /* k2:k1 */
   rhs2 = vcreate_p8(0x62EDAE7DED78D502);  /* byte swap */
   rhs3 = vcreate_p8(0x7DAEED6202D578ED);  /* half-word swap */
   rhs4 = vcreate_p8(0xAE7D62EDD502ED78);  /* byte swap of half-word swap */


   lhl1 = vld1q_p8((const poly8_t *) buf);
   lhl2 = vld1q_p8((const poly8_t *) buf + 16);

   lhs1 = vget_low_p8(lhl1);
   lhs2 = vget_high_p8(lhl1);
   lhs3 = vget_low_p8(lhl2);
   lhs4 = vget_high_p8(lhl2);

   /* pre-fold lhs4 */
   lhs4 = vreinterpret_p8_u16(veor_u16(vreinterpret_u16_p8(lhs4),
       vreinterpret_u16_p8(xor_constant)));

   for (loop = 0; loop < (len - 32)/32; ++loop) {
       uint64x1_t l1f4, l2f4, l3f4, l4f4;

       l1f4 = crc32_neon_proc_part(lhs1, rhs1, rhs2, rhs3, rhs4);
       l2f4 = crc32_neon_proc_part(lhs2, rhs1, rhs2, rhs3, rhs4);
       l3f4 = crc32_neon_proc_part(lhs3, rhs1, rhs2, rhs3, rhs4);
       l4f4 = crc32_neon_proc_part(lhs4, rhs1, rhs2, rhs3, rhs4);

       lhl1 = vld1q_p8((const poly8_t *) (buf + 32 * (loop + 1)));
       lhl2 = vld1q_p8((const poly8_t *) (buf + 32 * (loop + 1) + 16));

       __builtin_prefetch(buf + 32 * (loop + 2));

       lhs1 = vget_low_p8(lhl1);
       lhs2 = vget_high_p8(lhl1);
       lhs3 = vget_low_p8(lhl2);
       lhs4 = vget_high_p8(lhl2);

       lhs1 = vreinterpret_p8_u64(veor_u64(vreinterpret_u64_p8(lhs1), l1f4));
       lhs2 = vreinterpret_p8_u64(veor_u64(vreinterpret_u64_p8(lhs2), l2f4));
       lhs3 = vreinterpret_p8_u64(veor_u64(vreinterpret_u64_p8(lhs3), l3f4));
       lhs4 = vreinterpret_p8_u64(veor_u64(vreinterpret_u64_p8(lhs4), l4f4));
   }

   vst1q_p8((poly8_t *) &residues[0], vcombine_p8(lhs1, lhs2));
   vst1q_p8((poly8_t *) &residues[2], vcombine_p8(lhs3, lhs4));

   return __crc32(0xffffffff, (const uint8_t *)residues, 32);
}
#endif

unsigned long ZEXPORT crc32(crc, buf, len)
    unsigned long crc;
    const unsigned char FAR *buf;
    uInt len;
{
    if (buf == Z_NULL) return 0UL;

#ifdef __ARM_HAVE_NEON
    return crc32_neon(crc, buf, len);
#else
    return __crc32(crc, buf, len);
#endif
}

#ifdef BYFOUR

/* ========================================================================= */
#define DOLIT4 c ^= *buf4++; \
        c = crc_table[3][c & 0xff] ^ crc_table[2][(c >> 8) & 0xff] ^ \
            crc_table[1][(c >> 16) & 0xff] ^ crc_table[0][c >> 24]
#define DOLIT32 DOLIT4; DOLIT4; DOLIT4; DOLIT4; DOLIT4; DOLIT4; DOLIT4; DOLIT4

/* ========================================================================= */
local unsigned long crc32_little(crc, buf, len)
    unsigned long crc;
    const unsigned char FAR *buf;
    unsigned len;
{
    register u4 c;
    register const u4 FAR *buf4;

    c = (u4)crc;
    c = ~c;
    while (len && ((ptrdiff_t)buf & 3)) {
        c = crc_table[0][(c ^ *buf++) & 0xff] ^ (c >> 8);
        len--;
    }

    buf4 = (const u4 FAR *)(const void FAR *)buf;
    while (len >= 32) {
        DOLIT32;
        len -= 32;
    }
    while (len >= 4) {
        DOLIT4;
        len -= 4;
    }
    buf = (const unsigned char FAR *)buf4;

    if (len) do {
        c = crc_table[0][(c ^ *buf++) & 0xff] ^ (c >> 8);
    } while (--len);
    c = ~c;
    return (unsigned long)c;
}

/* ========================================================================= */
#define DOBIG4 c ^= *++buf4; \
        c = crc_table[4][c & 0xff] ^ crc_table[5][(c >> 8) & 0xff] ^ \
            crc_table[6][(c >> 16) & 0xff] ^ crc_table[7][c >> 24]
#define DOBIG32 DOBIG4; DOBIG4; DOBIG4; DOBIG4; DOBIG4; DOBIG4; DOBIG4; DOBIG4

/* ========================================================================= */
local unsigned long crc32_big(crc, buf, len)
    unsigned long crc;
    const unsigned char FAR *buf;
    unsigned len;
{
    register u4 c;
    register const u4 FAR *buf4;

    c = REV((u4)crc);
    c = ~c;
    while (len && ((ptrdiff_t)buf & 3)) {
        c = crc_table[4][(c >> 24) ^ *buf++] ^ (c << 8);
        len--;
    }

    buf4 = (const u4 FAR *)(const void FAR *)buf;
    buf4--;
    while (len >= 32) {
        DOBIG32;
        len -= 32;
    }
    while (len >= 4) {
        DOBIG4;
        len -= 4;
    }
    buf4++;
    buf = (const unsigned char FAR *)buf4;

    if (len) do {
        c = crc_table[4][(c >> 24) ^ *buf++] ^ (c << 8);
    } while (--len);
    c = ~c;
    return (unsigned long)(REV(c));
}

#endif /* BYFOUR */

#define GF2_DIM 32      /* dimension of GF(2) vectors (length of CRC) */

/* ========================================================================= */
local unsigned long gf2_matrix_times(mat, vec)
    unsigned long *mat;
    unsigned long vec;
{
    unsigned long sum;

    sum = 0;
    while (vec) {
        if (vec & 1)
            sum ^= *mat;
        vec >>= 1;
        mat++;
    }
    return sum;
}

/* ========================================================================= */
local void gf2_matrix_square(square, mat)
    unsigned long *square;
    unsigned long *mat;
{
    int n;

    for (n = 0; n < GF2_DIM; n++)
        square[n] = gf2_matrix_times(mat, mat[n]);
}

/* ========================================================================= */
local uLong crc32_combine_(crc1, crc2, len2)
    uLong crc1;
    uLong crc2;
    z_off64_t len2;
{
    int n;
    unsigned long row;
    unsigned long even[GF2_DIM];    /* even-power-of-two zeros operator */
    unsigned long odd[GF2_DIM];     /* odd-power-of-two zeros operator */

    /* degenerate case (also disallow negative lengths) */
    if (len2 <= 0)
        return crc1;

    /* put operator for one zero bit in odd */
    odd[0] = 0xedb88320UL;          /* CRC-32 polynomial */
    row = 1;
    for (n = 1; n < GF2_DIM; n++) {
        odd[n] = row;
        row <<= 1;
    }

    /* put operator for two zero bits in even */
    gf2_matrix_square(even, odd);

    /* put operator for four zero bits in odd */
    gf2_matrix_square(odd, even);

    /* apply len2 zeros to crc1 (first square will put the operator for one
       zero byte, eight zero bits, in even) */
    do {
        /* apply zeros operator for this bit of len2 */
        gf2_matrix_square(even, odd);
        if (len2 & 1)
            crc1 = gf2_matrix_times(even, crc1);
        len2 >>= 1;

        /* if no more bits set, then done */
        if (len2 == 0)
            break;

        /* another iteration of the loop with odd and even swapped */
        gf2_matrix_square(odd, even);
        if (len2 & 1)
            crc1 = gf2_matrix_times(odd, crc1);
        len2 >>= 1;

        /* if no more bits set, then done */
    } while (len2 != 0);

    /* return combined crc */
    crc1 ^= crc2;
    return crc1;
}

/* ========================================================================= */
uLong ZEXPORT crc32_combine(crc1, crc2, len2)
    uLong crc1;
    uLong crc2;
    z_off_t len2;
{
    return crc32_combine_(crc1, crc2, len2);
}

uLong ZEXPORT crc32_combine64(crc1, crc2, len2)
    uLong crc1;
    uLong crc2;
    z_off64_t len2;
{
    return crc32_combine_(crc1, crc2, len2);
}
