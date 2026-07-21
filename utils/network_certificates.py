"""Resolve a valid CA bundle for online data requests."""

import os
import sys
from pathlib import Path
from typing import Optional


def configure_ca_bundle(base: Optional[Path] = None) -> Optional[Path]:
    """Replace stale certificate environment paths with a usable bundle."""
    candidates = []

    if base is not None:
        candidates.append(Path(base) / "certifi" / "cacert.pem")
    elif getattr(sys, "frozen", False):
        candidates.append(Path(sys._MEIPASS) / "certifi" / "cacert.pem")

    try:
        import certifi

        candidates.append(Path(certifi.where()))
    except Exception:
        pass

    bundle = next((path for path in candidates if path.is_file()), None)
    if bundle is None:
        for variable in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
            if os.environ.get(variable) and not Path(os.environ[variable]).is_file():
                os.environ.pop(variable, None)
        return None

    for variable in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        os.environ[variable] = str(bundle)
    return bundle
