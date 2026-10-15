#!/usr/bin/env python3
"""Fixed-command SSH gateway, fetchstat only; bounded stdin, no shell/file paths."""
import base64
import errno
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from inresearch.materials import collector_production as production

PROTOCOL='fetchstat-ssh-gateway/1'
MAX_INPUT=114*1024*1024
DATA=Path.home()/'.local/share/inresearch.ai'
ROOT=Path(__file__).resolve().parents[1]


def execute(request, data_root):
    if not isinstance(request,dict) or request.get('protocol')!=PROTOCOL or request.get('provider')!='fetchstat':
        raise ValueError('gateway_scope_invalid')
    delivery=request.get('delivery')
    if not isinstance(delivery,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',delivery):raise ValueError('gateway_delivery_invalid')
    if request.get('action')=='lookup':
        if set(request)!={'protocol','provider','delivery','action','receiver_revision'}:raise ValueError('gateway_fields_invalid')
        receipt=production.lookup_receipt(data_root,'fetchstat',delivery)
        return dict(protocol=PROTOCOL,found=receipt is not None,receipt=receipt)
    if request.get('action')!='deliver' or set(request)!={'protocol','provider','delivery','action','receiver_revision','files'}:
        raise ValueError('gateway_fields_invalid')
    files=request['files']
    if not isinstance(files,dict) or not 5<=len(files)<=10005:raise ValueError('gateway_files_invalid')
    with tempfile.TemporaryDirectory(prefix='fetchstat-ingress-') as tmp:
        root=Path(tmp);total=0
        for name,value in files.items():
            path=PurePosixPath(name)
            if not isinstance(name,str) or path.is_absolute() or '..' in path.parts or str(path)!=name or not path.parts or '\\' in name:
                raise ValueError('gateway_path_invalid')
            if not isinstance(value,str) or len(value)>28*1024*1024:raise ValueError('gateway_file_budget')
            raw=base64.b64decode(value,validate=True);total+=len(raw)
            if len(raw)>20*1024*1024 or total>80*1024*1024:raise ValueError('gateway_byte_budget')
            dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        report=production.validator.validate(root)
        manifest=json.loads((root/'manifest.json').read_text())
        if not report['offline_valid'] or manifest['provider_id']!='fetchstat' or manifest['delivery_id']!=delivery:
            raise ValueError('gateway_package_scope_invalid')
        selected=production.inventory(root)
        if set(selected)!=set(files):raise ValueError('gateway_extra_files')
        receipt=production.receive(root,data_root)
        return dict(protocol=PROTOCOL,receipt=receipt)


def main():
    try:
        if os.environ.get('SSH_ORIGINAL_COMMAND')!='fetchstat-gateway-v1':raise ValueError('gateway_fixed_command_required')
        raw=sys.stdin.buffer.read(MAX_INPUT+1)
        if len(raw)>MAX_INPUT:raise ValueError('gateway_input_budget')
        request=json.loads(raw)
        revision=request.get('receiver_revision') if isinstance(request,dict) else None
        actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
        if not isinstance(revision,str) or not re.fullmatch('[0-9a-f]{40}',revision) or actual!=revision or dirty:
            raise ValueError('gateway_receiver_revision_changed_or_dirty')
        print(json.dumps(execute(request,DATA),ensure_ascii=False));return 0
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error,subprocess.SubprocessError) as error:
        category='busy' if getattr(error,'errno',None) in (errno.EAGAIN,errno.EWOULDBLOCK) else 'local_storage' if isinstance(error,(OSError,sqlite3.Error)) else 'integrity_conflict'
        print(json.dumps(dict(protocol=PROTOCOL,received=False,error_type=type(error).__name__,error_category=category)),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
