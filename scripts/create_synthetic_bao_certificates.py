"""Create local synthetic TLS identities; never prints private key material.

CA keys remain operator-only on this Pi for synthetic development. Production
requires offline CA/recovery custody, explicitly not satisfied by this helper.
"""

import datetime
import ipaddress
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

DEST = Path.home() / ".local/share/health03/operator/synthetic-pki"


def save(name, data):
    with os.fdopen(
        os.open(DEST / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
    ) as output:
        output.write(data)


def issue(name, issuer=None, server=False):
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer[1].subject if issuer else subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=90 if issuer else 365))
        .add_extension(
            x509.BasicConstraints(ca=issuer is None, path_length=0 if issuer is None else None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=issuer is None,
                crl_sign=issuer is None,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
    )
    if issuer:
        certificate = certificate.add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH]
            ),
            critical=False,
        )
    if server:
        certificate = certificate.add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("bao.health03.internal"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
    cert = certificate.sign(issuer[0] if issuer else key, hashes.SHA256())
    save(
        name + ".key",
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    save(name + ".crt", cert.public_bytes(serialization.Encoding.PEM))
    return key, cert


def main():
    DEST.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(DEST.parent, 0o700)
    DEST.mkdir(mode=0o700)  # Refuse overwriting an existing local trust root.
    server_ca = issue("server-ca")
    issue("server", server_ca, server=True)
    admin_ca = issue("admin-ca")
    issue("health03-app", admin_ca)
    issue("health03-operator", admin_ca)
    print("Created synthetic 90-day identities in an operator-only directory; no keys printed.")


if __name__ == "__main__":
    main()
