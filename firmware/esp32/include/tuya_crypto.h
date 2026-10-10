// tuya_crypto.h 🔐 Примитивы для протокола TuyaOpen (порт mpy/lib/compat.py на mbedtls).
#pragma once
#include <Arduino.h>

namespace tcrypto {
// AES-128-GCM. key 16 байт, nonce 12, tag 16. Возвращает false при ошибке mbedtls.
bool gcmEncrypt(const uint8_t key[16], const uint8_t nonce[12], const uint8_t* aad, size_t aadLen,
                const uint8_t* in, size_t inLen, uint8_t* out, uint8_t tag[16]);
bool gcmDecrypt(const uint8_t key[16], const uint8_t nonce[12], const uint8_t* aad, size_t aadLen,
                const uint8_t* in, size_t inLen, const uint8_t tag[16], uint8_t* out);
// AES-128-ECB + PKCS7 (старый формат 2.2 и QR). out должен вмещать inLen + 16; возвращает длину.
size_t aesEcbEncrypt(const uint8_t key[16], const uint8_t* in, size_t inLen, uint8_t* out);
size_t aesEcbDecrypt(const uint8_t key[16], const uint8_t* in, size_t inLen, uint8_t* out);  // 0 при ошибке набивки

String md5Hex(const uint8_t* data, size_t len);
String md5Hex(const String& s);
String sha256Hex(const uint8_t* data, size_t len);
String hmacSha256Hex(const uint8_t* key, size_t keyLen, const uint8_t* data, size_t len);
String hmacSha256Hex(const String& key, const String& data);

String base64Encode(const uint8_t* data, size_t len);
size_t base64Decode(const String& s, uint8_t* out, size_t outMax);   // 0 при ошибке
String hexEncode(const uint8_t* data, size_t len);
size_t hexDecode(const String& s, uint8_t* out, size_t outMax);

void randomBytes(uint8_t* out, size_t len);   // esp_random
uint32_t crc32(const uint8_t* data, size_t len);
}  // namespace tcrypto
