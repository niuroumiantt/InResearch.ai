"""Preserve original bytes and make publication-sized JPEGs; no creative image edits."""
from pathlib import Path
import hashlib, json, shutil
from PIL import Image

OUT = Path(__file__).resolve().parents[2]
RAW = Path('/Users/m5/.local/share/inresearch.ai/geluoke-research/2026-10-09-us-datacenter-power/visual-originals')
USER = Path('/Users/m5/.codex/generated_images/01a07143-b842-79f3-b874-3caad9352be5')
NEW = Path('/Users/m5/.codex/generated_images/01a11dcd-34f5-79f0-837e-2345c274c075')
SPECS = [
 ('VR1', USER/'exec-da1c0d26-37b4-4648-8e30-1e70066f1ca9.png', '园区全景与地上地下剖面', 'scene-campus.jpg'),
 ('VR2', USER/'exec-1b118851-f494-402a-8d33-1599b0636dd1.png', '设备、建筑和供配电的安装关系', 'scene-cost-assets.jpg'),
 ('VR3', USER/'exec-08a47fea-a74a-4e60-8a68-41de471bf823.png', '燃料到发电再到机房的路径；只用画法，新图改为管道来气', None),
 ('VR4', USER/'exec-65d2940a-8ec9-4b6c-a81e-8027ab728978.png', '三个项目阶段的具象对照；不是同一项目时序', 'scene-stages.jpg'),
 ('VR5', USER/'exec-3156555a-0134-4882-bc8f-86cb2a7c0c99.png', '机柜、泵组与室外散热设施的工程剖面', 'scene-cooling.jpg'),
 ('NEW1', NEW/'exec-596b2a2e-53aa-4285-8371-ce553c756869.png', '已有设施旁的新增变电施工瓶颈', 'scene-bottleneck.jpg'),
 ('NEW2', NEW/'exec-e2bbb126-f7e6-4625-a7eb-d7d3b68205f9.png', '核电经公共网络到负荷的通用机制', 'scene-nuclear-grid.jpg'),
 ('NEW3', NEW/'exec-c44d0d2a-fe16-4753-b36b-91f9c178992a.png', '初稿标签过小，保留原件，不嵌入正文', None),
 ('NEW4', NEW/'exec-9d9d069c-4faa-43a0-91e0-bae866e9435a.png', '移除小标签的干净内燃机底图，出版文字独立排版', 'scene-gas-pipeline.jpg'),
]
RAW.mkdir(parents=True, exist_ok=True)
records=[]
for rid,src,role,asset in SPECS:
    target=RAW/(rid+'.png')
    if target.exists():
        assert target.read_bytes()==src.read_bytes(), 'Never overwrite different original bytes'
    else: shutil.copy2(src,target)
    with Image.open(target) as original:
        size=original.size
        if asset:
            im=original.convert('RGB')
            im.thumbnail((1280,1280),Image.Resampling.LANCZOS)
            # Only resize/compress for publishing. Preserve uncropped composition.
            im.save(OUT/'assets'/asset,quality=85,optimize=True,subsampling=2)
            assert (OUT/'assets'/asset).stat().st_size<1_000_000
    records.append({'id':rid,'origin':'用户提供的已生成参考图' if rid.startswith('VR') else '本次内置 image_gen 生成',
        'original_file':str(target),'original_package_path':'visual-originals/'+target.name,
        'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'width':size[0],'height':size[1],
        'role':role,'article_asset':'assets/'+asset if asset else None,'postprocessing':'仅下采样/压缩，无裁切、补画或结构修改',
        'evidence_role':'视觉参考/通用工程示意，不作事实来源或真实项目照片',
        'human_review':'已逐张核对用途、图文对应、主要设备与供能路径；具体布置和比例不作为工程事实'})
# A portable reference preview is published without treating it as a body figure.
preview=OUT/'work/reference-previews';preview.mkdir(exist_ok=True)
for r in records:
    if r['id']=='VR3':
        with Image.open(r['original_file']) as im:
            im=im.convert('RGB');im.thumbnail((1280,1280),Image.Resampling.LANCZOS)
            im.save(preview/'VR3.jpg',quality=85,optimize=True)
        r['reference_preview']='work/reference-previews/VR3.jpg'
    elif r['id'].startswith('VR'):
        r['reference_preview']=r['article_asset']
    if r['id']=='NEW4':
        r['editable_labels']='assets/scene-gas-labeled.svg'
        r['postprocessing']='底图仅下采样/压缩；中文标注在独立SVG层，未修改底图结构'
(OUT/'work/visual-references.json').write_text(json.dumps({'standard':'editorial-engineering-scenes-20261009',
    'as_of':'2026-10-09','records':records,'superseded_public_asset':'assets/fig1-grid.png：旧资产保留，正文不再嵌入',
    'prompts_file':'work/illustration-prompts.json','scope':'长文正文；不改网站图册迁移队列'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'originals':len(records),'article_scenes':sum(bool(r['article_asset']) for r in records)},ensure_ascii=False))
