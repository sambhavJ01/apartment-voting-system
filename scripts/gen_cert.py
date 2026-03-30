"""
Generate a self-signed TLS certificate for local HTTPS development.

Usage:
    python -m scripts.gen_cert              # writes certs/cert.pem + certs/key.pem
    python -m scripts.gen_cert --days 365   # custom validity period

The certificate covers:
  - DNS: localhost
  - IP:  127.0.0.1

Import certs/cert.pem into your OS / browser trust store once to silence the
"Not Secure" warning in development.
"""
import argparse
import datetime
import ipaddress
import pathlib

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_DIR = pathlib.Path(__file__).resolve().parent.parent / "certs"


def generate(days: int = 825) -> None:
    CERT_DIR.mkdir(exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Apartment Voting System"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=days))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    key_path = CERT_DIR / "key.pem"
    cert_path = CERT_DIR / "cert.pem"

    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    expiry = (now + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"Certificate  : {cert_path}")
    print(f"Private key  : {key_path}")
    print(f"Valid until  : {expiry}")
    print()
    print("To trust this cert on Windows (run as Administrator):")
    print(f"  certutil -addstore Root {cert_path.resolve()}")
    print()
    print("To trust this cert on macOS:")
    print(f"  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain {cert_path.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate self-signed dev cert")
    parser.add_argument("--days", type=int, default=825, help="Validity in days (default 825)")
    args = parser.parse_args()
    generate(args.days)
