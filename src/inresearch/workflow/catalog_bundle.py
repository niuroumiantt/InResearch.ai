"""Verify every bounded supplement batch and HTML byte before importing."""
import hashlib
import json
from pathlib import Path
import re
import tarfile
import tempfile


def import_bundle(root, stream, company):
    from .product_catalog import receive, validate, verify_snapshots
    with tempfile.TemporaryDirectory(prefix='catalog-supplement-') as directory:
        archive = Path(directory)
        count,total = 0,0
        names = set()
        with tarfile.open(fileobj=stream,mode='r|gz') as tar:
            for member in tar:
                name = member.name
                if not member.isfile() or name in names or not re.fullmatch(r'(?:manifest\.json|report\.json|catalogs/batch-\d{5}\.json|originals/[0-9a-f]{64}\.html)',name):
                    raise ValueError('invalid or duplicate catalog bundle member')
                count += 1; total += member.size
                if count>25000 or total>512*1024*1024 or member.size>16*1024*1024:
                    raise ValueError('catalog bundle size bound exceeded')
                names.add(name)
                path = archive / name
                path.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(member) as inp,path.open('wb') as out:
                    import shutil
                    shutil.copyfileobj(inp,out)
        manifest = json.loads((archive/'manifest.json').read_text())
        if manifest.get('schema_version') != 1 or manifest.get('company_id') != company or manifest.get('mode') != 'historical_supplement':
            raise ValueError('historical supplement manifest required')
        entries = manifest.get('batches')
        if not isinstance(entries,list) or not entries or len(entries)>10000:
            raise ValueError('nonempty bounded batch list required')
        payloads,seen = [],set()
        for entry in entries:
            name = entry['path']
            if name not in names or not re.fullmatch(r'catalogs/batch-\d{5}\.json',name) or name in seen:
                raise ValueError('invalid or repeated manifest batch')
            seen.add(name)
            body = (archive/name).read_bytes()
            if hashlib.sha256(body).hexdigest() != entry['sha256']:
                raise ValueError('catalog batch SHA mismatch')
            payload = validate(json.loads(body),company)
            if payload.get('catalog_mode') != 'historical_supplement':
                raise ValueError('bundle can only supplement a current catalog')
            verify_snapshots(payload,archive)
            payloads.append(payload)
        from .product_catalog import database
        from .catalog_materials import check_material_products
        import sqlite3
        ids = {p['id'] for batch in payloads for p in batch['products']}
        path = database(root,company)
        if path.is_file():
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
                ids.update(r[0] for r in db.execute('SELECT id FROM products WHERE run_id=(SELECT id FROM runs ORDER BY generated DESC LIMIT 1)'))
        if len(ids)>10000:
            raise ValueError('supplemented catalog size limit exceeded')
        previous_stamp = None
        from datetime import datetime
        for batch in payloads:
            check_material_products(batch.get('material_index',[]),ids)
            stamp = datetime.fromisoformat(batch['generated_at'])
            if previous_stamp is not None and stamp<=previous_stamp:
                raise ValueError('bundle batch timestamps must increase')
            previous_stamp = stamp
        # Whole bundle is byte/schema verified before the first DB transaction.
        # Batches commit individually and are replayable after interruptions.
        receipts = [receive(root,p,company) for p in payloads]
        from .catalog_materials import query
        from .product_catalog import summary_snapshot
        materials = query(root,company,limit=1)
        return {'ok':True,'company_id':company,'batches':len(receipts),
                'added_products':sum(r.get('added_products',0) for r in receipts),
                'indexed_materials':materials['total'],'unassigned_materials':materials.get('unassigned',0),
                'catalog_summary':summary_snapshot(root,company).get('summary',{}),'receipts':receipts}
