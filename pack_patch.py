"""Package the local translation overrides as a standard, unencrypted XP3."""
from pathlib import Path
import struct, zlib, json
BASE=Path(__file__).resolve().parent
ROOT=BASE/'overlay'

def chunk(tag,data): return tag+struct.pack('<Q',len(data))+data

def build():
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.suffix!='.xp3' and p.name not in ['patch.tjs','xp3filter.tjs','gesture_help.pimg'] and not p.name.endswith('.tmp'))
    out=ROOT/'patch2.xp3';tmp=ROOT/'patch2.xp3.tmp';index=[]; hashes=[]
    with tmp.open('wb') as f:
        f.write(b'XP3\r\n \n\x1a\x8bg\x01'+b'\0'*8)
        for path in files:
            name=path.relative_to(ROOT).as_posix().encode('utf-16le')
            data=path.read_bytes();checksum=zlib.adler32(data)&0xffffffff; hashes.append(checksum)
            packed=zlib.compress(data,6) if path.suffix in ['.tjs','.ks','.txt'] else data
            compressed=int(len(packed)<len(data))
            if not compressed:packed=data
            offset=f.tell();f.write(packed)
            info=struct.pack('<IQQH',0,len(data),len(packed),len(name)//2)+name
            segment=struct.pack('<IQQQ',compressed,offset,len(data),len(packed))
            index.append(chunk(b'File',chunk(b'info',info)+chunk(b'segm',segment)+chunk(b'adlr',struct.pack('<I',checksum))))
        offset=f.tell();raw=b''.join(index);packed=zlib.compress(raw,6)
        f.write(b'\1'+struct.pack('<QQ',len(packed),len(raw))+packed)
        f.seek(11);f.write(struct.pack('<Q',offset))
    tmp.replace(out)
    source=BASE/'tools/xp3filter.base.tjs'
    script=source.read_text('utf8')
    needle='function cxdec_decode(hash, offset, buf, len)\n    {'
    assert needle in script
    script=script.replace(needle,needle+'\n        if (webPatchHashes[hash]) return;')
    script='var webPatchHashes = %[];\n'+''.join('webPatchHashes[0x%08x] = true;\n'%h for h in sorted(set(hashes)))+script
    filterpath=ROOT/'xp3filter.tjs';temp=filterpath.with_suffix('.tjs.tmp');temp.write_text(script,encoding='utf8');temp.replace(filterpath)
    report={'archive' :str(out),'files':len(files),'bytes':out.stat().st_size,'encrypted':False}
    dest=BASE/'case/patch-build.json';tmp=dest.with_suffix('.json.tmp');tmp.write_text(json.dumps(report,indent=2),encoding='utf8');tmp.replace(dest)
    print(json.dumps(report))

if __name__=='__main__':build()
