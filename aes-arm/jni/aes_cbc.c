#include <stdio.h>
#include <openssl/bio.h>
#include <openssl/evp.h>

//
// CONFIG: Enable debugging logs
//
#define DEBUG

//
// CONFIG: Use null IV
//
#define USE_NULL_IV


#ifdef DEBUG
#define DLOG(...) printf(__VA_ARGS__)
#define DBIO_DUMP(...) BIO_dump_fp(__VA_ARGS__)
#else
#define DLOG(...) do {} while (0)
#define DBIO_DUMP(...) do {} while (0)
#endif


// KEY
static const unsigned char cbc_key[] = {
    0x5F, 0xC4, 0xF4, 0xCE, 0x93, 0x5A, 0xBC, 0x48,
    0x01, 0x1B, 0x36, 0x85, 0x1F, 0xAE, 0xCA, 0xC8
};

// PLAINTEXT
static const unsigned char cbc_pt[] = {
    0x67, 0x85, 0xC2, 0xD2, 0x42, 0x40, 0x48, 0x18,
    0x31, 0xD8, 0xC4, 0x6C, 0x42, 0xD9, 0x62, 0xA1
};


#ifdef USE_NULL_IV

// IV
static const unsigned char cbc_iv[] = {
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};

// CIPHERTEXT
static const unsigned char cbc_ct[] = {
    0x83, 0xc8, 0x9f, 0x74, 0x5a, 0xda, 0xce, 0xb9,
    0x42, 0xc4, 0x12, 0x7b, 0x6d, 0xa2, 0x56, 0x24
};

#else

static const unsigned char cbc_iv[] = {
    0xD3, 0x22, 0x3A, 0x93, 0xC3, 0x42, 0x7A, 0xFD,
    0x63, 0x4C, 0xEB, 0x4A, 0x83, 0x26, 0x60, 0x3A
};

static const unsigned char cbc_ct[] = {
    0x9e, 0x15, 0x3d, 0x8c, 0x12, 0x12, 0xfa, 0x3b,
    0x58, 0xd0, 0xcb, 0xde, 0xb2, 0x4b, 0x26, 0x61
};

#endif





void aes_cbc_encrypt(void)
{
    EVP_CIPHER_CTX *ctx;
    int outlen, tmplen;
    unsigned char outbuf[1024];
    
    DLOG("\n");
    DLOG("[+] AES CBC Encrypt:\n");
    DLOG("[-]     IV:\n");
    DBIO_DUMP(stdout, cbc_iv, sizeof(cbc_iv));
    DLOG("[-]     Plaintext:\n");
    DBIO_DUMP(stdout, cbc_pt, sizeof(cbc_pt));
    
    // Initialize context
    ctx = EVP_CIPHER_CTX_new();
    
    // Set cipher type and mode
    EVP_EncryptInit_ex(ctx, EVP_aes_128_cbc(), NULL, NULL, NULL);
    
    // Set key
    EVP_EncryptInit_ex(ctx, NULL, NULL, cbc_key, NULL);
    
    // Set IV and IV length
    EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_SET_IVLEN, sizeof(cbc_iv), NULL);
    EVP_EncryptInit_ex(ctx, NULL, NULL, NULL, cbc_iv);
    
    // Encrypt plaintext 
    EVP_EncryptUpdate(ctx, outbuf, &outlen, cbc_pt, sizeof(cbc_pt));
    
    // Output encrypted block 
    DLOG("[-]     Ciphertext:\n");
    DBIO_DUMP(stdout, outbuf, outlen);
    
    // Assume only 16 bytes of data to work on
    EVP_EncryptFinal_ex(ctx, outbuf, &outlen);
    EVP_CIPHER_CTX_free(ctx);
}


void aes_cbc_decrypt(void)
{
    EVP_CIPHER_CTX *ctx;
    int outlen, tmplen;
    unsigned char outbuf[1024];
    
    DLOG("\n");
    DLOG("[+] AES CBC Decrypt:\n");
    DLOG("[-]     Ciphertext:\n");
    DBIO_DUMP(stdout, cbc_ct, sizeof(cbc_ct));
    
    // Initialize context
    ctx = EVP_CIPHER_CTX_new();
    
    // Set cipher type
    EVP_DecryptInit_ex(ctx, EVP_aes_128_cbc(), NULL, NULL, NULL);
    
    // Set key
    EVP_DecryptInit_ex(ctx, NULL, NULL, cbc_key, NULL);
    
    // Set IV and IV length
    EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_SET_IVLEN, sizeof(cbc_iv), NULL);
    EVP_DecryptInit_ex(ctx, NULL, NULL, NULL, cbc_iv);
    
    // Decrypt plaintext
    // NOTE: OpenSSL has an off-by-one bug where you need to pass in a size that
    //       is 1 more than the original length of the ciphertext.
    EVP_DecryptUpdate(ctx, outbuf, &outlen, cbc_ct, sizeof(cbc_ct) + 1);
    
    // Output decrypted block 
    DLOG("[-]     Plaintext:\n");
    DBIO_DUMP(stdout, outbuf, outlen);
    
    // Assume only 16 bytes of data to work on
    EVP_DecryptFinal_ex(ctx, outbuf, &outlen);
    EVP_CIPHER_CTX_free(ctx);
}


int main(int argc, char **argv)
{
    aes_cbc_encrypt();
    aes_cbc_decrypt();
}