/*
 * Copyright (c) The btclib developers
 * Distributed under the MIT software license, see the accompanying
 * LICENSE file or https://opensource.org/license/mit for the full text.
 *
 * Valgrind's constant-time check of the secret-taking secp256k1-zkp calls
 * this package wraps that secp256k1-zkp's own src/ctime_tests.c does not
 * make. It follows that file: each secret is marked undefined before the
 * call and the return value defined after it, so memcheck reports a
 * branch or a memory access that depends on a secret.
 *
 * The one argument names the call to run, so that each call gets a
 * Valgrind run and an exit code of its own. `control` branches on a
 * secret, which memcheck has to report. An unknown name exits 2.
 *
 * .github/workflows/upstream-tests.yml builds it against the library
 * secp256k1-zkp's ctime_tests links, with that program's flags, and holds
 * each call to the outcome SECURITY.md records for it.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "secp256k1.h"
#include "secp256k1_ecdsa_s2c.h"
#include "secp256k1_generator.h"
#include "secp256k1_rangeproof.h"

#include "checkmem.h"

#if !SECP256K1_CHECKMEM_ENABLED
#error "compile with -DVALGRIND and valgrind/memcheck.h on the include path"
#endif

#define CHECK(cond)                                                       \
    do {                                                                  \
        if (!(cond)) {                                                    \
            fprintf(stderr, "%s:%d: CHECK(%s) failed\n", __FILE__,        \
                    __LINE__, #cond);                                     \
            abort();                                                      \
        }                                                                 \
    } while (0)

static void fill(unsigned char *buf, size_t len, unsigned char start) {
    size_t i;
    for (i = 0; i < len; i++) {
        buf[i] = (unsigned char)(start + i);
    }
}

static void anti_exfil_sign(const secp256k1_context *ctx) {
    secp256k1_ecdsa_signature sig;
    unsigned char msg[32], seckey[32], host_data[32];
    int ret;

    fill(msg, 32, 1);
    fill(seckey, 32, 65);
    fill(host_data, 32, 33);
    SECP256K1_CHECKMEM_UNDEFINE(seckey, 32);
    SECP256K1_CHECKMEM_UNDEFINE(host_data, 32);
    ret = secp256k1_anti_exfil_sign(ctx, &sig, msg, seckey, host_data);
    SECP256K1_CHECKMEM_DEFINE(&ret, sizeof(ret));
    CHECK(ret == 1);
}

static void generator_generate_blinded(const secp256k1_context *ctx) {
    secp256k1_generator gen;
    unsigned char seed[32], blind[32];
    int ret;

    fill(seed, 32, 7);
    fill(blind, 32, 65);
    SECP256K1_CHECKMEM_UNDEFINE(blind, 32);
    ret = secp256k1_generator_generate_blinded(ctx, &gen, seed, blind);
    SECP256K1_CHECKMEM_DEFINE(&ret, sizeof(ret));
    CHECK(ret == 1);
}

static void pedersen_blind_sum(const secp256k1_context *ctx) {
    unsigned char blind_out[32], blind0[32], blind1[32];
    const unsigned char *blinds[2];
    int ret;

    fill(blind0, 32, 65);
    fill(blind1, 32, 33);
    blinds[0] = blind0;
    blinds[1] = blind1;
    SECP256K1_CHECKMEM_UNDEFINE(blind0, 32);
    SECP256K1_CHECKMEM_UNDEFINE(blind1, 32);
    ret = secp256k1_pedersen_blind_sum(ctx, blind_out, blinds, 2, 1);
    SECP256K1_CHECKMEM_DEFINE(&ret, sizeof(ret));
    CHECK(ret == 1);
}

static void pedersen_blind_generator_blind_sum(const secp256k1_context *ctx) {
    uint64_t values[2];
    unsigned char gen_blind0[32], gen_blind1[32], blind0[32], blind1[32];
    const unsigned char *gen_blinds[2];
    unsigned char *blinds[2];
    int ret;

    values[0] = 5;
    values[1] = 5;
    fill(gen_blind0, 32, 3);
    fill(gen_blind1, 32, 4);
    fill(blind0, 32, 5);
    memset(blind1, 0, 32);
    gen_blinds[0] = gen_blind0;
    gen_blinds[1] = gen_blind1;
    blinds[0] = blind0;
    blinds[1] = blind1;
    SECP256K1_CHECKMEM_UNDEFINE(values, sizeof(values));
    SECP256K1_CHECKMEM_UNDEFINE(gen_blind0, 32);
    SECP256K1_CHECKMEM_UNDEFINE(gen_blind1, 32);
    SECP256K1_CHECKMEM_UNDEFINE(blind0, 32);
    ret = secp256k1_pedersen_blind_generator_blind_sum(ctx, values, gen_blinds,
                                                       blinds, 2, 1);
    SECP256K1_CHECKMEM_DEFINE(&ret, sizeof(ret));
    CHECK(ret == 1);
}
/* blind 65.., nonce 1.., message 100.. and the value 1234567, committed
 * under H, all of them defined */
static void rangeproof_inputs(const secp256k1_context *ctx,
                              secp256k1_pedersen_commitment *commit,
                              unsigned char *blind, unsigned char *nonce,
                              unsigned char *message, uint64_t *value) {
    fill(blind, 32, 65);
    fill(nonce, 32, 1);
    fill(message, 32, 100);
    *value = 1234567;
    CHECK(secp256k1_pedersen_commit(ctx, commit, blind, *value,
                                    secp256k1_generator_h));
}

static void rangeproof_sign(const secp256k1_context *ctx) {
    secp256k1_pedersen_commitment commit;
    unsigned char proof[5134];
    unsigned char blind[32], nonce[32], message[32];
    size_t plen = sizeof(proof);
    uint64_t value;
    int ret;

    rangeproof_inputs(ctx, &commit, blind, nonce, message, &value);
    SECP256K1_CHECKMEM_UNDEFINE(blind, 32);
    SECP256K1_CHECKMEM_UNDEFINE(nonce, 32);
    SECP256K1_CHECKMEM_UNDEFINE(&value, sizeof(value));
    SECP256K1_CHECKMEM_UNDEFINE(message, 32);
    ret = secp256k1_rangeproof_sign(ctx, proof, &plen, 0, &commit, blind,
                                    nonce, 0, 0, value, message, 32, NULL, 0,
                                    secp256k1_generator_h);
    SECP256K1_CHECKMEM_DEFINE(&ret, sizeof(ret));
    CHECK(ret == 1);
}

static void rangeproof_rewind(const secp256k1_context *ctx) {
    secp256k1_pedersen_commitment commit;
    unsigned char proof[5134];
    unsigned char blind[32], nonce[32], message[32];
    unsigned char blind_out[32], message_out[4096];
    size_t plen = sizeof(proof);
    size_t outlen = sizeof(message_out);
    uint64_t value, value_out, min_value, max_value;
    int ret;

    rangeproof_inputs(ctx, &commit, blind, nonce, message, &value);
    CHECK(secp256k1_rangeproof_sign(ctx, proof, &plen, 0, &commit, blind,
                                    nonce, 0, 0, value, message, 32, NULL, 0,
                                    secp256k1_generator_h));
    SECP256K1_CHECKMEM_UNDEFINE(nonce, 32);
    ret = secp256k1_rangeproof_rewind(ctx, blind_out, &value_out, message_out,
                                      &outlen, nonce, &min_value, &max_value,
                                      &commit, proof, plen, NULL, 0,
                                      secp256k1_generator_h);
    SECP256K1_CHECKMEM_DEFINE(&ret, sizeof(ret));
    CHECK(ret == 1);
}

/* a branch on a secret, which memcheck has to report */
static void control(const secp256k1_context *ctx) {
    unsigned char secret[32];

    (void)ctx;
    fill(secret, 32, 65);
    SECP256K1_CHECKMEM_UNDEFINE(secret, 32);
    if (secret[0] == 65) {
        printf("control: branched on a secret\n");
    }
}

static const struct {
    const char *name;
    void (*run)(const secp256k1_context *ctx);
} calls[] = {
    {"control", control},
    {"anti_exfil_sign", anti_exfil_sign},
    {"generator_generate_blinded", generator_generate_blinded},
    {"pedersen_blind_sum", pedersen_blind_sum},
    {"pedersen_blind_generator_blind_sum", pedersen_blind_generator_blind_sum},
    {"rangeproof_sign", rangeproof_sign},
    {"rangeproof_rewind", rangeproof_rewind},
};

int main(int argc, char **argv) {
    secp256k1_context *ctx;
    size_t i;

    if (!SECP256K1_CHECKMEM_RUNNING()) {
        fprintf(stderr, "run under valgrind: valgrind %s <call>\n", argv[0]);
        return EXIT_FAILURE;
    }
    if (argc != 2) {
        fprintf(stderr, "usage: %s <call>\n", argv[0]);
        return 2;
    }
    for (i = 0; i < sizeof(calls) / sizeof(calls[0]); i++) {
        if (strcmp(argv[1], calls[i].name) == 0) {
            ctx = secp256k1_context_create(SECP256K1_CONTEXT_DECLASSIFY);
            calls[i].run(ctx);
            secp256k1_context_destroy(ctx);
            return EXIT_SUCCESS;
        }
    }
    fprintf(stderr, "%s: no call named %s\n", argv[0], argv[1]);
    return 2;
}
