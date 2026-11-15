"""AES ciphers for the Gree LAN protocol -- Android build.

Upstream greeclimate uses pycryptodome. On Android via Chaquopy, the
cross-compiled pycryptodome wheel from Chaquopy's package mirror is
missing several native cipher extension modules for arm64-v8a
(`Crypto.Cipher._raw_ecb`, also hit `Crypto.Util._cpuid_c` on newer
pycryptodome releases) -- AES import crashes the app at startup no matter
which recent pycryptodome version is pinned. See app/README.md and
app/build.gradle for the trail.

This vendored copy of cipher.py (used only in the Android build; the
desktop app imports the real, unmodified `greeclimate` package via pip)
implements the exact same two ciphers using `javax.crypto`, which is
part of the Android platform itself -- no native wheel, no packaging
risk, present on every device. The public API (CipherBase/CipherV1/
CipherV2, same constructor defaults, same encrypt()/decrypt() shapes) is
unchanged, so the rest of vendored greeclimate (device.py, discovery.py)
needs no changes.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Tuple, Union

from java import jclass

_logger = logging.getLogger(__name__)

_Cipher = jclass("javax.crypto.Cipher")
_SecretKeySpec = jclass("javax.crypto.spec.SecretKeySpec")
_GCMParameterSpec = jclass("javax.crypto.spec.GCMParameterSpec")

_GCM_TAG_BITS = 128
_GCM_TAG_BYTES = _GCM_TAG_BITS // 8


class CipherBase:
    def __init__(self, key: bytes) -> None:
        self._key: bytes = key

    @property
    def key(self) -> str:
        return self._key.decode()

    @key.setter
    def key(self, value: str) -> None:
        self._key = value.encode()

    def encrypt(self, data) -> Tuple[str, Union[str, None]]:
        raise NotImplementedError

    def decrypt(self, data, tag=None) -> dict:
        raise NotImplementedError

    def _key_spec(self):
        return _SecretKeySpec(self._key, "AES")


def _strip_trailing_garbage(decrypted_text: str) -> str:
    # Same defensive trim upstream does: drop anything after the final '}'
    # (ECB/PKCS7-style padding can leave trailing bytes once decoded as text).
    return decrypted_text.replace(decrypted_text[decrypted_text.rindex("}") + 1 :], "")


class CipherV1(CipherBase):
    def __init__(self, key: bytes = b"a3K8Bx%2r8Y7#xDh") -> None:
        super().__init__(key)

    def __pad(self, s: str) -> str:
        return s + (16 - len(s) % 16) * chr(16 - len(s) % 16)

    def encrypt(self, data) -> Tuple[str, Union[str, None]]:
        _logger.debug("Encrypting data: %s", data)
        cipher = _Cipher.getInstance("AES/ECB/NoPadding")
        cipher.init(_Cipher.ENCRYPT_MODE, self._key_spec())
        padded = self.__pad(json.dumps(data)).encode()
        encrypted = bytes(cipher.doFinal(padded))
        encoded = base64.b64encode(encrypted).decode()
        _logger.debug("Encrypted data: %s", encoded)
        return encoded, None

    def decrypt(self, data, tag=None) -> dict:
        _logger.debug("Decrypting data: %s", data)
        cipher = _Cipher.getInstance("AES/ECB/NoPadding")
        cipher.init(_Cipher.DECRYPT_MODE, self._key_spec())
        decoded = base64.b64decode(data)
        decrypted = bytes(cipher.doFinal(decoded)).decode()
        t = _strip_trailing_garbage(decrypted)
        _logger.debug("Decrypted data: %s", t)
        return json.loads(t)


class CipherV2(CipherBase):
    GCM_NONCE = b"\x54\x40\x78\x44\x49\x67\x5a\x51\x6c\x5e\x63\x13"
    GCM_AEAD = b"qualcomm-test"

    def __init__(self, key: bytes = b"{yxAHAY_Lm6pbC/<") -> None:
        super().__init__(key)

    def encrypt(self, data) -> Tuple[str, str]:
        _logger.debug("Encrypting data: %s", data)
        cipher = _Cipher.getInstance("AES/GCM/NoPadding")
        spec = _GCMParameterSpec(_GCM_TAG_BITS, self.GCM_NONCE)
        cipher.init(_Cipher.ENCRYPT_MODE, self._key_spec(), spec)
        cipher.updateAAD(self.GCM_AEAD)
        # Java appends the tag to the end of the ciphertext on encrypt.
        combined = bytes(cipher.doFinal(json.dumps(data).encode()))
        encrypted, tag = combined[:-_GCM_TAG_BYTES], combined[-_GCM_TAG_BYTES:]
        encoded = base64.b64encode(encrypted).decode()
        tag_b64 = base64.b64encode(tag).decode()
        _logger.debug("Encrypted data: %s", encoded)
        _logger.debug("Cipher digest: %s", tag_b64)
        return encoded, tag_b64

    def decrypt(self, data, tag=None) -> dict:
        _logger.debug("Decrypting data: %s", data)
        if tag is None:
            raise ValueError("CipherV2 requires an authentication tag")
        cipher = _Cipher.getInstance("AES/GCM/NoPadding")
        spec = _GCMParameterSpec(_GCM_TAG_BITS, self.GCM_NONCE)
        cipher.init(_Cipher.DECRYPT_MODE, self._key_spec(), spec)
        cipher.updateAAD(self.GCM_AEAD)
        decoded = base64.b64decode(data)
        decoded_tag = base64.b64decode(tag, validate=True)
        # Java expects ciphertext+tag concatenated for decrypt; it raises
        # javax.crypto.AEADBadTagException on mismatch (propagated as a
        # Chaquopy PyException, same effect as pycryptodome's ValueError).
        decrypted = bytes(cipher.doFinal(decoded + decoded_tag)).decode()
        t = _strip_trailing_garbage(decrypted)
        _logger.debug("Decrypted data: %s", t)
        return json.loads(t)
