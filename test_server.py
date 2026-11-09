import base64
import io
import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import server

class ServerChecks(unittest.TestCase):
    def test_photo_request_and_validation(self):
        values={key:None for key in server.NUTRIENTS};values.update(calories=130,protein=2.7,carbs=28.2,fat=.3)
        output={'food_present':True,'items':[{'name':'Rice','grams':200,'per100':values}],'notes':['Estimated portion.']}
        captured={}
        def fake(request,timeout):
            captured['body']=json.loads(request.data)
            captured['url']=request.full_url
            return io.BytesIO(json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(output)}]}]}).encode())
        image='data:image/jpeg;base64,'+base64.b64encode(b'\xff\xd8\xfftest-only-image').decode()
        result=server.analyze_photo(image,'test-only-not-a-real-key',opener=fake)
        self.assertEqual(result['items'][0]['source'],'AI estimate')
        self.assertIsNone(result['items'][0]['per100']['vitaminC'])
        self.assertEqual(captured['url'],'https://api.openai.com/v1/responses')
        self.assertFalse(captured['body']['store'])
        self.assertTrue(captured['body']['text']['format']['strict'])
        self.assertNotIn('test-only-not-a-real-key',json.dumps(captured['body']))
        with self.assertRaises(ValueError):server.analyze_photo('https://untrusted.example/image.jpg','key',opener=fake)
        output['items'][0]['per100']['protein']=-1
        with self.assertRaises(ValueError):server.validate_analysis(output)
    def test_loopback_routes_and_no_key(self):
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        address=f'http://127.0.0.1:{http.server_port}'
        try:
            with urlopen(address+'/') as response:
                self.assertIn(b'auth-screen',response.read())
                self.assertEqual(response.headers['Cache-Control'],'no-store')
            request=Request(address+'/api/ai/analyze',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
            with self.assertRaises(HTTPError) as caught:urlopen(request)
            self.assertEqual(caught.exception.code,403)
            request=Request(address+'/api/ai/analyze',data=b'{"consent":true}',headers={'Content-Type':'application/json','Origin':address,'X-Bloom-Request':'1'},method='POST')
            with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
                with self.assertRaises(HTTPError) as caught:urlopen(request)
            self.assertEqual(caught.exception.code,503)
            self.assertIn(b'Connect your OpenAI API key',caught.exception.read())
        finally:http.shutdown();http.server_close();thread.join()

    def test_local_recognition_routes(self):
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        address=f'http://127.0.0.1:{http.server_port}'
        image='data:image/jpeg;base64,'+base64.b64encode(b'\xff\xd8\xfftest-image').decode()
        try:
            with urlopen(address+'/api/ml/status') as response:
                self.assertFalse(json.load(response)['ready'])
            request=Request(address+'/api/ml/predict',data=json.dumps({'image':image}).encode(),headers={'Content-Type':'application/json','Origin':address,'X-Bloom-Request':'1'},method='POST')
            with self.assertRaises(HTTPError) as caught:urlopen(request)
            self.assertEqual(caught.exception.code,503)
            with patch.object(server.LOCAL_MODEL,'status',return_value={'ready':True}),patch.object(server.LOCAL_MODEL,'predict',return_value={'candidates':[{'label':'rice','score':.8}],'abstained':False}) as prediction:
                with urlopen(request) as response:self.assertEqual(json.load(response)['candidates'][0]['label'],'rice')
                prediction.assert_called_once_with(b'\xff\xd8\xfftest-image')
            hostile=Request(address+'/api/ml/predict',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://example.com','X-Bloom-Request':'1'},method='POST')
            with self.assertRaises(HTTPError) as caught:urlopen(hostile)
            self.assertEqual(caught.exception.code,403)
            bad=Request(address+'/api/ml/predict',data=b'{"image":"not-an-image"}',headers={'Content-Type':'application/json','Origin':address,'X-Bloom-Request':'1'},method='POST')
            with patch.object(server.LOCAL_MODEL,'status',return_value={'ready':True}):
                with self.assertRaises(HTTPError) as caught:urlopen(bad)
                self.assertEqual(caught.exception.code,400)
        finally:http.shutdown();http.server_close();thread.join()

    def test_mobile_app_origin_via_public_host(self):
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        address=f'http://127.0.0.1:{http.server_port}'
        try:
            with patch.object(server,'PUBLIC_HOST','bloom.example.org'):
                preflight=Request(address+'/api/ai/analyze',headers={'Host':'bloom.example.org','Origin':'capacitor://localhost'},method='OPTIONS')
                with urlopen(preflight) as response:
                    self.assertEqual(response.status,204)
                    self.assertEqual(response.headers['Access-Control-Allow-Origin'],'capacitor://localhost')
                request=Request(address+'/api/ai/analyze',data=b'{"consent":true}',headers={'Content-Type':'application/json','Host':'bloom.example.org','Origin':'https://localhost','X-Bloom-Request':'1'},method='POST')
                with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
                    with self.assertRaises(HTTPError) as caught:urlopen(request)
                self.assertEqual(caught.exception.code,503)
                self.assertEqual(caught.exception.headers['Access-Control-Allow-Origin'],'https://localhost')
                hostile=Request(address+'/api/ai/analyze',data=b'{"consent":true}',headers={'Content-Type':'application/json','Host':'bloom.example.org','Origin':'https://evil.example','X-Bloom-Request':'1'},method='POST')
                with self.assertRaises(HTTPError) as caught:urlopen(hostile)
                self.assertEqual(caught.exception.code,403)
                # Unknown Host still gets rejected even though Origin alone looks like a trusted mobile app.
                unknown_host=Request(address+'/api/ai/analyze',data=b'{"consent":true}',headers={'Content-Type':'application/json','Host':'not-the-configured-host.example','Origin':'https://localhost','X-Bloom-Request':'1'},method='POST')
                with self.assertRaises(HTTPError) as caught:urlopen(unknown_host)
                self.assertEqual(caught.exception.code,403)
        finally:http.shutdown();http.server_close();thread.join()
if __name__=='__main__':unittest.main()
