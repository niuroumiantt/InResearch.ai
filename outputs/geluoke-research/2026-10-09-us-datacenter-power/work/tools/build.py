from pathlib import Path
import base64,html,json,re
from PIL import Image,ImageOps,ImageDraw
OUT=Path(__file__).resolve().parents[2];A=OUT/'assets'
font='Arial,"PingFang SC","Microsoft YaHei","Noto Sans SC","WenQuanYi Zen Hei",sans-serif'
imgs=[]
for p in A.glob('*-render.png'):
    if p.name.startswith('cover'):
        im=Image.open(A/'cover-master.png').convert('RGB');im.resize((1080,1620),Image.Resampling.LANCZOS).save(A/'cover-wechat.jpg',quality=88,optimize=True)
        # Separate optional platform list-cover crop, composed from the top panel.
        ImageOps.fit(im.crop((0,0,2400,1100)),(900,383),Image.Resampling.LANCZOS).save(A/'cover-list-2.35.jpg',quality=88,optimize=True)
    else:
        im=Image.open(p).convert('RGB').quantize(colors=256);im.save(A/p.name.replace('-render',''),optimize=True)
    p.unlink()
for p in sorted(A.glob('*.png')):
    with Image.open(p) as im:imgs.append(dict(path='assets/'+p.name,width=im.width,height=im.height,bytes=p.stat().st_size,mode=im.mode))
for p in sorted(A.glob('*.jpg')):
    with Image.open(p) as im:imgs.append(dict(path='assets/'+p.name,width=im.width,height=im.height,bytes=p.stat().st_size,mode=im.mode))
doc=(OUT/'article.md').read_text();paras=doc.strip().split('\n\n')
def safe(s):return re.sub(r'\[(\d+)\]',r'<span style="font-size:0.85em;color:#1E66B3">[\1]</span>',html.escape(s))
def heading(s):
    if '：' in s:
        a,b=s.split('：',1)
        return '<span style="display:block;">'+safe(a+'：')+'</span><span style="display:block;">'+safe(b)+'</span>'
    return safe(s)
def src(p,embed):
    f=OUT/p
    return 'data:'+('image/jpeg' if f.suffix=='.jpg' else 'image/png')+';base64,'+base64.b64encode(f.read_bytes()).decode() if embed else p
def image_tag(p,alt,embed):return f'<img src="{src(p,embed)}" alt="{html.escape(alt)}" style="display:block;width:100%;height:auto;margin:18px 0;"/>'
def build(mode):
    embed=mode!='lite';content=[image_tag('assets/cover-wechat.jpg','美国数据中心电力专题总览',embed)];small=False;comment=False
    for para in paras:
        if para.startswith('# '):content.append('<h1 style="font-size:26px;font-weight:700;color:#0068B5;line-height:1.45;margin:24px 0 16px;text-wrap:balance;">'+heading(para[2:])+'</h1>')
        elif para.startswith('## '):
            h=para[3:];small=h in ['来源','备注'];comment=h=='格洛可点评'
            content.append('<h2 style="font-size:22px;color:#08577C;line-height:1.5;margin:32px 0 16px;font-weight:700;text-wrap:balance;">'+heading(h)+'</h2>')
        elif para.startswith('!['):
            m=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',para);assert m;content.append(image_tag(m[2],m[1],embed))
        else:
            size=11 if small else 12 if para.startswith('图') else 14 if para.startswith(('格洛可｜','本篇覆盖')) else 17
            color='#5A6B7F' if size<17 else '#1F2A37'
            ff='FangSong,STFangsong,"仿宋","Songti SC",serif' if comment else font
            content.append(f'<p style="font-size:{size}px;line-height:1.8;color:{color};margin:0 0 {10 if small else 19}px;text-align:justify;font-family:{ff};overflow-wrap:break-word;">'+safe(para)+'</p>')
    wrap='margin:0;font-family:'+font+';background:white;'
    css='' if mode=='wechat' else '<style>html,body{margin:0;background:white}body{padding:0 16px}article{max-width:720px;margin:auto}@media(max-width:767px){body{padding:0 8px}}img{max-width:100%}h1,h2{text-wrap:balance}</style>'
    return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>美国数据中心的电力现状｜格洛可</title>'+css+'</head><body style="'+wrap+'"><article style="background:white;'+('' if mode!='wechat' else 'margin:0;padding:0;')+'">'+''.join(content)+'</article></body></html>'
for mode in ['wechat','full','lite']:(OUT/(mode+'.html')).write_text(build(mode))
body=doc.split('## 来源')[0];body='\n'.join(x for x in body.splitlines() if not x.startswith(('#','!','图','本篇覆盖','格洛可｜')))
public_images=['assets/cover-wechat.jpg']+re.findall(r'!\[.*?\]\((.*?)\)',doc)
stats=dict(body_images=len(public_images)-1,public_images=public_images,body_hanzi=len(re.findall('[\u4e00-\u9fff]',body)),body_nonspace_characters=len(re.sub(r'\[\d+\]|\s','',body)),images=imgs,html_bytes={m:(OUT/(m+'.html')).stat().st_size for m in ['wechat','full','lite']},wechat_editor='未实粘；浏览器验收不替代微信编辑器',image_upload='单张公众号图JPG/PNG均小于1MB；Base64是复制包形式，发布需转为公众号素材URL')
(OUT/'checks/build.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2))
# Contact sheet follows actual public figure order; older unused assets are excluded.
thumbs=[]
for name in public_images[1:]:
    im=Image.open(OUT/name).convert('RGB');im.thumbnail((400,600));thumbs.append((name,im))
rows=(len(thumbs)+2)//3
sheet=Image.new('RGB',(1230,rows*640),'#e7ecf0');d=ImageDraw.Draw(sheet)
for i,(name,im) in enumerate(thumbs):
    x=(i%3)*410;y=(i//3)*640;sheet.paste(im,(x,y+25));d.text((x+5,y+5),name,fill='black')
sheet.save(OUT/'checks/figures-contact.jpg',quality=90)
print(json.dumps({'body_hanzi':stats['body_hanzi'],'body_images':stats['body_images'],'html_bytes':stats['html_bytes']},ensure_ascii=False))
