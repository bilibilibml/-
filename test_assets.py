from pathlib import Path
import struct,zlib,re,unittest
ROOT=Path(__file__).resolve().parent/'overlay'

def chunks(b):
    i=0
    while i+12<=len(b):
        n=struct.unpack_from('<Q',b,i+4)[0]
        yield b[i:i+4],b[i+12:i+12+n]
        i+=12+n

def entries(path):
    with path.open('rb') as f:
        f.seek(11);off=struct.unpack('<Q',f.read(8))[0]
        while True:
            f.seek(off);flag=f.read(1)[0];size=struct.unpack('<Q',f.read(8))[0]
            if flag&128:
                f.seek(size,1);off=struct.unpack('<Q',f.read(8))[0];continue
            if flag&1:f.read(8)
            data=f.read(size)
            if flag&1:data=zlib.decompress(data)
            break
    result=[]
    for tag,body in chunks(data):
        if tag!=b'File':continue
        fields=dict(chunks(body));info=fields[b'info'];length=struct.unpack_from('<H',info,20)[0]
        result.append({'name':info[22:22+length*2].decode('utf-16le'),'hash':struct.unpack('<I',fields[b'adlr'])[0],'fields':fields})
    return result

class AssetTests(unittest.TestCase):
    def test_all_original_archives_present(self):
        self.assertEqual(len(list(ROOT.glob('*.xp3'))),17)
    def test_plain_patch_checksums_and_filter(self):
        rows=entries(ROOT/'patch2.xp3')
        self.assertEqual(len(rows),142)
        hashes={r['hash'] for r in rows}
        allowed={int(x,16) for x in re.findall(r'webPatchHashes\[0x([0-9a-f]+)\]',(ROOT/'xp3filter.tjs').read_text('utf8'))}
        self.assertEqual(hashes,allowed)
        with (ROOT/'patch2.xp3').open('rb') as f:
            for row in rows:
                flag,offset,raw,packed=struct.unpack('<IQQQ',row['fields'][b'segm'])
                f.seek(offset);data=f.read(packed)
                if flag&1:data=zlib.decompress(data)
                self.assertEqual(len(data),raw,row['name'])
                self.assertEqual(zlib.adler32(data)&0xffffffff,row['hash'],row['name'])
        for archive in ROOT.glob('*.xp3'):
            if archive.name=='patch2.xp3':continue
            self.assertFalse(hashes&{r['hash'] for r in entries(archive)},archive.name)
    def test_chinese_patch_and_menu_safety(self):
        names={r['name'] for r in entries(ROOT/'patch2.xp3')}
        self.assertIn('custom.ks',names)
        self.assertIn('custom.tjs',names)
        self.assertIn('title.pimg',names)
        self.assertNotIn('gesture_help.pimg',names)
        text=(ROOT/'custom.ks').read_text('utf16')
        self.assertIn('Web: use original static title background',text)
        self.assertNotIn('[ev storage=yuzulogo.mtn',text)

if __name__=='__main__':unittest.main()
