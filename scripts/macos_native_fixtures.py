"""Finite reconstructed native-fixture preparation, never native execution.

Construction authority: N:68/148/187/221, T1:74/88 and T2:90 named in
inputs.json. This is NOT the unrecovered historical test_coverage_native.py.
Only hash-verified original pure modules execute; provenance is inert.
"""
from __future__ import annotations

import argparse
import builtins
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
from pathlib import Path, PurePosixPath
import stat
import sys
from types import ModuleType

BUNDLE = Path(__file__).absolute().parent / 'fixtures/macos-native-proof'
INPUTS_SHA256 = 'a4892c1c8d3975690100102defb4093fe10cdaa4a39507d456eb69e933350788'
# Canonical contract excluding only comparator's self-identity avoids a circular
# source/manifest hash. Every other manifest field has this independent pin.
FRAMES_CONTRACT_SHA256 = 'a9d2548e64103fec425933887cfe610ed2baa799183b52e7bf8fc3a975480487'
MATRIX_INPUT = 'bb4d75ea9bd6d18b42b5bc24eddfe1f4378f947aea6d572172828a9f226432d9'
MATRIX_OUTPUT = '5c0aa4104a2e34dfdbad2e7d7a72dc9b1926de887c6a1b82ff1828ceef56b75f'
WRAPPER_RAW = '9596a90312891c2a348f0089bfff9f739f5e2dfcb82a8d54f532aea10fcbcba8'
WRAPPER_PINS = (
    (524288, 'dfdf3fb42fc1ce910f72c3662e1574ed9fe2c1824eb9afb838dd6e7169d920ef'),
    (524289, 'a90bd62fcf791441a48eeb90b2440e7dcca2ab9386e7d2dc7c2b4e086c93710c'),
    (528326, '3d1a558349289d600fab3fcbf2a2492c074e9efbb53d2fefb688440f8fda5899'),
)
MAX_STDIN = 32 * 1024 * 1024
MAX_FRAME = 1100000
MAX_STDOUT = 64 * 1024 * 1024
MAX_LINE = 8 * 1024 * 1024
MODULES = ('coverage_contract', 'coverage_json', 'coverage_index', 'coverage_compile',
           'coverage_requests', 'coverage_response')
FLAGS = ('prayer_points', 'scripture_extraction', 'social_excerpts', 'chapter_markers',
         'notable_quotations', 'short_summary', 'podcast_show_notes', 'short_description')
TEMPLATES = ('full_outline_scriptures', 'full_outline', 'summary', 'devotional')
WHITESPACE = '\t\n\v\f\r \u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000'
NON_WHITESPACE = '\x1c\x1d\x1e\x1f\u180e\u200b\ufeff'
PICKER = ['KJV', 'WEB', 'ASV', 'WEBBE', 'DBY']
HEADINGS = {
    'introduction': 'Introduction', 'illustrations': 'Illustrations', 'quotes': 'Notable quotations',
    'prayer_points': 'Prayer points', 'calls_to_action': 'Calls to action', 'key_lessons': 'Key lessons',
    'chapter_markers': 'Chapter markers', 'social_excerpts': 'Social excerpts',
    'podcast_show_notes': 'Podcast show notes', 'short_description': 'Short description',
}
BATCH_COUNTS = (('matrix',1024), ('translations',8), ('content',1), ('helper scan',1),
                ('Unicode',64), ('scalar caps',3), ('list caps',2), ('wrapper',3),
                ('raw digest',2), ('public cap',1), ('combined scriptures',2))


class ProofError(ValueError):
    """Safe failure naming the violated invariant, without raw payloads."""


def require(condition, name):
    if not condition:
        raise ProofError(name)


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def _json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(ProofError('nonfinite JSON')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ProofError('invalid JSON') from exc


def _regular(path):
    # Reject symlinks in the full ancestry before opening, including bundle root.
    try:
        for ancestor in (path, *path.parents):
            require(not ancestor.is_symlink(), 'symlink input')
        require(stat.S_ISREG(path.lstat().st_mode), 'nonregular input')
        return path.read_bytes()
    except OSError as exc:
        raise ProofError('missing/unreadable input') from exc


def _closure(root, expected):
    require(root.is_dir() and not root.is_symlink(), 'missing/symlink bundle directory')
    found = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'symlink bundle member')
        if path.is_dir():
            relative = path.relative_to(BUNDLE).as_posix() + '/'
            require(any(name.startswith(relative) for name in expected), 'extra bundle directory')
            continue
        require(stat.S_ISREG(path.lstat().st_mode), 'nonregular bundle member')
        found.add(path.relative_to(BUNDLE).as_posix())
    return found


def _frame_manifest():
    raw = _regular(BUNDLE / 'frames.json')
    manifest = _json(raw)
    require(type(manifest) is dict and set(manifest) == {
        'version', 'inputs_sha256', 'historical', 'batches', 'pure_rejections',
        'independent_reproduction', 'comparator',
    }, 'frame manifest fields')
    contract = {key: value for key, value in manifest.items() if key != 'comparator'}
    require(sha256(wire(contract)).hexdigest() == FRAMES_CONTRACT_SHA256,
            'frozen frame contract identity')
    source = _regular(Path(__file__).absolute())
    source_identity = {
        'path': 'scripts/macos_native_fixtures.py',
        'bytes': len(source), 'sha256': sha256(source).hexdigest(),
    }
    _same(manifest['comparator'], source_identity, 'comparator source identity')
    # The authenticated contract fixes its own order. Append the fixed-order
    # identity last rather than accepting the untrusted manifest's key order.
    expected = contract | {'comparator': source_identity}
    canonical = (json.dumps(expected, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    require(raw == canonical, 'frame manifest raw serialization')
    return manifest, sha256(raw).hexdigest()


def _input_manifest():
    raw = _regular(BUNDLE / 'inputs.json')
    require(sha256(raw).hexdigest() == INPUTS_SHA256, 'input manifest identity')
    return _json(raw)


def _verified_member(row):
    body = _regular(BUNDLE / row['path'])
    require(len(body) == row['bytes'] and sha256(body).hexdigest() == row['sha256'],
            'input bytes/hash mismatch: ' + row['path'])
    return body


def _payload_bytes(relative):
    # Authenticate this exact read, not an earlier read discarded by the closure
    # check. Both compile() and fixture parsing consume these returned bytes.
    rows = [row for row in _input_manifest()['payloads']
            if row['path'] == 'payloads/' + relative]
    require(len(rows) == 1, 'unapproved payload')
    return _verified_member(rows[0])


def verify_inputs() -> dict:
    """Verify the compiled-in bundle; no configurable roots or golden inputs."""
    manifest = _input_manifest()
    require(len(manifest['payloads']) == 29, 'payload count')
    require(manifest['historical'] == {'matrix_input': MATRIX_INPUT, 'matrix_output': MATRIX_OUTPUT,
                                    'wrapper_raw': WRAPPER_RAW}, 'historical oracle identity')
    for kind in ('payloads', 'provenance'):
        expected = set()
        for row in manifest[kind]:
            rel = PurePosixPath(row['path'])
            require(not rel.is_absolute() and '..' not in rel.parts and rel.parts[0] == kind,
                    'unsafe input path')
            require(str(rel) not in expected, 'duplicate input destination')
            expected.add(str(rel))
            _verified_member(row)
        require(_closure(BUNDLE / kind, expected) == expected, 'input closure mismatch: ' + kind)
    require({p.name for p in BUNDLE.iterdir()} == {'inputs.json','frames.json','payloads','provenance'},
            'unexpected bundle root member')
    frames, frames_digest = _frame_manifest()
    return {'payload_count': 29, 'provenance_count': len(manifest['provenance']),
            'inputs_sha256': INPUTS_SHA256, 'frames_sha256': frames_digest,
            'comparator_sha256': frames['comparator']['sha256'], 'native_executed': False}


def _modules():
    verify_inputs()
    loaded = {}
    def local_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith('coverage_'):
            require(level == 0 and name in loaded, 'unapproved pure-module import')
            return loaded[name]
        return builtins.__import__(name, globals, locals, fromlist, level)
    for name in MODULES:
        # A private module namespace avoids trusting ambient coverage_* imports.
        unique = '_macos_native_frozen_' + name
        module = ModuleType(unique)
        module.__file__ = str(BUNDLE / 'payloads' / (name + '.py'))
        module.__dict__['__builtins__'] = dict(vars(builtins), __import__=local_import)
        sys.modules[unique] = module  # dataclass resolves its own module here.
        exec(compile(_payload_bytes(name + '.py'), module.__file__, 'exec'), module.__dict__)
        loaded[name] = module
    return loaded


@dataclass(frozen=True)
class Batch:
    name: str
    frames: tuple[dict, ...]
    stdin: bytes


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool


def _batch(name, frames):
    frames = tuple(frames)
    lines = [wire(frame) + b'\n' for frame in frames]
    require(all(len(line) <= MAX_FRAME for line in lines), 'stdin frame cap')
    return Batch(name, frames, b''.join(lines))


def options(template=TEMPLATES[0], flags=(True, True, False, True, True, True, False, False)):
    return {'template': template, 'preferred_translation': 'KJV', 'include': dict(zip(FLAGS, flags))}


def teaching(text='Remain steady.', id='T000', kind='movement'):
    return {'id': id, 'kind': kind, 'text': text, 'source_blocks': ['B0000']}


def disposition(block_id='B0000', teachings=None, paths=None, excluded=None, repeats=None):
    return {'block_id': block_id, 'teaching_ids': teachings or [], 'section_paths': paths or [],
            'excluded_reasons': excluded or [], 'repeats_teaching_ids': repeats or []}


def empty():
    return {'schema_version': '1', 'outcome': 'complete', 'failure_code': 'none', 'teachings': [],
            'source_dispositions': [disposition(excluded=['transition'])], 'outline': [],
            'sections': {'title': '', 'main_scripture': '', 'supporting_scriptures': [],
                         'illustrations': [], 'quotes': [], 'prayer_points': [], 'calls_to_action': [],
                         'key_lessons': [], 'chapter_markers': [], 'introduction': [], 'summary': ''},
            'section_links': [], 'quote_spans': []}


def note():
    value = empty()
    value['teachings'] = [teaching()]
    value['outline'] = [{'teaching_id': 'T000', 'sub_point_ids': []}]
    value['source_dispositions'] = [disposition(teachings=['T000'])]
    return value


def linked_sections(private):
    paths = []
    for field, value in sorted(private['sections'].items()):
        if isinstance(value, list):
            paths.extend(f'/{field}/{index}' for index in range(len(value)))
        elif value:
            paths.append(f'/{field}')
    private['section_links'] = [{'path': path, 'source_blocks': ['B0000']} for path in paths]
    private['source_dispositions'][0]['section_paths'] = paths


def _fixture(path):
    return _json(_payload_bytes('fixtures/' + path))


def _frame(draft, value, **extra):
    return {'options': value, 'draft_json': draft.draft_json.decode('utf-8'),
            'result_digest': draft.result_digest, **extra}


def _envelope(frame):
    return (b'{"output":[{"content":[{"text":' + wire(frame['draft_json'])
            + b',"type":"output_text"}]}]}' + b' ' * frame.get('envelope_suffix_spaces', 0))


def prepare_batches() -> tuple[list[Batch], list[CheckResult]]:
    modules = _modules()
    contract = modules['coverage_contract']
    compiler = modules['coverage_compile']
    index_source = modules['coverage_index'].index_source
    checks = []
    batches = []
    def compiled(private, source='Remain steady.', value=None):
        return compiler.compile_private(private, index_source(source), value or options())
    def raw_probe(fields):
        raw = wire(fields)
        return compiler.CompiledDraft(raw, sha256(raw).hexdigest())
    def reject(name, code, private, value=None, source='Remain steady.'):
        try:
            compiled(private, source, value)
        except contract.CoverageFailure as exc:
            require(exc.code == code, 'wrong pure rejection: ' + name)
        else:
            raise ProofError('missing pure rejection: ' + name)
        checks.append(CheckResult(name + ':' + code, True))
    def add(name, cases):
        batches.append(_batch(name, cases))

    cases = []
    for template, flags in product(TEMPLATES, product((False, True), repeat=8)):
        value = options(template, flags)
        private = note()
        private['sections'] = {field: '' if field in {'title', 'summary', 'main_scripture'} else []
                               for field in contract.public_schema(value)['required'] if field != 'points'}
        texts = [' \u2009Still 🥁\t', 'e\u0301 — exactly retained\u3000', '\u200b']
        private['teachings'] = [teaching(text, f'T{i:03}', 'movement' if i == 0 else 'supporting_teaching')
                                for i, text in enumerate(texts)]
        private['source_dispositions'] = [disposition(teachings=['T000', 'T001', 'T002'])]
        private['outline'][0]['sub_point_ids'] = ['T002', 'T001']
        cases.append(_frame(compiled(private, value=value), value, observe_body=True))
    add('matrix', cases)
    require(sha256(batches[-1].stdin).hexdigest() == MATRIX_INPUT, 'historical matrix input mismatch')

    cases = []
    for translation in [*PICKER, 'x'*16, 'é'*16, 'a'*15+'🥁']:
        value = options(); value['preferred_translation'] = translation
        value = contract.validate_options(value)
        cases.append(_frame(compiled(note(), value=value), value, observe_body=True))
    add('translations', cases)
    mutations = [lambda v: v.update(preferred_translation='é'*17),
                 lambda v: v.update(preferred_translation='🥁'*17),
                 lambda v: v.update(preferred_translation='\ud800'),
                 lambda v: v.update(preferred_translation=1), lambda v: v.update(template='fallback'),
                 lambda v: v.update(extra=None), lambda v: v.pop('template'),
                 lambda v: v['include'].update(prayer_points=1),
                 lambda v: v['include'].update(extra=True), lambda v: v['include'].pop('prayer_points')]
    for i, mutate in enumerate(mutations):
        value = options(); mutate(value); reject(f'option-{i}', 'options_invalid', note(), value)

    fixture = _fixture('native/content.json'); private = note()
    for field in ('title', 'summary', 'main_scripture', 'supporting_scriptures', 'quotes', 'chapter_markers'):
        private['sections'][field] = fixture[field]
    points = fixture['points']
    private['teachings'] = [teaching(points[0]['text']),
                           teaching(points[0]['sub_points'][0], 'T001', 'supporting_teaching'),
                           teaching(points[0]['sub_points'][1], 'T002', 'supporting_teaching'),
                           teaching(points[1]['text'], 'T003')]
    private['outline'] = [{'teaching_id': 'T000', 'sub_point_ids': ['T001','T002']},
                          {'teaching_id': 'T003', 'sub_point_ids': []}]
    private['source_dispositions'] = [disposition(teachings=['T000','T001','T002','T003'])]
    linked_sections(private)
    private['quote_spans'] = [{'quote_index': i, 'first_block': 'B0000', 'last_block': 'B0000', 'occurrence': 1}
                            for i in range(len(fixture['quotes']))]
    add('content', [_frame(compiled(private, fixture['source']), options(), observe_helpers=True,
                           segments=fixture['segments'])])
    private = note()
    private['sections']['illustrations'] = [' '.join(f'Psalms {i}:1' for i in range(1,66))]
    linked_sections(private)
    add('helper scan', [_frame(compiled(private), options(), observe_helpers=True)])

    cases = []; baseline = _json(compiled(note()).draft_json)
    for i, character in enumerate(WHITESPACE + NON_WHITESPACE):
        private = note()
        private['teachings'][0]['text'] = character
        for field in ('title','summary','main_scripture'): private['sections'][field] = character
        private['sections']['illustrations'] = [character]; linked_sections(private)
        if character in WHITESPACE:
            reject(f'blank-{i}', 'local_contract', private)
            fields = baseline | private['sections'] | {'points': [{'text': character, 'sub_points': []}]}
            cases.append(_frame(raw_probe(fields), options()))
        else:
            cases.append(_frame(compiled(private), options()))
        retained = f'{character}e\u0301🥁{character}'
        private['teachings'][0]['text'] = retained
        for field in ('title','summary','main_scripture'): private['sections'][field] = retained
        private['sections']['illustrations'] = [retained]
        cases.append(_frame(compiled(private), options()))
    add('Unicode', cases)

    cases = []
    for field, limit in [('title',200),('summary',4000),('main_scripture',2000)]:
        private = empty(); private['sections'][field] = '🥁'*limit; linked_sections(private)
        cases.append(_frame(compiled(private), options()))
        private['sections'][field] += '🥁'; reject('scalar-'+field, 'local_contract', private)
    add('scalar caps', cases)
    cases = []
    for field, limit in [('illustrations',64),('supporting_scriptures',128)]:
        private = empty(); private['sections'][field] = ['\\🥁'*1000]+[f'Exact {i}' for i in range(1,limit)]
        linked_sections(private); cases.append(_frame(compiled(private), options()))
        private['sections'][field].append('over'); linked_sections(private)
        reject('list-'+field, 'local_contract', private)
    add('list caps', cases)

    private = note(); private['teachings'][0]['text'] = '"\\'*1000; draft = compiled(private)
    require(len(draft.draft_json) == 4238 and draft.result_digest == WRAPPER_RAW, 'historical wrapper raw mismatch')
    compact = _envelope(_frame(draft,options()))
    literal = b'{"output":[{"content":[{"text":'+draft.draft_json+b',"type":"output_text"}]}]}'
    padding = 524288-len(compact)
    cases = [_frame(draft,options(),envelope_suffix_spaces=n)
             for n in (padding,padding+1,524288-len(literal))]
    for case, pin in zip(cases,WRAPPER_PINS,strict=True):
        envelope = _envelope(case)
        require((len(envelope),sha256(envelope).hexdigest()) == pin, 'historical wrapper envelope mismatch')
    add('wrapper',cases)
    draft = compiled(note()); changed = draft.draft_json.replace(b'":', b'": ',1)
    add('raw digest', [_frame(compiler.CompiledDraft(changed,draft.result_digest),options()),
                       _frame(raw_probe(_json(changed)),options())])

    # N:187 maximal_public, with N:221's fixed one-block source and all flags.
    value = options(flags=(True,)*8); source = 'Synthetic input.'; private = empty()
    private['sections'] = {key: '' if key in {'title','summary','main_scripture'} else []
                          for key in contract.private_schema(value)['properties']['sections']['required']}
    outline = []; records = []
    for point in range(32):
        main = len(records); sub_count = 16 if point == 0 else 2 if point <= 24 else 0
        records.append(teaching('q'*2000,f'T{main:03}')); subs = []
        for _ in range(sub_count):
            identifier = f'T{len(records):03}'
            records.append(teaching('q'*2000,identifier,'supporting_teaching')); subs.append(identifier)
        outline.append({'teaching_id':f'T{main:03}','sub_point_ids':subs})
    private['outline'] = outline; private['teachings'] = records
    private['source_dispositions'] = [disposition(teachings=[entry['id'] for entry in records])]
    remainder = 262144-len(compiled(private,source,value).draft_json)
    for entry in records:
        widened = min(remainder,len(entry['text']))
        entry['text'] = 'é'*widened+entry['text'][widened:]; remainder -= widened
    require(remainder == 0, 'public cap construction')
    draft = compiled(private,source,value)
    require(len(draft.draft_json) == 262144 and len(records) == 96
            and all(len(r['text']) == 2000 for r in records), 'public cap selection')
    add('public cap',[_frame(draft,value)])
    last = private['teachings'][-1]; last['text'] = 'é'+last['text'][1:]
    reject('public-byte', 'byte_limit', private,value,source)
    last['text'] += 'q'; reject('teaching-2001','local_contract',private,value,source)
    last['text'] = last['text'][1:]
    private['outline'].append({'teaching_id':'T000','sub_point_ids':[]})
    reject('outline-33','local_contract',private,value,source); private['outline'].pop()
    private['outline'][0]['sub_point_ids'].append('T001')
    reject('subpoints-17','local_contract',private,value,source); private['outline'][0]['sub_point_ids'].pop()
    private['teachings'].append(teaching(id='T096')); reject('teachings-97','local_contract',private,value,source)

    cases = []
    for main_present in (False,True):
        private = empty(); private['sections']['main_scripture'] = ' John 1:1  ' if main_present else ''
        private['sections']['supporting_scriptures'] = [f'Stated address {i}' for i in range(128-main_present)]
        linked_sections(private); cases.append(_frame(compiled(private),options()))
        private['sections']['supporting_scriptures'].append('Over'); linked_sections(private)
        reject(f'combined-{main_present}', 'local_contract', private)
    add('combined scriptures',cases)
    require(tuple((b.name,len(b.frames)) for b in batches) == BATCH_COUNTS, 'batch shape')
    require(len(checks) == 47 and len({c.name for c in checks}) == 47, 'pure rejection count')
    require(sum(len(b.stdin) for b in batches) <= MAX_STDIN, 'aggregate stdin cap')
    frozen, _ = _frame_manifest()
    _same(frame_inventory(batches), frozen['batches'], 'frozen batch inventory')
    _same([check.name for check in checks], frozen['pure_rejections'], 'frozen pure rejections')
    return batches, checks


def _same(actual, expected, name):
    # JSON booleans and integers must not compare equal by Python's coercion.
    require(type(actual) is type(expected), name + ': type')
    if isinstance(expected, dict):
        require(actual.keys() == expected.keys(), name + ': fields')
        for key, value in expected.items():
            _same(actual[key], value, name + '.' + key)
    elif isinstance(expected, list):
        require(len(actual) == len(expected), name + ': count')
        for i, value in enumerate(expected):
            _same(actual[i], value, name + f'[{i}]')
    else:
        require(actual == expected, name + ': value')


def _body(actual, value, schema, checks):
    require(type(actual) is dict and set(actual) == {'transport_calls','clamped','schema','developer'},
            'body fields')
    for key, expected in {'transport_calls':0,'clamped':False,'schema':schema}.items():
        _same(actual[key], expected, 'body.'+key); checks.append('body.'+key)
    prompt = actual['developer']; require(type(prompt) is str, 'body developer type')
    parts = _fixture('requests/native-prompt-parts.json')
    require(parts['translation'].format(value['preferred_translation']) in prompt, 'body translation')
    checks.append('body.translation')
    for template in TEMPLATES:
        require((parts[template] in prompt) == (template == value['template']), 'body template')
        checks.append('body.template.'+template)
    conditions = {'podcast': value['include']['podcast_show_notes'],
                  'podcast_scripture': value['include']['podcast_show_notes'] and value['include']['scripture_extraction'],
                  'short_description': value['include']['short_description']}
    for key, expected in conditions.items():
        require((parts[key] in prompt) == expected, 'body '+key); checks.append('body.'+key)


def _check_row(name, index, frame, actual, contract):
    """Check each row against fixed construction semantics, never native goldens."""
    checks = []
    if name == 'raw digest' and index == 0:
        _same(actual, {'status':'digest_mismatch'}, 'raw digest error')
        return ['digest_mismatch.exact_row']
    envelope = _envelope(frame); raw = frame['draft_json'].encode('utf-8')
    expected = {'envelope_bytes':len(envelope),'envelope_sha256':sha256(envelope).hexdigest(),
                'raw_bytes':len(raw),'raw_sha256':frame['result_digest']}
    if name == 'wrapper' and index > 0:
        expected['status'] = 'native_byte_limit'
        _same(actual, expected, 'wrapper overflow')
        return ['wrapper.exact_five_field_row']
    fields = _json(raw); value = frame['options']; schema = contract.public_schema(value)
    def kept(s):
        return any(c not in WHITESPACE for c in s)
    points = [{'text':p['text'], 'sub_points':[s for s in p['sub_points'] if kept(s)]}
              for p in fields['points'] if kept(p['text'])]
    scriptures = [s for s in [fields.get('main_scripture',''), *fields.get('supporting_scriptures',[])] if kept(s)]
    sections = [{'heading':'Main points','items':[],'points':points}]
    for field, heading in HEADINGS.items():
        if field in fields:
            sections.append({'heading':heading,'items':[s for s in fields[field] if kept(s)],'points':[]})
    summary = fields.get('summary') if kept(fields.get('summary','')) else None
    caveats = (['Summary'] if 'summary' in fields and summary is None else [])
    caveats += ['Scripture references'] if 'main_scripture' in fields and not scriptures else []
    caveats += [s['heading'] for s in sections if not s['items'] and not s['points']]
    # The persisted API boundary is UTF-8 bytes; API validation above is scalars.
    translation = value['preferred_translation'].encode('utf-8')[:16].decode('utf-8', errors='ignore')
    expected.update(status='parsed', clamped=False, options=value, schema=schema,
                    title=fields['title'] if kept(fields['title']) else 'Sermon notes', summary=summary,
                    scriptures=scriptures, sections=sections, caveats=caveats,
                    attached_scripture_verdict_count=0, attached_timestamp_count=0,
                    picker_translations=PICKER, persisted_translation=translation)
    if name == 'content':
        fixture = _fixture('native/content.json'); pts = fixture['points']; chapters = fixture['chapter_markers']
        expected.update(helper_scripture_verdicts=fixture['scripture_verdicts'],
                        helper_scripture_scan_truncated=False,
                        helper_timestamps=[
                            {'heading':'Main points','text':pts[0]['text'],'offset_ms':1000},
                            {'heading':'Main points','text':pts[1]['text'],'offset_ms':9000},
                            {'heading':'Chapter markers','text':chapters[0],'offset_ms':1000},
                            {'heading':'Chapter markers','text':chapters[1],'offset_ms':5000},
                            {'heading':'Chapter markers','text':chapters[2],'offset_ms':9000}])
    elif name == 'helper scan':
        expected.update(helper_scripture_scan_truncated=True,
                        helper_scripture_verdicts=[{'reference':f'Psalms {i}:1','verified':True} for i in range(1,65)],
                        helper_timestamps=[])
    required = set(expected) | ({'legacy_build_body'} if frame.get('observe_body') else set())
    require(set(actual) == required, 'observation fields')
    for key, wanted in expected.items():
        _same(actual[key], wanted, key); checks.append(key)
    if frame.get('observe_body'):
        _body(actual['legacy_build_body'],value,schema,checks)
    if name == 'matrix':
        require(list(fields) == schema['required'], 'matrix public field order')
        checks.append('matrix.public_field_order')
    if name == 'public cap':
        require(len(raw) == 262144 and len(points) == 32 and len(points[0]['sub_points']) == 16,
                'public cap dimensions')
        require(sum(1+len(p['sub_points']) for p in points) == 96, 'public cap selected teachings')
        require(all(len(s) == 2000 for p in points for s in [p['text'],*p['sub_points']]),
                'public cap scalar lengths')
        checks.extend(['public_cap.dimensions','public_cap.selected_teachings','public_cap.scalar_lengths'])
    return checks


def check_observations(name: str, stdout: bytes) -> dict:
    require(type(stdout) is bytes and 0 < len(stdout) <= MAX_STDOUT, 'stdout aggregate cap/empty')
    require(stdout.endswith(b'\n'), 'stdout missing final LF')
    lines = stdout[:-1].split(b'\n')  # splitlines would also split Unicode/control scalars.
    require(all(0 < len(line) <= MAX_LINE for line in lines), 'stdout line cap/empty')
    batches, _ = prepare_batches()
    batch = next((batch for batch in batches if batch.name == name), None)
    require(batch is not None, 'unknown batch')
    require(len(lines) == len(batch.frames), 'stdout row count')
    observations = [_json(line) for line in lines]
    require(all(type(row) is dict for row in observations), 'stdout row type')
    contract = _modules()['coverage_contract']
    # Fixed independent baseline public schema must agree with the recovered producer.
    _same(contract.public_schema(options()), _fixture('contract/baseline-public-schema.json'), 'pinned public schema')
    checks = ['pinned_public_schema']
    for index, (frame, row) in enumerate(zip(batch.frames, observations, strict=True)):
        checks.extend(f'{index}:{check}' for check in _check_row(name,index,frame,row,contract))
    digest = sha256(b''.join(wire(row)+b'\n' for row in observations)).hexdigest()
    if name == 'matrix':
        require(digest == MATRIX_OUTPUT, 'historical matrix observation mismatch')
        checks.append('historical_matrix_output')
    return {'name':name,'count':len(observations),'stdout_bytes':len(stdout),
            'stdout_sha256':sha256(stdout).hexdigest(),'observations_sha256':digest,
            'checks':checks}


def frame_inventory(batches):
    return [{'name':b.name,'count':len(b.frames),'bytes':len(b.stdin),'sha256':sha256(b.stdin).hexdigest()}
            for b in batches]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare-check',action='store_true')
    group.add_argument('--self-test',action='store_true')
    args = parser.parse_args()
    if args.self_test:
        import unittest
        sys.path.insert(0, str(Path(__file__).absolute().parent.parent))
        suite = unittest.defaultTestLoader.loadTestsFromName('scripts.test_macos_native_proof')
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    try:
        inputs = verify_inputs(); batches, checks = prepare_batches()
        print(json.dumps(inputs | {'batches':frame_inventory(batches),'pure_rejections':[c.name for c in checks],
                                  'matrix_input_matched':True,'wrapper_inputs_matched':True},indent=2))
        return 0
    except ProofError as exc:
        print('fixture preparation failed: '+str(exc),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
