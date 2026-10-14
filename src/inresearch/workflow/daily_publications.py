"""Owner-confirmed authored daily links; independent of research adoption."""
import argparse
from datetime import date,datetime,timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
from urllib.request import Request,build_opener,HTTPRedirectHandler
from inresearch.storage.layout import workspace_path


def database(root):
    return workspace_path('logs/daily-publications.sqlite3',root)


def validate(value):
    if not isinstance(value,dict):raise ValueError('invalid_daily_publication')
    if not re.fullmatch(r'20\d\d-\d\d-\d\d',value.get('report_date','')):raise ValueError('invalid_daily_date')
    date.fromisoformat(value['report_date'])
    if not isinstance(value.get('title'),str) or not value['title'].startswith('格洛可数据中心日报') or len(value['title'])>300:raise ValueError('invalid_daily_title')
    if not re.fullmatch(r'https://(?:www\.)?inews\.today/c/[1-9][0-9]*',value.get('url','')):raise ValueError('invalid_daily_url')
    if not re.fullmatch(r'[a-f0-9]{64}',value.get('html_sha256','')):raise ValueError('invalid_daily_sha')
    return value


def publish(root,value,*,confirmed_sha,actor,verified_page_sha,now=None):
    validate(value)
    if confirmed_sha!=value['html_sha256'] or not actor or not re.fullmatch(r'[a-f0-9]{64}',verified_page_sha):raise ValueError('exact_confirmation_and_page_verification_required')
    stamp=now or datetime.now(timezone.utc).isoformat()
    path=database(root);path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS publications(report_date TEXT PRIMARY KEY,title TEXT NOT NULL,url TEXT NOT NULL,html_sha256 TEXT NOT NULL,actor TEXT NOT NULL,published_at TEXT NOT NULL,verified_page_sha TEXT NOT NULL,pinned INTEGER NOT NULL DEFAULT 0)')
        db.execute('CREATE TABLE IF NOT EXISTS audit(at TEXT,actor TEXT,prior_json TEXT,next_json TEXT)')
        db.execute('BEGIN IMMEDIATE')
        prior=db.execute('SELECT * FROM publications ORDER BY report_date').fetchall()
        old=db.execute('SELECT html_sha256,url FROM publications WHERE report_date=?',(value['report_date'],)).fetchone()
        if old==(value['html_sha256'],value['url']):return {'status':'published','duplicate':True,'report_date':value['report_date']}
        db.execute('INSERT INTO publications VALUES(?,?,?,?,?,?,?,0) ON CONFLICT(report_date) DO UPDATE SET title=excluded.title,url=excluded.url,html_sha256=excluded.html_sha256,actor=excluded.actor,published_at=excluded.published_at,verified_page_sha=excluded.verified_page_sha',tuple(value[k] for k in ('report_date','title','url','html_sha256'))+(actor,stamp,verified_page_sha))
        # Late delivery never evicts a newer daily. All historical rows survive.
        newest=db.execute('SELECT MAX(report_date) FROM publications').fetchone()[0]
        db.execute('UPDATE publications SET pinned=(report_date=?)',(newest,))
        db.execute('INSERT INTO audit VALUES(?,?,?,?)',(stamp,actor,json.dumps(prior,ensure_ascii=False),json.dumps(value,ensure_ascii=False)))
    return {'status':'published','report_date':value['report_date'],'pinned':newest==value['report_date'],'highlight':newest==value['report_date'],'url':value['url'],'html_sha256':value['html_sha256']}


def projection(root):
    path=database(root)
    if not path.exists():return []
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('SELECT report_date,title,url,html_sha256,published_at,pinned FROM publications ORDER BY pinned DESC,report_date DESC LIMIT 90').fetchall()
    return [dict(row)|{'pinned':bool(row['pinned']),'highlight':bool(row['pinned']),'source_role':'authored_analysis'} for row in rows]


class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--html',required=True);p.add_argument('--confirmed-sha',required=True);p.add_argument('--actor',required=True);p.add_argument('--root',default=str(Path(__file__).resolve().parents[3]));args=p.parse_args()
    value=validate(json.loads(Path(args.input).read_text()))
    if hashlib.sha256(Path(args.html).read_bytes()).hexdigest()!=args.confirmed_sha or value['html_sha256']!=args.confirmed_sha:raise ValueError('confirmed_html_changed')
    # No redirect may turn a public approved URL into another host/private page.
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    with build_opener(NoRedirect).open(Request(value['url'],headers={'User-Agent':'InResearch-owner-publication/1.0'}),timeout=30) as response:
        if response.status!=200 or response.geturl()!=value['url']:raise ValueError('daily_page_not_public')
        body=response.read(4*1024*1024+1)
    if len(body)>4*1024*1024:raise ValueError('daily_page_too_large')
    text=Text();text.feed(body.decode('utf-8'))
    if value['title'] not in ''.join(text.parts):raise ValueError('daily_title_mismatch')
    print(json.dumps(publish(args.root,value,confirmed_sha=args.confirmed_sha,actor=args.actor,verified_page_sha=hashlib.sha256(body).hexdigest()),ensure_ascii=False))


if __name__=='__main__':main()
