"""Conservative project identity and power observations; never adopted facts."""
import re
import unicodedata


def normalized(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))
    return re.sub(r'[^\w]+', ' ', value).strip()


def contains(text, alias):
    alias = normalized(alias)
    if re.search(r'[\u3400-\u9fff]', alias): return bool(alias and alias in normalized(text))
    return bool(alias and re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', normalized(text)))


def identity(item, sites, companies=()):
    text = ' '.join(str(item.get(k) or '') for k in ('title', 'title_zh'))
    actors = {x[6:] for x in item.get('object_ids') or [] if x.startswith('actor:')}
    for company in companies:
        if any(contains(text, company.get(k) or '') for k in ('name', 'name_cn')):
            actors.add(company['company_id'])
    candidates = []
    company_words = {word for c in companies for word in normalized(c.get('name') or '').split()}
    generic = {'stargate','campus','county','township','center','centre','digital','india','south','north','central','region','project'}
    for site in sites:
        if site.get('duplicate_of') or 'portfolio' in site.get('site_id', ''): continue
        if not actors.intersection(site.get('developer', []) + site.get('tenant', [])): continue
        # Registered aliases are authoritative names. A city is only a candidate,
        # never sufficient to merge multiple campuses or rewrite a site record.
        names = [site['name']]
        hits = [n for n in names if len(normalized(n)) >= 5 and contains(text, n)]
        actor_words = set(re.split(r'[\s-]+', ' '.join(site.get('developer',[])+site.get('tenant',[]))))
        physical = [t for t in site['site_id'].split('-')[2:] if len(t)>=5 and t not in actor_words
                    and t not in ('microsoft','google','stargate','campus','center','fairwater')]
        aliases = [a for a in site.get('aliases',[]) if len(normalized(a))>=5 and contains(text,a)
                   and (any(contains(a,t) for t in physical) or re.search(r'[A-Za-z]+\d{2,}',a))]
        landmarks = [t for t in re.findall(r'[A-Za-z][A-Za-z0-9-]{4,}',site['name'])
                     if t.casefold() not in company_words|generic and contains(text,t)]
        location = site.get('location', '').split(',')[-1].strip()
        if hits:
            candidates.append({'site_id': site['site_id'], 'method': 'registered_name_and_actor', 'anchor': hits[0]})
        elif aliases:
            candidates.append({'site_id': site['site_id'], 'method': 'registered_alias_candidate', 'anchor': aliases[0]})
        elif len(normalized(location)) >= 5 and contains(text, location):
            candidates.append({'site_id': site['site_id'], 'method': 'location_and_actor_candidate', 'anchor': location})
        elif landmarks:
            candidates.append({'site_id':site['site_id'],'method':'project_landmark_and_actor_candidate','anchor':landmarks[0]})
    exact = [c for c in candidates if c['method'] == 'registered_name_and_actor']
    matched = exact[0]['site_id'] if len(exact) == 1 else None
    return {'matched_site_id': matched, 'site_candidates': candidates,
            'match_method': 'registered_name_and_actor' if matched else None}


def power(text, locator='headline'):
    rows = []
    pattern = r'(?<![\d.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:GW|MW|吉瓦|兆瓦)(?![A-Za-z/])'
    for match in re.finditer(pattern, text, re.I):
        quote = text[max(0, match.start()-100):match.end()+100].strip()
        # Separate bases. Generic "power" and a remote IT mention are insufficient.
        left = text[max(0,match.start()-60):match.start()]
        right = text[match.end():match.end()+60]
        near = re.split(r'[,，;；。\n]',left)[-1] + match.group() + re.split(r'[,，;；。\n]',right)[0]
        basis = 'unknown'
        it = bool(re.search(r'IT\s*(?:load|capacity|power|负载|负荷|容量|功率)|计算设备负荷', near, re.I))
        facility = bool(re.search(r'设施|场址|总功率|facility|site power|grid|interconnect|发电|供电|电站|generation', near, re.I))
        if it != facility: basis = 'it' if it else 'facility_or_grid'
        number = float(re.search(r'[\d,.]+', match.group()).group().replace(',', ''))
        rows.append({'quoted_value': match.group(), 'mw': number * (1000 if re.search(r'GW|吉瓦', match.group(), re.I) else 1),
                     'basis': basis, 'locator': locator, 'quote': quote, 'acceptance': 'candidate'})
    return rows


def constraints(text):
    return [name for name, pattern in (
        ('power', r'缺电|供电|电网|并网|电力|停电|grid|power|electricity|interconnect'),
        ('water', r'缺水|用水|水资源|water|drought'),
        ('permits', r'审批|许可|审查|审议|环保|环境|permit|approv|review|environment'),
        ('land', r'土地|选址|地块|land|zoning|site selection'),
        ('finance', r'投资|融资|借贷|贷款|investment|financ|loan|debt')) if re.search(pattern, text, re.I)]
