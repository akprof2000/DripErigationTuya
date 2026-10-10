// tuya_crypto.cpp 🔐 Примитивы протокола TuyaOpen на mbedtls (порт mpy/lib/compat.py).
// В MicroPython GCM собирался вручную поверх ECB; здесь всё делает mbedtls из ESP-IDF.
#include "tuya_crypto.h"

#include <esp_random.h>
#include <mbedtls/aes.h>
#include <mbedtls/base64.h>
#include <mbedtls/gcm.h>
#include <mbedtls/md.h>
#include <mbedtls/md5.h>
#include <mbedtls/sha256.h>
#include <string.h>

namespace tcrypto {

// ------------------------------------------------------------------ AES-128-GCM
bool gcmEncrypt(const uint8_t key[16], const uint8_t nonce[12], const uint8_t* aad, size_t aadLen,
                const uint8_t* in, size_t inLen, uint8_t* out, uint8_t tag[16]) {
  mbedtls_gcm_context ctx;
  mbedtls_gcm_init(&ctx);
  int rc = mbedtls_gcm_setkey(&ctx, MBEDTLS_CIPHER_ID_AES, key, 128);
  if (rc == 0) {
    rc = mbedtls_gcm_crypt_and_tag(&ctx, MBEDTLS_GCM_ENCRYPT, inLen, nonce, 12, aad, aadLen, in, out, 16, tag);
  }
  mbedtls_gcm_free(&ctx);
  return rc == 0;
}

bool gcmDecrypt(const uint8_t key[16], const uint8_t nonce[12], const uint8_t* aad, size_t aadLen,
                const uint8_t* in, size_t inLen, const uint8_t tag[16], uint8_t* out) {
  mbedtls_gcm_context ctx;
  mbedtls_gcm_init(&ctx);
  int rc = mbedtls_gcm_setkey(&ctx, MBEDTLS_CIPHER_ID_AES, key, 128);
  if (rc == 0) {
    // auth_decrypt сам сверяет тег (MBEDTLS_ERR_GCM_AUTH_FAILED при несовпадении)
    rc = mbedtls_gcm_auth_decrypt(&ctx, inLen, nonce, 12, aad, aadLen, tag, 16, in, out);
  }
  mbedtls_gcm_free(&ctx);
  return rc == 0;
}

// ------------------------------------------------------------------ AES-128-ECB + PKCS7
size_t aesEcbEncrypt(const uint8_t key[16], const uint8_t* in, size_t inLen, uint8_t* out) {
  mbedtls_aes_context ctx;
  mbedtls_aes_init(&ctx);
  if (mbedtls_aes_setkey_enc(&ctx, key, 128) != 0) {
    mbedtls_aes_free(&ctx);
    return 0;
  }
  const uint8_t pad = 16 - (inLen % 16);   // PKCS7: всегда есть хотя бы один байт набивки
  const size_t total = inLen + pad;
  uint8_t block[16];
  for (size_t off = 0; off < total; off += 16) {
    for (size_t i = 0; i < 16; i++) block[i] = (off + i < inLen) ? in[off + i] : pad;
    mbedtls_aes_crypt_ecb(&ctx, MBEDTLS_AES_ENCRYPT, block, out + off);
  }
  mbedtls_aes_free(&ctx);
  return total;
}

size_t aesEcbDecrypt(const uint8_t key[16], const uint8_t* in, size_t inLen, uint8_t* out) {
  if (inLen == 0 || inLen % 16 != 0) return 0;
  mbedtls_aes_context ctx;
  mbedtls_aes_init(&ctx);
  if (mbedtls_aes_setkey_dec(&ctx, key, 128) != 0) {
    mbedtls_aes_free(&ctx);
    return 0;
  }
  for (size_t off = 0; off < inLen; off += 16) mbedtls_aes_crypt_ecb(&ctx, MBEDTLS_AES_DECRYPT, in + off, out + off);
  mbedtls_aes_free(&ctx);
  const uint8_t pad = out[inLen - 1];
  if (pad < 1 || pad > 16 || pad > inLen) return 0;
  for (size_t i = inLen - pad; i < inLen; i++) {
    if (out[i] != pad) return 0;
  }
  return inLen - pad;
}

// ------------------------------------------------------------------ хеши
String hexEncode(const uint8_t* data, size_t len) {
  static const char digits[] = "0123456789abcdef";
  String s;
  s.reserve(len * 2);
  for (size_t i = 0; i < len; i++) {
    s += digits[data[i] >> 4];
    s += digits[data[i] & 0x0F];
  }
  return s;
}

static int hexVal(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

size_t hexDecode(const String& s, uint8_t* out, size_t outMax) {
  const size_t n = s.length();
  if (n % 2 != 0 || n / 2 > outMax) return 0;
  for (size_t i = 0; i < n; i += 2) {
    const int hi = hexVal(s[i]), lo = hexVal(s[i + 1]);
    if (hi < 0 || lo < 0) return 0;
    out[i / 2] = (uint8_t)((hi << 4) | lo);
  }
  return n / 2;
}

String md5Hex(const uint8_t* data, size_t len) {
  uint8_t d[16];
  if (mbedtls_md5_ret(data, len, d) != 0) return String();
  return hexEncode(d, 16);
}

String md5Hex(const String& s) { return md5Hex((const uint8_t*)s.c_str(), s.length()); }

String sha256Hex(const uint8_t* data, size_t len) {
  uint8_t d[32];
  if (mbedtls_sha256_ret(data, len, d, 0) != 0) return String();
  return hexEncode(d, 32);
}

String hmacSha256Hex(const uint8_t* key, size_t keyLen, const uint8_t* data, size_t len) {
  uint8_t d[32];
  const mbedtls_md_info_t* info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (!info || mbedtls_md_hmac(info, key, keyLen, data, len, d) != 0) return String();
  return hexEncode(d, 32);
}

String hmacSha256Hex(const String& key, const String& data) {
  return hmacSha256Hex((const uint8_t*)key.c_str(), key.length(), (const uint8_t*)data.c_str(), data.length());
}

// ------------------------------------------------------------------ base64
String base64Encode(const uint8_t* data, size_t len) {
  size_t need = 0;
  mbedtls_base64_encode(nullptr, 0, &need, data, len);   // узнать размер (с завершающим нулём)
  String s;
  if (need == 0) return s;
  uint8_t* buf = (uint8_t*)malloc(need);
  if (!buf) return s;
  size_t olen = 0;
  if (mbedtls_base64_encode(buf, need, &olen, data, len) == 0) s = String((const char*)buf, olen);
  free(buf);
  return s;
}

size_t base64Decode(const String& s, uint8_t* out, size_t outMax) {
  size_t olen = 0;
  if (mbedtls_base64_decode(out, outMax, &olen, (const uint8_t*)s.c_str(), s.length()) != 0) return 0;
  return olen;
}

// ------------------------------------------------------------------ прочее
void randomBytes(uint8_t* out, size_t len) { esp_fill_random(out, len); }

// CRC-32 (IEEE 802.3, как binascii.crc32): нужен только для старых кадров 2.2, скорость не важна
uint32_t crc32(const uint8_t* data, size_t len) {
  uint32_t crc = 0xFFFFFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320 & (0 - (crc & 1)));
  }
  return crc ^ 0xFFFFFFFF;
}

}  // namespace tcrypto
