import unittest, urllib.request, urllib.error, json, xml.etree.ElementTree as ET

BASE='http://127.0.0.1:8765'

class ServerTests(unittest.TestCase):
    def request(self,path,method='GET',headers=None):
        return urllib.request.urlopen(urllib.request.Request(BASE+path,method=method,headers=headers or {}),timeout=15)
    def test_status(self):
        with self.request('/api/status') as r:
            data=json.load(r)
            self.assertEqual(data['engine'],'Kirikiroid2 Web')
            self.assertFalse(data['originalFilesModified'])
    def test_wasm_headers(self):
        with self.request('/vendor/index.wasm','HEAD') as r:
            self.assertEqual(r.headers['Content-Type'],'application/wasm')
            self.assertEqual(r.headers['Cross-Origin-Opener-Policy'],'same-origin')
            self.assertEqual(r.headers['Cross-Origin-Embedder-Policy'],'require-corp')
    def test_range(self):
        with self.request('/game/data.xp3',headers={'Range':'bytes=0-10'}) as r:
            self.assertEqual(r.status,206)
            self.assertEqual(r.read(),b'XP3\r\n \n\x1a\x8bg\x01')
            self.assertTrue(r.headers['Content-Range'].startswith('bytes 0-10/'))
    def test_invalid_range(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.request('/game/data.xp3',headers={'Range':'bytes=999999999999-'})
        self.assertEqual(e.exception.code,416)
    def test_discovery(self):
        with self.request('/game/','PROPFIND',{'Depth':'1'}) as r:
            self.assertEqual(r.status,207)
            tree=ET.fromstring(r.read())
            hrefs=[e.text for e in tree.iter('{DAV:}href')]
            self.assertIn('/game/data.xp3',hrefs)
            self.assertIn('/game/patch.tjs',hrefs)
            self.assertNotIn('/game/SenrenBanka.exe',hrefs)
    def test_no_original_saves_or_executable(self):
        for path in ['/game/SenrenBanka.exe','/game/savedata/data0.kdt','/vendor/../../server.py','/server.py']:
            with self.subTest(path=path),self.assertRaises(urllib.error.HTTPError) as e:
                self.request(path)
            self.assertEqual(e.exception.code,404)

if __name__=='__main__': unittest.main()
