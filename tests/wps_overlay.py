#!/usr/bin/env python3
"""Measured formatting and preservation regression; no WPS or font binaries."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'genoffice-official-typeset/scripts'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


overlay = module('overlay', 'apply-wps-body.py')
compat = module('compat', 'apply-genoffice-compat.py')
NS = {'w': overlay.W}
W = '{'+overlay.W+'}'


class WpsOverlay(unittest.TestCase):
    def test_measured_layout_and_objects(self):
        with tempfile.TemporaryDirectory(prefix='WPS overlay tests ') as directory:
            folder = Path(directory)
            source, target, plan = [folder/name for name in ('source.docx', 'final.docx', 'plan.json')]
            table = '<w:tbl><w:tr><w:tc><w:p><w:r><w:rPr><w:rFonts w:eastAsia="宋体"/></w:rPr><w:t>001原表</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
            picture = '<w:p><w:r><w:pict><v:shape id="original"><v:textbox><w:txbxContent><w:p><w:r><w:rPr><w:rFonts w:eastAsia="宋体"/><w:b/></w:rPr><w:t>对象内文字</w:t></w:r></w:p></w:txbxContent></v:textbox></v:shape></w:pict></w:r></w:p>'
            header_ref = '<w:headerReference xmlns:r="'+overlay.R+'" w:type="default" r:id="rIdOriginalHeader"/>'
            paragraphs = [
                '<w:p><w:r><w:t>关于示例工作的通知</w:t></w:r></w:p>',
                '<w:p><w:r><w:t>各部门：</w:t></w:r></w:p>',
                '<w:p><w:pPr><w:sectPr>'+header_ref+'<w:type w:val="continuous"/><w:titlePg/></w:sectPr></w:pPr><w:r><w:t xml:space="preserve">请保留  两个空格。</w:t><w:tab/><w:br/><w:t>待核实</w:t></w:r></w:p>',
                '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="4"/></w:numPr><w:ind w:left="720" w:hanging="360"/></w:pPr><w:r><w:t>原生编号</w:t></w:r></w:p>',
                table, picture,
                '<w:p><w:r><w:t>附件：示例清单</w:t></w:r></w:p>',
                '<w:p><w:r><w:t>示例办公室</w:t></w:r></w:p>',
                '<w:p><w:r><w:t>2026年10月22日</w:t></w:r></w:p>',
                '<w:p><w:r><w:t xml:space="preserve">  </w:t></w:r></w:p>'
            ]
            header = ('<w:document xmlns:w="'+overlay.W+'" xmlns:v="urn:schemas-microsoft-com:vml" '
                      'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
                      'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" mc:Ignorable="w14">')
            document = (header+'<w:body>'+''.join(paragraphs)+'<w:sectPr>'+header_ref+'</w:sectPr></w:body></w:document>').encode()
            styles = ('<w:styles xmlns:w="'+overlay.W+'"><w:docDefaults><w:pPrDefault><w:pPr><w:spacing w:after="120"/></w:pPr></w:pPrDefault></w:docDefaults></w:styles>').encode()
            parts = {'word/document.xml': document, 'word/styles.xml': styles,
                     'word/header1.xml': ('<w:hdr xmlns:w="'+overlay.W+'"><w:p><w:r><w:rPr><w:rFonts w:eastAsia="宋体"/></w:rPr><w:t>原页眉</w:t></w:r></w:p></w:hdr>').encode(),
                     'word/numbering.xml': ('<w:numbering xmlns:w="'+overlay.W+'"><w:num w:numId="4"/></w:numbering>').encode(),
                     'word/media/image1.png': b'original-image-bytes',
                     '[Content_Types].xml': b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
                     'word/_rels/document.xml.rels': ('<Relationships xmlns="'+overlay.PKG+'"><Relationship Id="rIdImage" Type="'+overlay.R+'/image" Target="media/image1.png"/><Relationship Id="rIdOriginalHeader" Type="'+overlay.R+'/header" Target="header1.xml"/></Relationships>').encode()}
            with zipfile.ZipFile(source, 'w') as archive:
                for name, value in parts.items():
                    archive.writestr(name, value)
            roles = ['title', 'addressee', 'body', 'body', 'skip', 'skip', 'attachment', 'signature', 'date', 'blank']
            entries = [{'role': role, 'type': 'listitem' if i == 3 else 'paragraph'} for i, role in enumerate(roles)]
            plan.write_text(json.dumps({'entries': entries}))
            result = overlay.apply(source, plan, target)
            self.assertEqual(result['addedLayoutBlankParagraphs'], 2)
            with zipfile.ZipFile(target) as archive:
                final = archive.read('word/document.xml')
                self.assertTrue(final.startswith(header.encode()))
                self.assertIn(table.encode(), final)
                self.assertIn(picture.encode(), final)
                self.assertIn(header_ref.encode(), final)
                self.assertEqual(archive.read('word/numbering.xml'), parts['word/numbering.xml'])
                self.assertEqual(archive.read('word/media/image1.png'), parts['word/media/image1.png'])
                self.assertIn(b'rIdImage', archive.read('word/_rels/document.xml.rels'))
                self.assertIn(b'rIdOriginalHeader', archive.read('word/_rels/document.xml.rels'))
                relations = archive.read('word/_rels/document.xml.rels')
                for kind in ('settings', 'fontTable'):
                    self.assertIn((overlay.R+'/'+kind).encode(), relations)
                    self.assertIn(('word/'+kind+'.xml').encode(), archive.read('[Content_Types].xml'))
                settings = ET.fromstring(archive.read('word/settings.xml'))
                self.assertIsNotNone(settings.find('w:compat/w:useFELayout', NS))
                self.assertIsNotNone(settings.find('w:evenAndOddHeaders', NS))
                self.assertEqual(settings.find('w:themeFontLang', NS).get(W+'eastAsia'), 'zh-CN')
                for variant in ('Odd', 'Even'):
                    footer = archive.read('word/officialWpsFooter'+variant+'.xml')
                    self.assertIn(b' PAGE ', footer)
                    self.assertIn(b'mso-position-horizontal:outside;', footer)
                for name in archive.namelist():
                    if name.endswith(('.xml', '.rels')):
                        ET.fromstring(archive.read(name))
            self.assertEqual(overlay.content_signature(document), overlay.content_signature(final))
            root = ET.fromstring(final)
            sections = root.findall('.//w:sectPr', NS)
            self.assertEqual(len(sections), 2)
            self.assertEqual(sections[0].find('w:type', NS).get(W+'val'), 'continuous')
            self.assertIsNotNone(sections[0].find('w:titlePg', NS))
            self.assertEqual(sections[0].find('w:pgNumType', NS).get(W+'start'), '1')
            self.assertIsNone(sections[1].find('w:pgNumType', NS).get(W+'start'))
            self.assertTrue(all(section.find('w:headerReference', NS) is not None for section in sections))
            paras = root.findall('w:body/w:p', NS)
            title_spacing = paras[0].find('w:pPr/w:spacing', NS)
            self.assertEqual(title_spacing.get(W+'line'), '720')
            for p in paras:
                spacing = p.find('w:pPr/w:spacing', NS)
                if spacing is not None:
                    self.assertEqual(spacing.get(W+'before'), '0')
                    self.assertEqual(spacing.get(W+'after'), '0')
                    self.assertEqual(spacing.get(W+'lineRule'), 'exact')
            self.assertEqual(root.find('.//w:docGrid', NS).get(W+'linePitch'), '579')
            self.assertEqual(root.find('.//w:pgMar', NS).get(W+'top'), '2098')
            numbered = next(p for p in paras if p.find('w:pPr/w:numPr', NS) is not None)
            self.assertEqual(numbered.find('w:pPr/w:numPr/w:numId', NS).get(W+'val'), '4')
            self.assertEqual(numbered.find('w:pPr/w:ind', NS).get(W+'hanging'), '360')
            with self.assertRaises(ValueError):
                overlay.apply(source, plan, target)
            # An expanded plan is idempotent: retain existing layout blanks.
            expanded = entries[:1]+[{'role':'blank'}]+entries[1:6]+[{'role':'blank'}]+entries[6:]
            plan.write_text(json.dumps({'entries': expanded}))
            again = folder/'again.docx'
            self.assertEqual(overlay.apply(target, plan, again)['addedLayoutBlankParagraphs'], 0)
            with zipfile.ZipFile(again) as archive:
                self.assertEqual(overlay.content_signature(final), overlay.content_signature(archive.read('word/document.xml')))
                ids = [n.get(W+'styleId') for n in ET.fromstring(archive.read('word/styles.xml')).findall('w:style', NS)]
                self.assertEqual(len(ids), len(set(ids)))
            compatible = folder/'compatible.docx'
            compat.stage(target, compatible, {'宋体':'HYShuSongErKW', '仿宋_GB2312':'FangSong_GB2312'})
            with zipfile.ZipFile(compatible) as archive:
                compatible_document = archive.read('word/document.xml')
                self.assertIn(b'FangSong_GB2312', compatible_document)
                self.assertIn(b'w:ascii="Times New Roman"', compatible_document)
                self.assertIn(table.encode(), compatible_document)
                self.assertIn(picture.encode(), compatible_document)
                self.assertEqual(archive.read('word/header1.xml'), parts['word/header1.xml'])
                settings = ET.fromstring(archive.read('word/settings.xml'))
                self.assertIsNone(settings.find('w:characterSpacingControl', NS))
                odd = archive.read('word/officialWpsFooterOdd.xml')
                even = archive.read('word/officialWpsFooterEven.xml')
                self.assertIn(b'mso-position-horizontal:right;', odd)
                self.assertIn(b'<w:jc w:val="right"/>', odd)
                self.assertIn(b'mso-position-horizontal:left;', even)
                self.assertIn(b'margin-top:6pt;', odd)
                self.assertIn(b'margin-top:6pt;', even)
                self.assertIn(b' PAGE ', odd)


if __name__ == '__main__':
    unittest.main()
