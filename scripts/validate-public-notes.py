#!/usr/bin/env python3
"""Reject private deployment details in public release prose; never echo matches."""
import argparse
import html
import ipaddress
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

REPOSITORY = "B-G-HITECH-S-L/bg-classic-shop-app-release"
URL = re.compile(r"https?://[^\s<>\"'`]+", re.I)
DOMAIN = re.compile(r"(?<![A-Za-z0-9_@-])(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z][A-Za-z0-9-]+(?![A-Za-z0-9_-])")
IPV4 = re.compile(r"(?<![A-Za-z0-9_.])(?:\d{1,3}\.){3}\d{1,3}(?![A-Za-z0-9_.])")
IPV6 = re.compile(r"(?<![A-Za-z0-9_:])[0-9a-f:]*:[0-9a-f:]+(?:%[\w.-]+)?(?![A-Za-z0-9_:])", re.I)
IDENTIFIERS = {"com.byghitech.classicpos", "com.byghitech.classicpos.dev"}
FILE_EXTENSIONS = {"apk", "aab", "json", "fr3", "xml", "md", "pdf"}
RULES = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----", re.I)),
    ("credential-value", re.compile(r"(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|activation[_-]?code|license[_-]?code|密码|口令|激活码|授权码)\s*[:=：]\s*\S+", re.I)),
    ("credential-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|(?:AKIA|ASIA)[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{20,})\b")),
    ("credential-jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\b")),
    ("local-path", re.compile(r"/(?:Users|home|private|var|tmp|root)/|(?<![A-Za-z0-9])[A-Za-z]:[\\/]|\\\\[A-Za-z0-9_.-]+\\")),
    ("private-build-detail", re.compile(r"keystore\.properties|key\.properties|license\.local\.json|release-defines\.json|build-info\.json|pubspec\.lock|r8-mapping\.txt|app\.android-[\w-]+\.symbols|\.(?:jks|keystore|p12|pfx)\b|sourceDirty|sourceCommit|storePassword|keyPassword", re.I)),
    ("private-confirmation", re.compile(r"私有发版确认|完整发版确认单|内部验收记录|源码冻结快照|private release confirmation", re.I)),
    ("local-host", re.compile(r"\blocalhost\b", re.I)),
]


def allowed_public_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
            return False
        if parsed.hostname == "github.com":
            prefix = "/" + REPOSITORY
            return parsed.path.rstrip("/") == prefix or parsed.path.startswith(prefix + "/releases/") or parsed.path.startswith(prefix + "/issues/")
        if parsed.hostname == "raw.githubusercontent.com":
            return re.fullmatch(r"/B-G-HITECH-S-L/bg-pos-aio-release/(?:main|[0-9a-f]{40})/application/application-catalog\.json", parsed.path) is not None
    except ValueError:
        pass
    return False


def find_violations(text):
    normalized = unicodedata.normalize("NFKC", html.unescape(unquote(text)))
    normalized = re.sub(r"[\u200b-\u200d\u2060\ufeff]", "", normalized)
    found = set()
    for number, line in enumerate(normalized.splitlines(), 1):
        for rule, pattern in RULES:
            if pattern.search(line):
                found.add((number, rule))
        for match in URL.finditer(line):
            value = match.group().rstrip(".,;:!?，。；：？！）)]}")
            if not allowed_public_url(value):
                found.add((number, "unapproved-url"))
        prose = URL.sub(lambda match: " " * len(match.group()), line)
        for pattern in (IPV4, IPV6):
            for match in pattern.finditer(prose):
                candidate = match.group().split("%", 1)[0]
                try:
                    ipaddress.ip_address(candidate)
                except ValueError:
                    continue
                found.add((number, "ip-address"))
        for match in DOMAIN.finditer(prose):
            value = match.group().lower()
            if value in IDENTIFIERS:
                continue
            if value.rsplit(".", 1)[-1] in FILE_EXTENSIONS:
                continue
            found.add((number, "unapproved-hostname"))
        context = re.search(r"隐藏|开发设置|版本号|hidden|developer settings|ajustes de desarrollo|versión", line, re.I)
        taps = re.search(r"(?:点击|轻点|点按).{0,40}(?:5|五)\s*次|(?:tap|click).{0,60}(?:five|5)\b|\bfive\s+(?:taps|clicks)\b|(?:pulse|toque|clic).{0,60}(?:cinco|5)\s*veces", line, re.I)
        if context and taps:
            found.add((number, "maintenance-unlock-detail"))
    return [{"line": line, "rule": rule} for line, rule in sorted(found)]


def main():
    parser = argparse.ArgumentParser(description="检查公开 Release 正文；不输出命中的原文或凭据。")
    parser.add_argument("notes", type=Path)
    args = parser.parse_args()
    try:
        text = args.notes.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print("无法读取 UTF-8 公开发布说明。", file=sys.stderr)
        return 2
    issues = find_violations(text)
    if issues:
        print("公开发布说明包含禁止公开的内容，请将完整环境与验收信息保留在私有记录：", file=sys.stderr)
        for issue in issues:
            print("  第 {line} 行：{rule}".format(**issue), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
