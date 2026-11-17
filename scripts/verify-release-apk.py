#!/usr/bin/env python3
"""Inspect and verify the signed BiG Retail APK produced by a release build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import zipfile
from release_signing import expected_certificate

APPLICATION_ID = 'com.byghitech.classicpos'
ABIS = ('armeabi-v7a', 'arm64-v8a')


def signing_fingerprint(output):
    # AOSP prints either numbered signers or v3.1 SDK-range signers. One
    # certificate may be repeated for multiple ranges, but rotation/multi-signing
    # must not silently widen our single-certificate release policy.
    label = r'Signer (?:#([1-9][0-9]*)|\(minSdkVersion=[0-9]+(?: \(dev release=true\))?, maxSdkVersion=[0-9]+\))'
    lines = [line for line in output.splitlines()
             if line.startswith('Signer ') and ' certificate SHA-256 digest:' in line]
    parsed = [re.fullmatch(label + r' certificate SHA-256 digest: ([0-9a-fA-F]{64})', line)
              for line in lines]
    counts = [line for line in output.splitlines() if line.startswith('Number of signers:')]
    if (not parsed or any(match is None for match in parsed)
            or any(line != 'Number of signers: 1' for line in counts)):
        raise ValueError('未能确认唯一正式签名证书。')
    fingerprints = {match.group(2).lower() for match in parsed}
    numbered = {match.group(1) for match in parsed if match.group(1) is not None}
    if len(fingerprints) != 1 or len(numbered) > 1:
        raise ValueError('未能确认唯一正式签名证书。')
    return fingerprints.pop()


def android_tool(name):
    override = os.environ.get(name.upper() + '_BIN')
    if override:
        found = shutil.which(override)
        if found:
            return found
        raise ValueError(name.upper() + '_BIN 未指向可执行工具。')
    found = shutil.which(name)
    if found:
        return found
    roots = [os.environ.get('ANDROID_HOME'), os.environ.get('ANDROID_SDK_ROOT')]
    properties = Path(__file__).resolve().parents[1] / 'android/local.properties'
    if properties.is_file():
        for line in properties.read_text().splitlines():
            if line.startswith('sdk.dir='):
                roots.append(line.split('=', 1)[1].replace('\\:', ':').replace('\\\\', '\\'))
    roots += [str(Path.home() / 'Library/Android/sdk'), str(Path.home() / 'Android/Sdk')]
    for root in filter(None, roots):
        candidates = sorted((Path(root) / 'build-tools').glob('*/' + name),
                            key=lambda p: tuple(int(n) for n in re.findall(r'\d+', p.parent.name)), reverse=True)
        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    raise ValueError('找不到 Android SDK 工具：' + name)


def inspect(apk, version, code=None):
    if not 0 < apk.stat().st_size <= 512 * 1024 * 1024:
        raise ValueError('APK 大小超出客户端支持范围。')
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        if archive.testzip() is not None or 'AndroidManifest.xml' not in names:
            raise ValueError('APK ZIP 或 Manifest 无效。')
        for abi in ABIS:
            if 'lib/' + abi + '/libapp.so' not in names:
                raise ValueError('APK 缺少 ABI：' + abi)
    badging = subprocess.run([android_tool('aapt'), 'dump', 'badging', str(apk)],
                             capture_output=True, text=True, check=True).stdout
    package = next((line for line in badging.splitlines() if line.startswith('package: ')), '')
    fields = dict(word.split('=', 1) for word in shlex.split(package)[1:] if '=' in word)
    if code is None:
        value = fields.get('versionCode', '')
        if not re.fullmatch(r'[1-9][0-9]{0,9}', value):
            raise ValueError('APK 构建号无效。')
        code = int(value)
    if (fields.get('name') != APPLICATION_ID or fields.get('versionName') != version
            or fields.get('versionCode') != str(code) or not 1 <= code <= 2100000000):
        raise ValueError('APK 包名、版本或构建号与构建参数不符。')
    if 'application-debuggable' in badging:
        raise ValueError('不能使用可调试 APK。')
    certs = subprocess.run([android_tool('apksigner'), 'verify', '--verbose', '--print-certs', str(apk)],
                           capture_output=True, text=True, check=True).stdout
    if re.search(r'\bCN\s*=\s*Android Debug\b', certs, re.IGNORECASE):
        raise ValueError('不能使用 Android Debug 签名。')
    fingerprint = signing_fingerprint(certs)
    expected = expected_certificate(Path(__file__).resolve().parents[1])
    if expected != fingerprint:
        raise ValueError('签名不符合固定的正式证书指纹。')
    digest = hashlib.sha256()
    with apk.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return dict(applicationId=APPLICATION_ID, version=version, versionCode=code,
                packageFileName=apk.name, size=apk.stat().st_size, sha256=digest.hexdigest(),
                signingCertificateSha256=fingerprint, abis=list(ABIS))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('--version', required=True)
    codes = parser.add_mutually_exclusive_group(required=True)
    codes.add_argument('--build-number', type=int)
    codes.add_argument('--inspect-version-code', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.apk, args.version, args.build_number), ensure_ascii=False, indent=2))
    except ValueError as exc:
        parser.exit(1, 'APK 校验失败：' + str(exc) + '\n')
    except (OSError, zipfile.BadZipFile, subprocess.CalledProcessError):
        parser.exit(1, 'APK 校验失败：请检查 APK 文件、Android SDK 工具和签名。\n')


if __name__ == '__main__':
    main()
