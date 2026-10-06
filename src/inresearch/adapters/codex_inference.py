"""Bounded Codex inference, locally or through a private loopback relay.

The CLI does not report the provider model in JSONL. Record the explicit request
and executor, leave actual=None, and never accept model-written provenance.
"""
import argparse
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from inresearch.adapters.models import InferenceError, MAX_RESPONSE, json_object, load_profile, JsonModelClient

MAX_REQUEST = 24 * 1024 * 1024


def cli_failure(returncode, events, stderr, elapsed):
    """Classify transport waits without persisting prompts, tokens or raw errors."""
    terminal = [e for e in events if e.get('type') in ('error', 'turn.failed')]
    detail = (stderr + ' ' + json.dumps(terminal, ensure_ascii=False)).lower()
    status = re.search(r'(?:status(?: code)?[: ]+|http[/\d. ]+)([45]\d\d)\b', detail)
    status = int(status.group(1)) if status else None
    if any(s in detail for s in ('usage_limit', 'rate_limit', 'usage limit', 'rate limit', 'quota')) or status == 429:
        code, kind = 'model_quota_wait', 'quota'
    elif any(s in detail for s in ('not logged', 'authentication', 'unauthorized')) or status in (401, 403):
        code, kind = 'model_cli_authentication_failed', 'authentication'
    elif status in (408, 500, 502, 503, 504) or any(s in detail for s in (
            'stream disconnected', 'error sending request', 'connection reset',
            'connection closed', 'service unavailable', 'server_error', 'unexpected eof')):
        code, kind = 'model_relay_unavailable', 'transport'
    else:
        code, kind = 'model_cli_failed', 'unclassified'
    exc = InferenceError(code)
    exc.diagnostics = {'cli_returncode': returncode, 'failure_kind': kind,
                       'elapsed_seconds': round(elapsed, 3), 'http_status': status,
                       'diagnostic_sha256': hashlib.sha256(detail.encode()).hexdigest()}
    return exc


def strict_schema(schema):
    if not isinstance(schema, dict) or schema.get('type') != 'object':
        raise InferenceError('model_output_schema_invalid')
    value = json.loads(json.dumps(schema, allow_nan=False))
    def visit(node):
        if not isinstance(node, dict): return
        if node.get('type') == 'object':
            node['additionalProperties'] = False
            node['required'] = list(node.get('properties', {}))
            for child in node.get('properties', {}).values(): visit(child)
        if 'items' in node: visit(node['items'])
        for name in ('anyOf','oneOf','allOf'):
            for child in node.get(name, []): visit(child)
    visit(value)
    return value


def validate_shape(schema, value):
    """Validate the task's small JSON-Schema subset without another dependency."""
    if schema is None: return
    kind = schema.get('type')
    kinds = kind if isinstance(kind, list) else [kind]
    matches = {'object': isinstance(value, dict), 'array': isinstance(value, list),
               'string': isinstance(value, str), 'integer': type(value) is int,
               'number': type(value) in (int,float), 'boolean': type(value) is bool, 'null': value is None}
    if kind and not any(matches.get(k,False) for k in kinds): raise InferenceError('model_output_invalid')
    if 'enum' in schema and value not in schema['enum']: raise InferenceError('model_output_invalid')
    if isinstance(value, dict):
        if any(k not in value for k in schema.get('required', [])): raise InferenceError('model_output_invalid')
        props = schema.get('properties', {})
        if schema.get('additionalProperties') is False and set(value)-set(props): raise InferenceError('model_output_invalid')
        for k,v in value.items():
            if k in props: validate_shape(props[k],v)
    if isinstance(value, list):
        if not schema.get('minItems',0) <= len(value) <= schema.get('maxItems',100000): raise InferenceError('model_output_invalid')
        for item in value: validate_shape(schema.get('items',{}),item)
    if isinstance(value, str) and len(value)>schema.get('maxLength',10000000): raise InferenceError('model_output_invalid')
    if type(value) in (int,float) and not schema.get('minimum',float('-inf')) <= value <= schema.get('maximum',float('inf')):
        raise InferenceError('model_output_invalid')


def provenance(profile, system, user, image_bytes=None):
    result = {**profile.identity, 'requested':profile.model, 'actual':None,
              'executor':'codex-cli', 'identity_source':'explicit_cli_request_not_provider_reported',
              'prompt_sha256':hashlib.sha256(system.encode()).hexdigest(),
              'input_sha256':hashlib.sha256(user.encode()).hexdigest()}
    if image_bytes is not None: result['image_sha256'] = hashlib.sha256(image_bytes).hexdigest()
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def generate(client, system, user, *, json_schema=None, image_path=None):
    p = client.profile
    image_bytes = Path(image_path).read_bytes() if image_path is not None else None
    if image_bytes is not None and len(image_bytes)>16*1024*1024: raise InferenceError('model_image_too_large')
    schema = strict_schema(json_schema) if json_schema is not None else None
    if p.url:
        key = os.environ.get(p.api_key_env or '')
        if not key: raise InferenceError('model_key_not_configured')
        body = {'profile':p.identity,'system':system,'user':user,'json_schema':schema,
                'image':base64.b64encode(image_bytes).decode() if image_bytes is not None else None}
        raw = json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
        if len(raw)>MAX_REQUEST: raise InferenceError('input_exceeds_context_budget')
        request = urllib.request.Request(p.url+'/v1/inference',data=raw,
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
        try:
            with client._slots, urllib.request.build_opener(NoRedirect).open(request,timeout=p.timeout) as response:
                raw = response.read(MAX_RESPONSE+1)
            if len(raw)>MAX_RESPONSE: raise InferenceError('model_output_invalid')
            value = json_object(raw.decode())
        except urllib.error.HTTPError as exc:
            try: code=json_object(exc.read(1024).decode()).get('error')
            except (InferenceError,UnicodeError): code=None
            allowed = {'model_quota_wait','model_relay_unavailable','model_cli_timeout','model_cli_failed',
                       'model_output_invalid','model_identity_unverified','model_cli_tool_activity',
                       'model_cli_authentication_failed','model_cli_not_installed','model_output_incomplete'}
            raise InferenceError(code if code in allowed else 'model_failure') from None
        except (OSError, ValueError, UnicodeError): raise InferenceError('model_relay_unavailable') from None
        meta = value.pop('_model',None)
        expected = provenance(p,system,user,image_bytes)
        if not isinstance(meta,dict) or any(meta.get(k)!=v for k,v in expected.items()):
            raise InferenceError('model_identity_unverified')
        validate_shape(schema,value)
        value['_model']={**expected,**{k:meta[k] for k in ('elapsed_seconds','usage') if k in meta}}
        return value
    command = [p.command,'exec','--ignore-user-config','--ignore-rules','--skip-git-repo-check',
               '--ephemeral','--sandbox','read-only','--model',p.model,'--json','--color','never']
    settings = {'model_reasoning_effort':p.reasoning_effort or 'medium','web_search':'disabled',
                'approval_policy':'never','project_doc_max_bytes':0, 'developer_instructions':system,
                'features.shell_tool':False,'features.multi_agent':False,'features.apps':False,
                'features.browser_use':False,'features.computer_use':False,'features.code_mode_host':False,
                'features.view_image':False,'features.skill_search':False,'features.sleep_tool':False,
                'features.workspace_dependencies':False,'features.tool_suggest':False}
    for k,v in settings.items(): command.extend(['-c',k+'='+json.dumps(v,ensure_ascii=False)])
    start=time.monotonic()
    try:
        with client._slots, tempfile.TemporaryDirectory(prefix='inresearch-codex-') as directory:
            root=Path(directory); answer=root/'answer.json'
            if schema is not None:
                path=root/'schema.json';path.write_text(json.dumps(schema,ensure_ascii=False))
                command.extend(['--output-schema',str(path)])
            if image_bytes is not None:
                path=root/'page.png';path.write_bytes(image_bytes);command.extend(['--image',str(path)])
            command.extend(['-o',str(answer),'-'])
            with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                proc=subprocess.run(command,input=user,text=True,cwd=directory,
                    stdout=output,stderr=errors,timeout=p.timeout,check=False)
                output.seek(0);raw=output.read(MAX_RESPONSE+1)
                # Startup warnings can fill the beginning; terminal errors are
                # frequently at the end. Inspect both bounds, never log either.
                errors.seek(0);head=errors.read(4096)
                errors.seek(0,2);size=errors.tell();errors.seek(max(0,size-8192))
                error_text=(head+b'\n'+errors.read(8192)).decode(errors='replace')
            if len(raw)>MAX_RESPONSE: raise InferenceError('model_output_invalid')
            events=[json_object(line.decode()) for line in raw.splitlines() if line.strip()]
            if proc.returncode or any(e.get('type')=='turn.failed' for e in events):
                raise cli_failure(proc.returncode,events,error_text,time.monotonic()-start)
            if not events or events[-1].get('type')!='turn.completed': raise InferenceError('model_output_incomplete')
            # CLI feature diagnostics are error items even when the inference
            # turn succeeds. They are not tool activity; turn.failed still fails.
            if any(e.get('item',{}).get('type') not in (None,'agent_message','reasoning','plan','error') for e in events):
                raise InferenceError('model_cli_tool_activity')
            if not answer.is_file() or answer.stat().st_size>MAX_RESPONSE: raise InferenceError('model_output_invalid')
            value=json_object(answer.read_text())
        value.pop('_model',None)
        validate_shape(schema,value)
        value['_model']={**provenance(p,system,user,image_bytes),'elapsed_seconds':round(time.monotonic()-start,3),
                         'usage':events[-1].get('usage',{})}
        return value
    except FileNotFoundError: raise InferenceError('model_cli_not_installed') from None
    except subprocess.TimeoutExpired: raise InferenceError('model_cli_timeout') from None
    except (OSError,UnicodeError,ValueError): raise InferenceError('model_cli_failed') from None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=37261)
    parser.add_argument('--config',required=True)
    parser.add_argument('--token-env',default='INRESEARCH_CODEX_TOKEN')
    parser.add_argument('--parallel',type=int,default=2)
    args=parser.parse_args();key=os.environ.get(args.token_env)
    if not key or len(key)<32 or not 1<=args.parallel<=4: parser.error('private token and bounded concurrency required')
    clients={}
    for role in ('research_default','core_review','ocr','gap_ocr'):
        try: p=load_profile(role,args.config)
        except InferenceError: continue
        if role=='gap_ocr' and p.backend!='codex_cli': continue
        if p.backend!='codex_cli' or p.url: parser.error('relay profiles must use local Codex CLI')
        clients[json.dumps(p.identity,sort_keys=True)]=JsonModelClient(p)
    slots=threading.BoundedSemaphore(args.parallel)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def respond(self,status,value):
            raw=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            self.respond(200,{'ready':True,'executor':'codex-cli'}) if self.path=='/healthz' else self.respond(404,{'error':'not_found'})
        def do_POST(self):
            self.connection.settimeout(30)
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+key): return self.respond(401,{'error':'unauthorized'})
            if self.path!='/v1/inference': return self.respond(404,{'error':'not_found'})
            value={}
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=MAX_REQUEST: return self.respond(413,{'error':'request_too_large'})
                value=json_object(self.rfile.read(size).decode())
                client=clients.get(json.dumps(value.get('profile'),sort_keys=True))
                if client is None: return self.respond(409,{'error':'model_identity_unverified'})
                if not isinstance(value.get('system'),str) or not isinstance(value.get('user'),str): raise ValueError()
                if not slots.acquire(blocking=False): return self.respond(503,{'error':'model_relay_unavailable'})
                try:
                    with tempfile.TemporaryDirectory(prefix='inresearch-codex-image-') as directory:
                        image=None
                        if value.get('image') is not None:
                            raw=base64.b64decode(value['image'],validate=True)
                            if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw)>16*1024*1024: raise ValueError()
                            image=Path(directory)/'page.png';image.write_bytes(raw)
                        result=client.generate(value['system'],value['user'],json_schema=value.get('json_schema'),image_path=image)
                    self.respond(200,result)
                    print(json.dumps({'at':time.time(),'state':'completed','requested_model':client.profile.model,
                        'effort':client.profile.reasoning_effort,'seconds':result['_model']['elapsed_seconds'],
                        'usage':result['_model'].get('usage',{})}),flush=True)
                finally: slots.release()
            except InferenceError as exc:
                self.respond(503,{'error':exc.code})
                print(json.dumps({'at':time.time(),'state':'failed','error':exc.code,
                    'input_sha256':hashlib.sha256(str(value.get('user','')).encode()).hexdigest(),
                    'diagnostics':getattr(exc,'diagnostics',{})}),flush=True)
            except (ValueError,TypeError,UnicodeError): self.respond(400,{'error':'invalid_request'})
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(json.dumps({'state':'ready','bind':'loopback','profiles':len(clients),'parallel':args.parallel}),flush=True)
    server.serve_forever()


if __name__=='__main__': main()
