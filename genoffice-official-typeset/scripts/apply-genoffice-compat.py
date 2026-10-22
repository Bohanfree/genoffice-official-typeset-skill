#!/usr/bin/env python3
"""Apply equivalent GenOffice-compatible fonts and WPS footer positioning.

GenOffice 0.11.919's CJK font branches bypass OOXML altName. Point its
document explicitly at installed WPS alias families. The measurement asset
retains canonical names and the report records both. No fonts are bundled.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

_spec = importlib.util.spec_from_file_location('wps_measured_xml', Path(__file__).with_name('apply-wps-body.py'))
xml = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(xml)


def stage(source, output, font_map):
    pairs = {key.encode(): value.encode() for key, value in font_map.items()}
    changed = 0

    def rewrite(tag):
        nonlocal changed

        def font(attr):
            nonlocal changed
            replacement = pairs.get(attr[2])
            if replacement is None:
                return attr[0]
            changed += 1
            return attr[1] + replacement + attr[3]

        return re.sub(rb'(\bw:(?:ascii|hAnsi|eastAsia|cs)\s*=\s*")([^"]+)(")', font, tag)

    def align_odd_footer(match):
        contents = re.sub(rb'<w:jc\b[^>]*/>', b'', match[2])
        rpr = contents.find(b'<w:rPr')
        at = rpr if rpr >= 0 else len(contents)
        return match[1]+contents[:at]+b'<w:jc w:val="right"/>'+contents[at:]+match[3]

    def rewrite_owned_xml(data, document=False):
        root = xml.tree(data)
        nodes = root.child('w:body').children if document else root.children
        patches = []
        for node in nodes:
            if document:
                if node.name != 'w:p':
                    continue
                ppr = node.child('w:pPr')
                style = ppr.child('w:pStyle') if ppr else None
                ident = style.attrs.get('w:val', '') if style else ''
            else:
                ident = node.attrs.get('w:styleId', '') if node.name == 'w:style' else ''
            if not ident.startswith(xml.PREFIX):
                continue
            fonts, texts = [], []

            def walk(child):
                if child.name in ('w:drawing', 'w:pict', 'w:object', 'w:txbxContent'):
                    return
                if child.name == 'w:rFonts':
                    fonts.append(child)
                elif child.name == 'w:t':
                    raw = xml.frag(data, child)
                    inner = raw[raw.find(b'>')+1:raw.rfind(b'</')]
                    texts.append(inner)
                for nested in child.children:
                    walk(nested)

            walk(node)
            text = ''.join(ET.fromstring(b'<root>'+b''.join(texts)+b'</root>').itertext())
            metric = (document and ident in (xml.PREFIX+'24', xml.PREFIX+'2')
                      and bool(re.search(r'[\u3400-\u9fff]', text))
                      and not re.search(r'[A-Za-z0-9]', text))
            for font in fonts:
                replacement = rewrite(xml.frag(data, font))
                if metric:
                    # Chinese glyphs retain their WPS eastAsia family. The
                    # unused Latin slot supplies GenOffice's paragraph strut.
                    replacement = re.sub(rb'(w:(?:ascii|hAnsi)\s*=\s*")[^"]+(")',
                                         rb'\1Times New Roman\2', replacement)
                patches.append((font.start, font.end, replacement))
        for a, b, value in sorted(patches, reverse=True):
            data = xml.splice(data, a, b, value)
        return data

    with zipfile.ZipFile(source) as src, zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == 'word/document.xml':
                data = rewrite_owned_xml(data, document=True)
            elif info.filename == 'word/styles.xml':
                data = rewrite_owned_xml(data)
            elif info.filename in ('word/officialWpsFooterOdd.xml', 'word/officialWpsFooterEven.xml'):
                data = re.sub(rb'<w:rFonts\b[^>]*>', lambda m: rewrite(m[0]), data)
                # GenOffice's VML text strut places this measured footer 5pt
                # above WPS. Resolve it in the delivered document itself.
                data = data.replace(b'margin-top:1pt;', b'margin-top:6pt;')
                # The engine's VML parser only accepts left/center/right and
                # ignores fit-shape-to-text when positioning a 144pt box.
                # Resolve outside by parity; align odd-page text to the box's
                # inner right edge, which equals WPS's fitted box right edge.
                if info.filename == 'word/officialWpsFooterOdd.xml':
                    data = data.replace(b'mso-position-horizontal:outside;', b'mso-position-horizontal:right;')
                    data = re.sub(rb'(<w:txbxContent>[\s\S]*?<w:pPr>)([\s\S]*?)(</w:pPr>)',
                                  align_odd_footer, data, count=1)
                elif info.filename == 'word/officialWpsFooterEven.xml':
                    data = data.replace(b'mso-position-horizontal:outside;', b'mso-position-horizontal:left;')
            dst.writestr(info, data)
    return {'status': 'ok', 'fontMap': font_map, 'fontAttributeChanges': changed,
            'footerCompatibility': 'outside-parity-and-fitted-inner-edge',
            'footerVerticalOffsetAdjustmentPt': 5,
            'pureCjkTitleAndHeadingAsciiMetricFont': 'Times New Roman',
            'characterSpacingControl': 'measured-template-default'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--font-map', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(stage(args.source, args.out, json.loads(args.font_map)), ensure_ascii=False))
    except Exception as exc:
        parser.exit(1, str(exc) + '\n')
