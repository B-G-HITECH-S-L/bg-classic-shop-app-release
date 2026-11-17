"""SDK output compatibility without weakening the pinned single-certificate policy."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'scripts/verify-release-apk.py').is_file())
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('release_apk_verifier',ROOT/'scripts/verify-release-apk.py')
verifier=importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
sys.path.pop(0)
PIN='a'*64


def line(label='Signer #1', digest=PIN):
    return label+' certificate SHA-256 digest: '+digest


class SignerOutputTests(unittest.TestCase):
    def test_legacy_numbered_signer(self):
        self.assertEqual(verifier.signing_fingerprint(line()),PIN)

    def test_same_certificate_repeated_for_sdk_ranges(self):
        output='Number of signers: 1\n'+line('Signer (minSdkVersion=24, maxSdkVersion=32)')+'\n'+line('Signer (minSdkVersion=33, maxSdkVersion=2147483647)')
        self.assertEqual(verifier.signing_fingerprint(output),PIN)

    def test_dev_release_range(self):
        self.assertEqual(verifier.signing_fingerprint(line('Signer (minSdkVersion=33 (dev release=true), maxSdkVersion=2147483647)')),PIN)

    def test_source_stamp_is_not_an_application_signer(self):
        self.assertEqual(verifier.signing_fingerprint(line()+'\n'+line('Source Stamp Signer','b'*64)),PIN)

    def test_distinct_certificates_across_ranges_are_rejected(self):
        output=line('Signer (minSdkVersion=24, maxSdkVersion=32)')+'\n'+line('Signer (minSdkVersion=33, maxSdkVersion=2147483647)','b'*64)
        with self.assertRaises(ValueError): verifier.signing_fingerprint(output)

    def test_multiple_numbered_signers_are_rejected_even_with_same_digest(self):
        with self.assertRaises(ValueError): verifier.signing_fingerprint(line()+'\n'+line('Signer #2'))

    def test_malformed_or_unknown_certificate_lines_are_rejected(self):
        for invalid in ['',line(digest='bad'),line()+'\n'+line('Signer unknown'),line()+'\n'+line('Signer #2','invalid')]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError): verifier.signing_fingerprint(invalid)

    def test_explicit_signer_count_must_be_one(self):
        for count in ['0','2','unknown']:
            with self.subTest(count=count), self.assertRaises(ValueError):
                verifier.signing_fingerprint('Number of signers: '+count+'\n'+line())
