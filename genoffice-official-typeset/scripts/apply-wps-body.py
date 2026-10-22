#!/usr/bin/env python3
"""Apply measured WPS 公文主体 formatting without rewriting source XML content.

Only paragraph/run formatting, section settings, and official page-number parts
are replaced. Original text, object XML, relationship IDs and mc namespace scopes
remain byte-preserved in document.xml outside those formatting nodes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from xml.parsers import expat
import zipfile

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
NS = {'w': W, 'r': R}
ET.register_namespace('w', W)
ET.register_namespace('r', R)
PREFIX = 'WpsOfficialMeasured_'


class Node:
    def __init__(self, name, attrs, start, data):
        self.name, self.attrs, self.start = name, attrs, start
        self.open_end = data.find(b'>', start) + 1
        self.children = []
        self.end = self.close_start = None

    def child(self, name):
        return next((c for c in self.children if c.name == name), None)


def tree(data):
    """Expat supplies byte offsets; preserve the document's original XML prefixes."""
    parser = expat.ParserCreate()
    stack, roots = [], []

    def start(name, attrs):
        node = Node(name, attrs, parser.CurrentByteIndex, data)
        (stack[-1].children if stack else roots).append(node)
        stack.append(node)

    def end(name):
        node = stack.pop()
        pos = parser.CurrentByteIndex
        if data[node.open_end-2:node.open_end] == b'/>':
            node.close_start, node.end = node.open_end, node.open_end
        else:
            node.close_start, node.end = pos, data.find(b'>', pos) + 1

    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.Parse(data, True)
    return roots[0]


def frag(data, node):
    return data[node.start:node.end]


def map_style_refs(xml):
    # Never remap arbitrary w:val values (sizes and numbering share that name).
    xml = re.sub(r'(w:styleId\s*=\s*")([^"]+)(")',
                 lambda m: m.group(1) + PREFIX + m.group(2) + m.group(3), xml)
    xml = re.sub(r'(<w:(?:pStyle|rStyle|basedOn|next|link|styleLink|numStyleLink)\b[^>]*?w:val\s*=\s*")([^"]+)(")',
                 lambda m: m.group(1) + PREFIX + m.group(2) + m.group(3), xml)
    return xml


def serialize(el):
    return ET.tostring(el, encoding='utf-8')


def role_pr(spec):
    # WPS's measured pPrDefault is empty (zero before/after). The preparation
    # document may carry e.g. 6pt after in docDefaults. Scope the WPS defaults to
    # formatted paragraphs so those source defaults cannot leak into this mode.
    pr = ET.fromstring(map_style_refs(spec))
    spacing = pr.find('{'+W+'}spacing')
    if spacing is None:
        spacing = ET.Element('{'+W+'}spacing')
        following = ('ind', 'contextualSpacing', 'mirrorIndents', 'suppressOverlap',
                     'jc', 'textDirection', 'textAlignment', 'textboxTightWrap',
                     'outlineLvl', 'divId', 'cnfStyle', 'rPr', 'sectPr', 'pPrChange')
        pos = next((i for i, c in enumerate(pr) if c.tag.rsplit('}',1)[-1] in following), len(pr))
        pr.insert(pos, spacing)
    for attr in ('before', 'after'):
        if spacing.get('{'+W+'}'+attr) is None:
            spacing.set('{'+W+'}'+attr, '0')
    # Materialize the WPS style's exact rule. GenOffice's inherited-style CSS
    # leaves these paragraphs in its generic grid selector; a direct exact
    # rule correctly marks them as fixed-height lines.
    if spacing.get('{'+W+'}line') is None:
        style = pr.find('{'+W+'}pStyle')
        is_title = style is not None and style.get('{'+W+'}val') == PREFIX+'24'
        spacing.set('{'+W+'}line', '720' if is_title else '560')
        spacing.set('{'+W+'}lineRule', 'exact')
    return serialize(pr)


def role_rpr(spec):
    # WPS uses regular faces throughout this preset. Scope its absent/default
    # b/i flags explicitly so source defaults or heading HTML cannot add weight.
    pr = ET.fromstring(spec)
    for tag in ('b', 'bCs', 'i', 'iCs'):
        if pr.find('{'+W+'}'+tag) is None:
            pr.insert(1, ET.Element('{'+W+'}'+tag, {'{'+W+'}val': '0'}))
    return serialize(pr)


def splice(data, start, end, replacement):
    return data[:start] + replacement + data[end:]


def replace_run_pr(paragraph, rpr):
    root = tree(paragraph)
    patches = []

    def walk(node):
        if node.name in ('w:drawing', 'w:pict', 'w:object', 'w:txbxContent'):
            return
        if node.name == 'w:r' and any(c.name in ('w:t', 'w:tab', 'w:br') for c in node.children):
            old = node.child('w:rPr')
            patches.append((old.start if old else node.open_end,
                            old.end if old else node.open_end, rpr))
        else:
            for c in node.children:
                walk(c)

    walk(root)
    for a, b, replacement in sorted(patches, reverse=True):
        paragraph = splice(paragraph, a, b, replacement)
    return paragraph


def replace_ppr(paragraph, ppr, is_list=False):
    root = tree(paragraph)
    old = root.child('w:pPr')
    if is_list and old:
        # Preserve native numbering, hanging marker and list indentation exactly.
        keep = [frag(paragraph, c) for c in old.children if c.name in ('w:numPr', 'w:ind')]
        if keep:
            pr = ET.fromstring(ppr)
            for tag in ('numPr', 'ind'):
                for child in list(pr):
                    if child.tag == '{'+W+'}'+tag:
                        pr.remove(child)
            # numPr belongs before spacing/ind; ind belongs before jc/rPr.
            for raw in keep:
                preserved = ET.fromstring(('<root xmlns:w="'+W+'">').encode()+raw+b'</root>')[0]
                following = ('pBdr', 'shd', 'tabs', 'suppressAutoHyphens', 'kinsoku',
                             'wordWrap', 'overflowPunct', 'topLinePunct', 'autoSpaceDE',
                             'autoSpaceDN', 'bidi', 'adjustRightInd', 'snapToGrid',
                             'spacing', 'ind', 'contextualSpacing', 'mirrorIndents',
                             'suppressOverlap', 'jc', 'textDirection', 'textAlignment',
                             'textboxTightWrap', 'outlineLvl', 'divId', 'cnfStyle',
                             'rPr', 'sectPr', 'pPrChange')
                if preserved.tag == '{'+W+'}ind':
                    following = following[following.index('contextualSpacing'):]
                pos = next((i for i, c in enumerate(pr) if c.tag.rsplit('}',1)[-1] in following), len(pr))
                pr.insert(pos, preserved)
            ppr = serialize(pr)
    if old and old.child('w:sectPr'):
        at = ppr.rfind(b'</w:pPr>')
        ppr = splice(ppr, at, at, frag(paragraph, old.child('w:sectPr')))
    return splice(paragraph, old.start if old else root.open_end,
                  old.end if old else root.open_end, ppr)


def spacer(ppr):
    return b'<w:p>' + role_pr(ppr) + b'</w:p>'


def add_root_children(xml, fragments):
    root = tree(xml)
    if xml[root.open_end-2:root.open_end] == b'/>':
        return xml[:root.open_end-2] + b'>' + b''.join(fragments) + b'</' + root.name.encode() + b'>'
    return splice(xml, root.close_start, root.close_start, b''.join(fragments))


def content_signature(xml):
    root = ET.fromstring(xml)
    body = root.find('w:body', NS)
    return [(e.tag, e.text or '') for e in body.iter()
            if e.tag in ('{'+W+'}t', '{'+W+'}tab', '{'+W+'}br', '{'+W+'}instrText')]


def apply(source, plan_path, output):
    if output.exists():
        raise ValueError('为保留已有文件，请更换输出名称：'+str(output))
    asset = Path(__file__).resolve().parents[1] / 'assets' / 'wps-body-format.json'
    template = json.loads(asset.read_text(encoding='utf-8'))
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    with zipfile.ZipFile(source) as z:
        parts = {name: z.read(name) for name in z.namelist() if not name.endswith('/')}
    original_xml = parts['word/document.xml']
    doc = tree(original_xml)
    body = doc.child('w:body')
    blocks = [n for n in body.children if n.name != 'w:sectPr']
    entries = plan['entries']
    if len(blocks) != len(entries):
        raise ValueError('GenOffice 段落索引与 DOCX 顶层块不一致，已停止以免错排对象')
    chunks, cursor, added = [], body.open_end, 0
    for i, (block, entry) in enumerate(zip(blocks, entries)):
        chunks.append(original_xml[cursor:block.start])
        raw, role = frag(original_xml, block), entry['role']
        if block.name == 'w:p' and role != 'skip':
            if role == 'attachment' and i and entries[i-1]['role'] != 'blank':
                chunks.append(spacer(template['attachmentSpacerPPr']))
                added += 1
            spec = template['roles'][role]
            if role == 'blank' and i and entries[i-1]['role'] == 'title':
                pr = template['titleSpacerPPr']
            else:
                pr = spec['pPr']
            is_list = entry.get('type') in ('listitem', 'listItem', 'list', 'docListItem')
            raw = replace_ppr(raw, role_pr(pr), is_list)
            raw = replace_run_pr(raw, role_rpr(spec['rPr']))
        chunks.append(raw)
        if role == 'title' and i+1 < len(entries) and entries[i+1]['role'] != 'blank':
            chunks.append(spacer(template['titleSpacerPPr']))
            added += 1
        cursor = block.end
    chunks.append(original_xml[cursor:body.close_start])
    rebuilt = splice(original_xml, body.open_end, body.close_start, b''.join(chunks))
    # Replace section layout with the measured WPS grid/margins and new footer refs.
    rebuilt_root = tree(rebuilt)
    rebuilt_body = rebuilt_root.child('w:body')
    sections = []

    def collect(n):
        if n.name == 'w:sectPr':
            sections.append(n)
        for child in n.children:
            collect(child)

    collect(rebuilt_body)
    measured = ET.fromstring(template['section'])
    for child in list(measured):
        if child.tag in ('{'+W+'}headerReference', '{'+W+'}footerReference'):
            measured.remove(child)
    for variant, ident in [('default', 'rIdOfficialWpsFooterOdd'), ('even', 'rIdOfficialWpsFooterEven')]:
        measured.insert(0, ET.Element('{'+W+'}footerReference', {'{'+W+'}type': variant, '{'+R+'}id': ident}))
    for ordinal, section in reversed(list(enumerate(sorted(sections, key=lambda n:n.start)))):
        effective = ET.fromstring(serialize(measured))
        # Retain section breaks and the input's first-page header behavior.
        original_type = section.child('w:type')
        if original_type:
            pos = next((i for i,c in enumerate(effective) if c.tag == '{'+W+'}pgSz'), len(effective))
            effective.insert(pos, ET.Element('{'+W+'}type', {'{'+W+'}val':original_type.attrs.get('w:val','nextPage')}))
        title_page = section.child('w:titlePg')
        if title_page:
            value = title_page.attrs.get('w:val')
            pos = next((i for i,c in enumerate(effective) if c.tag == '{'+W+'}docGrid'), len(effective))
            effective.insert(pos, ET.Element('{'+W+'}titlePg', {} if value is None else {'{'+W+'}val':value}))
            effective.insert(0, ET.Element('{'+W+'}footerReference', {'{'+W+'}type':'first','{'+R+'}id':'rIdOfficialWpsFooterOdd'}))
        if ordinal:
            effective.find('{'+W+'}pgNumType').attrib.pop('{'+W+'}start', None)
        serialized = serialize(effective)
        headers = [frag(rebuilt,c) for c in section.children if c.name == 'w:headerReference']
        at = tree(serialized).open_end
        serialized = splice(serialized, at, at, b''.join(headers))
        rebuilt = splice(rebuilt, section.start, section.end, serialized)
    if not sections:
        raise ValueError('DOCX 缺少节设置，已停止')
    assert content_signature(original_xml) == content_signature(rebuilt), '原文字符或域内容发生变化'
    # Merge namespaced WPS styles; leave the original styles and namespace roots intact.
    styles_xml = parts['word/styles.xml']
    styles_root = tree(styles_xml)
    patches = [(n.start, n.end, b'') for n in styles_root.children
               if n.name == 'w:style' and n.attrs.get('w:styleId', '').startswith(PREFIX)]
    for a, b, value in sorted(patches, reverse=True):
        styles_xml = splice(styles_xml, a, b, value)
    tmpl_styles = template['styles'].encode()
    style_nodes = tree(tmpl_styles).children
    imported = []
    for node in style_nodes:
        if node.name != 'w:style':
            continue
        raw = map_style_refs(frag(tmpl_styles, node).decode())
        raw = re.sub(r'\s+w:default="[^"]*"', '', raw)
        imported.append(raw.encode())
    parts['word/styles.xml'] = add_root_children(styles_xml, imported)
    # Font aliases are WPS's recorded family names, not redistributed font files.
    old_fonts = parts.get('word/fontTable.xml')
    if old_fonts:
        old_root = tree(old_fonts)
        # Required WPS families must carry the measured WPS alias rather than
        # an unrelated alias inherited from the input document.
        for node in sorted(old_root.children, key=lambda n: n.start, reverse=True):
            if node.attrs.get('w:name') in template['requiredFonts']:
                old_fonts = splice(old_fonts, node.start, node.end, b'')
        old_root = tree(old_fonts)
        names = {n.attrs.get('w:name') for n in old_root.children}
        tf = template['fonts'].encode()
        missing = []
        for node in tree(tf).children:
            name = node.attrs.get('w:name')
            if name not in names:
                missing.append(frag(tf, node))
                names.add(name)
        parts['word/fontTable.xml'] = add_root_children(old_fonts, missing)
    else:
        parts['word/fontTable.xml'] = template['fonts'].encode()
    for name, key in [('officialWpsFooterOdd.xml', 'footerOdd'), ('officialWpsFooterEven.xml', 'footerEven')]:
        parts['word/'+name] = map_style_refs(template[key]).encode()
    relpath = 'word/_rels/document.xml.rels'
    rels = parts.get(relpath, ('<Relationships xmlns="'+PKG+'"/>').encode())
    relroot = tree(rels)
    for node in sorted(relroot.children, key=lambda n:n.start, reverse=True):
        if node.attrs.get('Id') in ('rIdOfficialWpsFooterOdd', 'rIdOfficialWpsFooterEven'):
            if node.attrs.get('Type') != R+'/footer':
                raise ValueError('源文件关系标识与公文页脚冲突，已停止以保留原对象')
            rels = splice(rels, node.start, node.end, b'')
    rels = add_root_children(rels, [
        ('<Relationship Id="'+ident+'" Type="'+R+'/footer" Target="'+name+'"/>').encode()
        for ident, name in [('rIdOfficialWpsFooterOdd','officialWpsFooterOdd.xml'), ('rIdOfficialWpsFooterEven','officialWpsFooterEven.xml')]])
    rel_nodes = tree(rels).children
    additions = []
    for kind, target, ident in [('settings', 'settings.xml', 'rIdOfficialWpsSettings'),
                                ('fontTable', 'fontTable.xml', 'rIdOfficialWpsFonts')]:
        existing = next((n for n in rel_nodes if n.attrs.get('Type') == R+'/'+kind), None)
        if existing and existing.attrs.get('Target') != target:
            raise ValueError('源文件使用非标准'+kind+'部件路径，已停止以免断开关联')
        if not existing:
            if any(n.attrs.get('Id') == ident for n in rel_nodes):
                raise ValueError('源文件关系标识与公文'+kind+'冲突，已停止以保留原对象')
            additions.append(('<Relationship Id="'+ident+'" Type="'+R+'/'+kind+'" Target="'+target+'"/>').encode())
    rels = add_root_children(rels, additions)
    parts[relpath] = rels
    ct = parts['[Content_Types].xml']
    additions = []
    for name in ('officialWpsFooterOdd.xml','officialWpsFooterEven.xml'):
        if ('PartName="/word/'+name+'"').encode() not in ct:
            additions.append(('<Override PartName="/word/'+name+'" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>').encode())
    for name, kind in [('settings.xml', 'settings'), ('fontTable.xml', 'fontTable')]:
        if ('PartName="/word/'+name+'"').encode() not in ct:
            additions.append(('<Override PartName="/word/'+name+'" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.'+kind+'+xml"/>').encode())
    parts['[Content_Types].xml'] = add_root_children(ct, additions)
    settings = parts.get('word/settings.xml', ('<w:settings xmlns:w="'+W+'"/>').encode())
    for node in sorted(tree(settings).children, key=lambda n: n.start, reverse=True):
        if node.name in ('w:compat', 'w:themeFontLang', 'w:evenAndOddHeaders'):
            settings = splice(settings, node.start, node.end, b'')
    settings = add_root_children(settings, [b'<w:evenAndOddHeaders/>']+[item.encode() for item in template.get('layoutSettings', [])])
    parts['word/settings.xml'] = settings
    parts['word/document.xml'] = rebuilt
    # Validate every edited part before writing a new ZIP.
    for name, value in parts.items():
        if name.endswith('.xml') or name.endswith('.rels'):
            ET.fromstring(value)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, value in parts.items():
            z.writestr(name, value)
    return {'status':'ok', 'textPreserved':True, 'addedLayoutBlankParagraphs':added,
            'formatPreset':'wps-official-body-measured-12.1.28496',
            'templateSha256':hashlib.sha256(asset.read_bytes()).hexdigest(),
            'sourceWpsDocumentSha256':template['sourceSha256'],
            'visualParity':'not-verified', 'requiredFonts':template['requiredFonts']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    opts = parser.parse_args()
    try:
        print(json.dumps(apply(opts.source, opts.plan, opts.out), ensure_ascii=False, indent=2))
    except Exception as exc:
        parser.exit(1, str(exc)+'\n')
