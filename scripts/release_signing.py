#!/usr/bin/env python3
"""Read the explicitly pinned public release certificate (never a password)."""
import os
from pathlib import Path
import re


def expected_certificate(root):
    pin_file = Path(root) / 'config/release-cert.sha256'
    pin = pin_file.read_text().strip().lower() if pin_file.is_file() else None
    override = os.environ.get('ANDROID_RELEASE_CERT_SHA256')
    override = override.replace(':', '').lower() if override is not None else None
    if pin is not None and not re.fullmatch(r'[0-9a-f]{64}', pin):
        raise ValueError('正式证书指纹文件无效。')
    if override is not None and not re.fullmatch(r'[0-9a-f]{64}', override):
        raise ValueError('ANDROID_RELEASE_CERT_SHA256 必须是完整 SHA-256 指纹。')
    if pin and override and pin != override:
        raise ValueError('ANDROID_RELEASE_CERT_SHA256 与已固定的正式证书冲突。')
    if not (pin or override):
        raise ValueError('缺少固定的正式证书指纹：config/release-cert.sha256。')
    return pin or override


if __name__ == '__main__':
    import sys
    try:
        print(expected_certificate(Path(__file__).resolve().parents[1]))
    except (OSError, ValueError) as error:
        sys.exit(str(error))
