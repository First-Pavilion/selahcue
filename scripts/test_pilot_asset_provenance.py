"""Synthetic file controls, not actual Tauri build/package proof."""
import json
import contextlib
import io
import tempfile
from pathlib import Path
import unittest
try:
 import pilot_asset_provenance as assets
except ImportError:
 assets = None

class AssetTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(assets, 'asset policy missing')
  self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
  self.root = Path(self.temp.name)
  (self.root / 'settings.js').write_text('Help: OPENAI_API_KEY; no credential value')
  self.inventory = {'settings.js': assets.file_digest(self.root / 'settings.js')[1]}
 def test_public_help_label_passes_asset_policy(self):
  snapshot = assets.capture_assets(self.root, self.inventory)
  assets.verify_unchanged(snapshot)
 def test_actual_key_in_asset_fails(self):
  secret = b'synthetic-actual-key-canary-874ab'
  (self.root / 'settings.js').write_bytes(secret)
  self.inventory['settings.js'] = assets.file_digest(self.root / 'settings.js')[1]
  with self.assertRaisesRegex(assets.PolicyError, 'asset-known-secret'):
   assets.capture_assets(self.root, self.inventory, known_secrets=(secret,))
 def test_extra_changed_and_symlink_assets_fail(self):
  snapshot = assets.capture_assets(self.root, self.inventory)
  (self.root / 'extra.js').write_text('extra')
  with self.assertRaises(assets.PolicyError): assets.verify_unchanged(snapshot)
  (self.root / 'extra.js').unlink(); (self.root / 'settings.js').write_text('changed')
  with self.assertRaises(assets.PolicyError): assets.verify_unchanged(snapshot)
 def test_fresh_codegen_directory_rejects_stale_cache(self):
  output = self.root / 'out'; output.mkdir(); (output / 'old.br').write_bytes(b'stale')
  with self.assertRaisesRegex(assets.PolicyError, 'asset-output-not-fresh'):
   assets.begin_codegen(output)
 def test_generated_inventory_and_emitted_packaged_hash_chain(self):
  source = self.root / 'source'; source.mkdir()
  (self.root / 'settings.js').rename(source / 'settings.js')
  inputs = assets.capture_assets(source, self.inventory)
  output = self.root / 'fresh'; output.mkdir(); token = assets.begin_codegen(output)
  (output / 'asset.br').write_bytes(b'explicit-synthetic-encoded-output')
  generated = {'asset.br': assets.file_digest(output / 'asset.br')[1]}
  op = self.root / 'operator'; op.write_bytes(b'synthetic-emitted-native')
  digest = assets.file_digest(op)[1]
  result = assets.finish_codegen(inputs, token, generated, emitted_operator=op,
                                 emitted_sha256=digest, packaged_sha256=digest)
  self.assertEqual(result.coverage, 'synthetic-helper-chain-only')
  with self.assertRaisesRegex(assets.PolicyError, 'asset-operator-binding'):
   assets.finish_codegen(inputs, token, generated, emitted_operator=op,
                         emitted_sha256=digest, packaged_sha256='0'*64)

 def test_config_toolchain_codegen_hash_inputs_and_features_are_pinned(self):
  root = self.root / 'contract'; root.mkdir()
  for name in ('Cargo.lock','rust-toolchain.toml','embedded_assets.rs','assets.rs'):
   (root / name).write_bytes(b'explicit-synthetic-reviewed-input')
  (root / 'tauri.conf.json').write_text('{"build":{"frontendDist":"dist"}}')
  pins = {p.name: assets.file_digest(p)[1] for p in root.iterdir()}
  assets.verify_build_contract(root, pins, config_path='tauri.conf.json', frontend_dist='dist', codegen_features=('compression',))
  for features, dist in [((), 'dist'), (('compression',), 'other')]:
   with self.assertRaises(assets.PolicyError):
    assets.verify_build_contract(root, pins, config_path='tauri.conf.json', frontend_dist=dist, codegen_features=features)
 def test_cargo_emitted_output_binding_and_debug_rejection(self):
  op = self.root / 'emitted'; op.write_bytes(b'synthetic-native-output')
  digest = assets.file_digest(op)[1]; log = self.root / 'cargo.json'
  row = {'reason':'compiler-artifact','target':{'name':'selahcue-operator'},'executable':str(op),'profile':{'debug_assertions':False}}
  log.write_text(json.dumps(row)); assets.verify_cargo_output(log, op, digest)
  row['profile']['debug_assertions'] = True; log.write_text(json.dumps(row))
  with self.assertRaisesRegex(assets.PolicyError,'asset-cargo-binding'): assets.verify_cargo_output(log, op, digest)
 def test_symlink_source_and_extra_generated_output_are_rejected(self):
  (self.root / 'settings.js').unlink(); (self.root / 'settings.js').symlink_to(self.root / 'missing')
  with self.assertRaises(assets.PolicyError): assets.capture_assets(self.root, self.inventory)
 def test_secret_bytes_and_fragments_never_appear_in_errors_or_repr(self):
  secret = b'synthetic-private-asset-canary-9823'
  (self.root / 'settings.js').write_bytes(secret)
  self.inventory['settings.js'] = assets.file_digest(self.root / 'settings.js')[1]
  output = io.StringIO()
  with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
   try: assets.capture_assets(self.root, self.inventory, known_secrets=(secret,))
   except assets.PolicyError as error: output.write(str(error))
  for index in range(len(secret)-7): self.assertNotIn(secret[index:index+8].decode(),output.getvalue())

if __name__ == '__main__': unittest.main()
