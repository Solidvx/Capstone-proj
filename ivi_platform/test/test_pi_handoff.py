import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from ivi_platform.scripts.prepare_pi_handoff import create_bundle, selected_files, EXTRAS
from ivi_platform.scripts.collect_pi_preflight import collect


class PiHandoffTests(unittest.TestCase):
    def populate(self,root):
        for name in EXTRAS:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture\n')

    def test_snapshot_includes_uncommitted_source_but_not_keys_or_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';root.mkdir();self.populate(root)
            for name in ('security/new_fix.py','security/key.bin','security/.env',
                         'security/models/private.py','ivi_platform/ui_qml/build/generated.cpp'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
            output=Path(directory)/'bundle'
            with patch('ivi_platform.scripts.prepare_pi_handoff.subprocess.check_output',return_value='base\n'):
                result=create_bundle(root,output)
            with tarfile.open(result['archive']) as package:
                names=package.getnames()
                self.assertIn('Capstone-handoff/security/new_fix.py',names)
                self.assertFalse(any('key.bin' in n or '.env' in n or '/models/' in n or '/build/' in n for n in names))
                manifest=json.load(package.extractfile('Capstone-handoff/HANDOFF-MANIFEST.json'))
                for name,digest in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(package.extractfile('Capstone-handoff/'+name).read()).hexdigest(),digest)
                self.assertIn(b'security/new_fix.py',package.extractfile('Capstone-handoff/HANDOFF-FILES.sha256').read())
            self.assertEqual(hashlib.sha256(Path(result['archive']).read_bytes()).hexdigest(),result['sha256'])
            with self.assertRaises(FileExistsError):create_bundle(root,output)

    def test_symlink_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';root.mkdir();self.populate(root)
            outside=Path(directory)/'outside.py';outside.write_text('do not include')
            (root/'security/leak.py').symlink_to(outside)
            with self.assertRaises(ValueError):selected_files(root)

    def test_environment_collection_does_not_read_key_or_hide_command_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            key=Path(directory)/'key.bin';key.write_bytes(bytes(32))
            failure={'exit_code':None,'stdout':'','stderr':'missing tool'}
            with patch('ivi_platform.scripts.collect_pi_preflight.command',return_value=failure), \
                 patch.object(Path,'read_bytes',side_effect=AssertionError('must not read key')):
                report=collect('ecu',str(key))
            self.assertEqual(report['key_metadata']['size_bytes'],32)
            self.assertEqual(report['commands']['can0']['stderr'],'missing tool')
            self.assertEqual(report['status'],'COLLECTED')
            self.assertNotIn('contents',report['key_metadata'])


if __name__=='__main__':unittest.main()
