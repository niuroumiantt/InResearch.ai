"""Conservative product-level compute projection, independent of vendor navigation."""
import re

CATEGORIES = {'cpu': 'CPU', 'gpu': 'GPU', 'accelerator': '其他计算加速器', 'unknown': '待核验', 'excluded': '非计算芯片'}
FORMS = {'chip': '芯片', 'board': '板卡 / 模组', 'system': '整机 / 平台', 'series': '系列 / 目录', 'ip': 'IP', 'unknown': '形态待核验'}
VERSION = '2026-10-02.1'


def project(product, company):
    # Delivered reviewed metadata wins; raw vendor navigation is never modified.
    if product.get('compute'):
        return {**product['compute'], 'version': VERSION, 'basis': 'reviewed_official_product'}
    name = product.get('name', '')
    result = {'category': 'unknown', 'form': 'unknown', 'architecture': '',
              'version': VERSION, 'basis': 'conservative_name_projection'}
    nav = product.get('navigation', {})
    if nav.get('group') == 'software' or nav.get('family') in {'networking', 'gsync', 'shield'}:
        return {**result, 'category': 'excluded'}
    if product.get('kind') == 'family_or_directory':
        result['form'] = 'series'
        return result
    if product.get('kind') == 'software_service' or re.search(r'BlueField|ConnectX|Spectrum|NVLink|NVSwitch|SuperNIC|\bDPU\b|\bNIC\b|G-SYNC', name, re.I):
        result['category'] = 'excluded'
        return result
    if company == 'arm' or re.search(r'\b(?:Cortex|Neoverse)\b', name, re.I):
        return {**result, 'category': 'excluded', 'form': 'ip'}
    if re.search(r'\b(?:DGX|HGX|MGX|GB\d+|NVL\d+|Jetson|IGX|DRIVE)\b|server|服务器|整机|机柜', name, re.I):
        return {**result, 'form': 'system'}
    if company == 'nvidia':
        if re.search(r'\bGrace CPU\b', name, re.I):
            return {**result, 'category': 'cpu', 'form': 'board' if 'superchip' in name.lower() else 'chip'}
        if re.search(r'\b(?:[ABHV]\d{2,3}(?:\s|$)|RTX|GeForce|Quadro|Tesla)\b', name, re.I):
            # H200 etc can be chip, SXM module or PCIe card; don't infer packaging.
            return {**result, 'category': 'gpu'}
    if company == 'intel' and re.search(r'\bGaudi\b', name, re.I):
        return {**result, 'category': 'accelerator'}
    if company in {'intel','amd'}:
        if re.search(r'\b(?:Xeon|Core|EPYC|Ryzen|Threadripper)\b', name, re.I):
            return {**result, 'category': 'cpu', 'form': 'chip'}
        if re.search(r'\b(?:Instinct|Radeon|Arc|Data Center GPU)\b', name, re.I):
            return {**result, 'category': 'gpu'}
    # In particular DCU is NOT a company-wide architecture rule.
    return result


def validate(value, source_keys):
    if not isinstance(value, dict) or value.get('category') not in CATEGORIES or value.get('form') not in FORMS:
        raise ValueError('invalid compute classification')
    if not isinstance(value.get('architecture', ''), str) or len(value.get('architecture', '')) > 500:
        raise ValueError('invalid compute architecture')
    refs = value.get('source_refs')
    if not isinstance(refs, list) or not refs or any(not isinstance(r, dict) or (r.get('sha256'), r.get('url')) not in source_keys for r in refs):
        raise ValueError('compute classification requires snapshot evidence')
    if value.get('architecture') and not value.get('architecture_quote'):
        raise ValueError('architecture requires a model-specific official quote')
    for field in ('evidence_quote', 'architecture_quote'):
        if field in value and (not isinstance(value[field], str) or len(value[field]) > 4000):
            raise ValueError('invalid compute evidence quote')
