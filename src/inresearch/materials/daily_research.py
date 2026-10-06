"""Validate explicitly authored event metadata; preserve candidate status and gaps."""
import json
import math
from pathlib import Path
import re
from inresearch.adapters.news_sync import public_url

STAGES={'unknown','planning','applied','approved','contracted','financed','construction','commissioning','operating','paused','cancelled'}
BASES={'unknown','it','facility','grid','generation','lease'}


def power_quantities(text):
    """Literal power units only; English spellings share the MW/GW contract."""
    pattern = r'(?<![\w.\-])(\d[\d,]*(?:\.\d+)?)\s*(megawatts?|gigawatts?|MW|GW|兆瓦|吉瓦)(?![A-Za-z/\-])(?!\s+hours?\b)'
    units = {'兆瓦':'MW', '吉瓦':'GW'}
    return [(float(n.replace(',', '')), units.get(u, 'GW' if u.lower().startswith('giga') else 'MW' if u.lower().startswith('mega') else u.upper()))
            for n, u in re.findall(pattern, text, re.I)]


def load(path, html_sha256, available):
    path=Path(path)
    if path.stat().st_size>5*1024*1024:raise ValueError('daily_research_too_large')
    value=json.loads(path.read_text())
    if not isinstance(value,dict) or value.get('schema_version')!=1 or value.get('html_sha256')!=html_sha256 or not isinstance(value.get('events'),list) or not 1<=len(value['events'])<=100:
        raise ValueError('invalid_daily_research')
    sections=set()
    for event in value['events']:
        if not isinstance(event,dict) or type(event.get('section')) is not int or event['section']<1 or event['section'] in sections:
            raise ValueError('invalid_daily_research_section')
        sections.add(event['section'])
        if event.get('stage') not in STAGES:raise ValueError('invalid_daily_research_stage')
        project=event.get('project')
        if not isinstance(project,dict):raise ValueError('daily_research_project_required')
        for key in ('name','country','province','city','address','campus','phase','developer','operator','customer'):
            item=project.get(key)
            if item is not None and (not isinstance(item,str) or len(item)>2000):raise ValueError('invalid_daily_research_project')
        for key in ('event_date','reported_date'):
            item=event.get(key)
            if item is not None:
                from datetime import date
                date.fromisoformat(item)
        refs=event.get('sources')
        if not isinstance(refs,list) or not refs or len(refs)>30:raise ValueError('daily_research_sources_required')
        for source in refs:
            if not isinstance(source,dict) or source.get('url') is not None and not public_url(source['url']):raise ValueError('invalid_daily_research_source')
            evidence=source.get('evidence_file')
            if evidence is not None and evidence not in available:raise ValueError('daily_research_evidence_not_delivered')
            if not source.get('url') and not evidence and not isinstance(source.get('label'),str):raise ValueError('daily_research_source_label_required')
        capacities=event.get('capacities',[])
        if not isinstance(capacities,list) or len(capacities)>30:raise ValueError('invalid_daily_research_capacities')
        for c in capacities:
            if (not isinstance(c,dict) or type(c.get('value')) not in (int,float) or not math.isfinite(c['value']) or c['value']<0
                    or c.get('unit') not in ('MW','GW') or c.get('basis') not in BASES
                    or c.get('nature') not in ('observed','announced','forecast','unknown')
                    or not isinstance(c.get('scope'),str) or not c['scope'].strip()
                    or not isinstance(c.get('phase'),str) or not isinstance(c.get('quote'),str) or not c['quote'].strip()
                    or type(c.get('source_index')) is not int or not 0<=c['source_index']<len(refs)):
                raise ValueError('invalid_daily_research_capacity')
        constraints=event.get('constraints',[])
        if not isinstance(constraints,list) or len(constraints)>30:raise ValueError('invalid_daily_research_constraints')
        for c in constraints:
            if (not isinstance(c,dict) or c.get('kind') not in ('power','water','permits','land','finance','network')
                    or not isinstance(c.get('quote'),str) or not c['quote'].strip()
                    or type(c.get('source_index')) is not int or not 0<=c['source_index']<len(refs)):
                raise ValueError('invalid_daily_research_constraint')
        gaps=event.get('gaps',[])
        if not isinstance(gaps,list) or len(gaps)>30 or any(not isinstance(g,str) or len(g)>2000 for g in gaps):
            raise ValueError('invalid_daily_research_gaps')
    return value


def attach(events, value, metadata_sha256, available, folder):
    by_section={ref['section']:e for e in events for ref in e['document_refs'] if ref['sha256']==value['html_sha256']}
    for event in value['events']:
        if event['section'] not in by_section:raise ValueError('daily_research_section_not_in_html')
        row=by_section[event['section']]
        # Evidence quotes must be literal in the delivered source text or HTML
        # section. PDFs remain explicitly unverified until text is delivered.
        checks=[]
        for observation in event.get('capacities',[])+event.get('constraints',[]):
            source=event['sources'][observation['source_index']]
            rel=source.get('evidence_file')
            if rel and Path(rel).suffix.lower() in ('.txt','.md'):
                text=(Path(folder)/rel).read_text(encoding='utf-8')
                locator=rel;checked_sha=available[rel]['sha256']
            else:text=row['body'];locator='html-section:'+str(event['section']);checked_sha=value['html_sha256']
            exact=''.join(observation['quote'].split()) in ''.join(text.split())
            numeric=True
            if 'value' in observation:
                quantities=power_quantities(observation['quote'])
                numeric=(observation['value'],observation['unit']) in quantities
            checks.append({'quote':observation['quote'],'locator':locator,'exact_quote':exact,'quantity_present':numeric,
                           'source_sha256':checked_sha})
        authored={**event,'acceptance':'candidate','metadata_sha256':metadata_sha256,'evidence_checks':checks}
        if row.get('editorial_event') and row['editorial_event']!=authored:
            row.setdefault('editorial_history',[]).append(row['editorial_event'])
        row.update(editorial_event=authored,
                   structured_evidence_status='quotes_verified' if checks and all(c['exact_quote'] and c['quantity_present'] for c in checks) else 'awaiting_quote_verification' if checks else 'no_quantitative_observations')
        for i,source in enumerate(event['sources']):
            if source.get('url'):
                linked={'label':source.get('label') or source['url'],'urls':[source['url']],
                        'source_sha256':metadata_sha256,'source_locator':'research-events.json#'+str(event['section'])+'/sources/'+str(i)}
                if linked not in row['sources']:row['sources'].append(linked)
    return events
