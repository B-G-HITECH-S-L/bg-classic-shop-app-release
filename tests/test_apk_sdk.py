"""Actual Android SDK signature verification, using disposable test keys only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SDK = Path(os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or Path.home()/'Library/Android/sdk')
TOOLS = sorted((SDK/'build-tools').glob('*/apksigner'), reverse=True)
PLATFORMS = sorted((SDK/'platforms').glob('*/android.jar'), reverse=True)
AVAILABLE = bool(TOOLS and PLATFORMS and shutil.which('keytool'))


@unittest.skipUnless(AVAILABLE, 'Requires Android SDK and JDK test tools')
class RealApkSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='retail-apk-signature-fixtures-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.tools = TOOLS[0].parent
        for name, dn in [('release','CN=Release Fixture'), ('debug','CN=Android Debug,O=Android,C=US'), ('other','CN=Other Fixture')]:
            cls.run_tool('keytool','-genkeypair','-keystore',str(cls.root/(name+'.p12')),'-alias','fixture',
                '-storepass','fixture-only','-keypass','fixture-only','-keyalg','RSA','-keysize','2048',
                '-validity','1','-dname',dn,'-noprompt')
        manifest = cls.root/'AndroidManifest.xml'
        manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.byghitech.classicpos" android:versionCode="7" android:versionName="0.0.1"><uses-sdk android:minSdkVersion="23" android:targetSdkVersion="35"/><application android:hasCode="false" android:debuggable="false" android:label="Fixture"/></manifest>''')
        unsigned = cls.root/'unsigned.apk'
        cls.run_tool(str(cls.tools/'aapt'),'package','-f','-M',str(manifest),'-I',str(PLATFORMS[0]),'-F',str(unsigned))
        with zipfile.ZipFile(unsigned,'a') as archive:
            for abi in ('armeabi-v7a','arm64-v8a'):
                archive.writestr('lib/'+abi+'/libapp.so',b'fixture library')
        aligned = cls.root/'aligned.apk'
        cls.run_tool(str(cls.tools/'zipalign'),'-f','4',str(unsigned),str(aligned))
        for name in ('release','debug','other'):
            cls.run_tool(str(cls.tools/'apksigner'),'sign','--ks',str(cls.root/(name+'.p12')),'--ks-key-alias','fixture',
                '--ks-pass','pass:fixture-only','--out',str(cls.root/(name+'.apk')),str(aligned))
        cert = cls.root/'release.der'
        cls.run_tool('keytool','-exportcert','-keystore',str(cls.root/'release.p12'),'-storepass','fixture-only',
            '-alias','fixture','-file',str(cert))
        cls.pin = hashlib.sha256(cert.read_bytes()).hexdigest()
        (cls.root/'scripts').mkdir()
        for file in ('verify-release-apk.py','release_signing.py'):
            shutil.copy2(ROOT/'scripts'/file,cls.root/'scripts'/file)
        (cls.root/'config').mkdir()
        (cls.root/'config/release-cert.sha256').write_text(cls.pin+'\n')

    @staticmethod
    def run_tool(*args):
        return subprocess.run(args,check=True,capture_output=True,text=True,timeout=30)

    def verify(self, name):
        env = dict(os.environ,AAPT_BIN=str(self.tools/'aapt'),APKSIGNER_BIN=str(self.tools/'apksigner'))
        env.pop('ANDROID_RELEASE_CERT_SHA256',None)
        return subprocess.run([sys.executable,str(self.root/'scripts/verify-release-apk.py'),str(self.root/(name+'.apk')),
            '--version','0.0.1','--inspect-version-code'],env=env,capture_output=True,text=True,timeout=30)

    def test_pinned_fixture_passes(self):
        result=self.verify('release')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['versionCode'],7)
        self.assertEqual(json.loads(result.stdout)['signingCertificateSha256'],self.pin)

    def test_unsigned_fixture_is_rejected(self):
        self.assertNotEqual(self.verify('unsigned').returncode,0)

    def test_debug_and_other_certificates_are_rejected(self):
        for name in ('debug','other'):
            with self.subTest(name=name):
                self.assertNotEqual(self.verify(name).returncode,0)

    def test_repacked_signed_fixture_is_rejected(self):
        shutil.copy2(self.root/'release.apk',self.root/'tampered.apk')
        with zipfile.ZipFile(self.root/'tampered.apk','a') as archive:
            archive.writestr('added-after-signing.txt',b'tampered')
        self.assertNotEqual(self.verify('tampered').returncode,0)

    def test_unsigned_apk_is_rejected_by_publish_entry_before_github(self):
        with tempfile.TemporaryDirectory(prefix='retail-publish-unsigned-') as tmp:
            root=Path(tmp)
            (root/'scripts').mkdir(); (root/'config').mkdir(); (root/'bin').mkdir()
            version=root/'dist/v0.0.1'; version.mkdir(parents=True)
            for file in ('release.sh','verify-release-apk.py','release_signing.py'):
                shutil.copy2(ROOT/'scripts'/file,root/'scripts'/file)
            (root/'config/release-cert.sha256').write_text(self.pin+'\n')
            shutil.copy2(self.root/'unsigned.apk',version/'big-retail.apk')
            git=root/'bin/git'; git.write_text('#!/bin/sh\necho git@github.com:B-G-HITECH-S-L/bg-classic-shop-app-release.git\n'); git.chmod(0o755)
            gh=root/'bin/gh'; gh.write_text('#!'+sys.executable+'\nimport pathlib\npathlib.Path('+repr(str(root/'github-called'))+').touch()\nraise SystemExit(99)\n'); gh.chmod(0o755)
            env=dict(os.environ,PATH=str(root/'bin')+os.pathsep+os.environ['PATH'],
                     AAPT_BIN=str(self.tools/'aapt'),APKSIGNER_BIN=str(self.tools/'apksigner'))
            env.pop('ANDROID_RELEASE_CERT_SHA256',None)
            result=subprocess.run([str(root/'scripts/release.sh'),'v0.0.1'],env=env,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('APK 正式签名或产物校验失败',result.stderr)
            self.assertFalse((root/'github-called').exists())
            self.assertFalse((root/'dist/.release-publish.lock').exists())
