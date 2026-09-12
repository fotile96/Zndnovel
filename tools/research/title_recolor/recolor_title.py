#!/usr/bin/env python3
"""Color-only title-logo study. All inputs/outputs are outside the repository.
Oklab matrices: https://bottosson.github.io/posts/oklab/ (public-domain code).
A spatially separated, smooth tone/chroma/hue transfer, calibrated at game size,
applied to the full-resolution Chinese source before the existing downsampler.
RGBA alpha is byte-identical to source. No glyph, geometry, or layout operations.
"""
import sys, argparse, json, hashlib
from pathlib import Path
sys.dont_write_bytecode=True
import numpy as np
from scipy.interpolate import PchipInterpolator
from PIL import Image, ImageDraw, ImageFont
from probe import ROOT, REPO, IN, lab, rgb
sys.path.insert(0,str(REPO))
from tools.bake_finale_title import fit_logo, content_box, compose_title_mock
from tools.build_disc import quantize_for_template


def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0,1)
    return t*t*(3-2*t)

def hue(v): return np.mod(np.arctan2(v[...,2],v[...,1]),2*np.pi)
def angle(a): return (a+np.pi)%(2*np.pi)-np.pi

def masks(im, reference=False):
    ar=np.array(im.convert('RGBA'))/255.; c=ar[...,:3]; v=lab(c)
    y=np.arange(im.height)[:,None]
    opaque=ar[...,3]>.95
    blue=(c[...,2]-c[...,0]>.075)&(v[...,0]<.65)&opaque
    warm=(c[...,0]-c[...,2]>.05)&(c[...,0]-c[...,1]>.015)&opaque
    return {
      'main':blue&(y<(49 if reference else 53)),
      'subtitle':blue&(y>=(58 if reference else 64)),
      'gold':warm&(y>=(44 if reference else 53))&(y<(59 if reference else 64)),
      'orange':warm&(y>=(59 if reference else 64)),
    }

def summarize(v,m):
    z=v[m]; med=np.median(z,axis=0)
    return {'n':int(m.sum()),'rgb_median':[round(float(x),1) for x in np.median(np.clip(rgb(z),0,1)*255,axis=0)],'L_quantiles':np.quantile(z[:,0],[.1,.5,.9]).tolist(),'chroma_median':float(np.median(np.linalg.norm(z[:,1:],axis=-1))),'hue_degrees':float(np.degrees(np.median(hue(z))))}

def calibrate(jp,zh):
    j=lab(np.array(jp)[...,:3]/255); z=lab(np.array(zh)[...,:3]/255)
    jm=masks(jp,True); zm=masks(zh)
    params={}
    for name in jm:
        js=summarize(j,jm[name]); zs=summarize(z,zm[name])
        params[name]={'reference':js,'source':zs,'chroma_ratio':js['chroma_median']/zs['chroma_median'],'hue_rotation':np.radians(js['hue_degrees']-zs['hue_degrees'])}
    return params

def tone_curve(v,p):
    s=np.array(p['source']['L_quantiles']); t=np.array(p['reference']['L_quantiles'])
    # Force ordered source anchors, endpoint identity; interpolate monotonic L.
    xs=np.r_[0,s,1]; ys=np.r_[max(0,t[0]-s[0]),t,1]
    return PchipInterpolator(xs,ys)(np.clip(v,0,1))

def transfer(v,p):
    out=v.copy(); out[...,0]=tone_curve(v[...,0],p)
    th=p['hue_rotation']; co,si=np.cos(th),np.sin(th)
    out[...,1]=(co*v[...,1]-si*v[...,2])*p['chroma_ratio']
    out[...,2]=(si*v[...,1]+co*v[...,2])*p['chroma_ratio']
    return out

def gamut_rgb(v):
    """Bring out-of-sRGB colours in gamut by reducing chroma at fixed L and hue.
    Binary search only the affected pixels; avoid hard clipping coloured highlights.
    """
    value=v.copy(); value[...,0]=np.clip(value[...,0],0,1)
    result=rgb(value)
    bad=((result < -1e-7)|(result > 1+1e-7)).any(axis=-1)
    z=value[bad].copy()
    if len(z):
        lo=np.zeros(len(z)); hi=np.ones(len(z))
        for _ in range(17):
            mid=(lo+hi)/2
            trial=z.copy(); trial[:,1:]*=mid[:,None]
            c=rgb(trial)
            ok=((c>=-1e-7)&(c<=1+1e-7)).all(axis=-1)
            lo=np.where(ok,mid,lo); hi=np.where(ok,hi,mid)
        z[:,1:]*=lo[:,None]
        result[bad]=rgb(z)
    return result, int(bad.sum())

def process(src,params,strength=.85,halo_strength=.8,gradient_strength=.55):
    original=np.array(src.convert('RGBA')); c=original[...,:3]/255.; a=original[...,3]/255
    v=lab(c); L=v[...,0]; C=np.linalg.norm(v[...,1:],axis=-1); H=hue(v)
    l,t,r,b=content_box(src); yy=(np.arange(src.height)[:,None]-t)/(b-t)*89
    # Transition bands fall in empty space between lettering and ornament.
    main_gate=1-smooth(53,57,yy); sub_gate=smooth(61,64,yy)
    line_gate=(1-main_gate)*(1-sub_gate)
    blue=smooth(.015,.08,c[...,2]-c[...,0])
    # Gradually taper between coloured ink and light edging. No hard RGB masks.
    ink=blue*(1-smooth(.64,.79,L))
    valid=(a>0)
    adjusted=v.copy()
    for name,gate in [('main',main_gate),('subtitle',sub_gate)]:
        target=transfer(v,params[name])
        if name=='main' and gradient_strength:
            # Original top stroke highlights lean lavender and fade darker downward.
            # The generated source has a brighter/cyan tail instead. Soft row correction.
            yrel=np.clip(yy/53,0,1)
            target[...,0]+=np.interp(yrel,[0,.28,.55,1],[.03,.025,.012,-.065])*gradient_strength
            target_h=np.radians(np.interp(yrel,[0,.28,.55,1],[269,267,256,254]))
            rot=angle(target_h-hue(target))*gradient_strength*.6
            ta,tb=target[...,1].copy(),target[...,2].copy()
            target[...,1]=np.cos(rot)*ta-np.sin(rot)*tb
            target[...,2]=np.sin(rot)*ta+np.cos(rot)*tb
        w=ink*gate*strength*valid
        adjusted += (target-v)*w[...,None]
    # Warm gold divider and orange -> reference's subdued gold / salmon pink.
    warmth=smooth(.015,.075,c[...,0]-c[...,2])*smooth(.003,.025,c[...,0]-c[...,1])
    for name,gate in [('gold',1-sub_gate),('orange',sub_gate)]:
        target=transfer(v,params[name]); w=warmth*gate*strength*valid
        adjusted+=(target-v)*w[...,None]
    # Pale rim and low-alpha blue aura are separate: reference outer glow is neutral.
    light=smooth(.66,.84,L)*(1-warmth)
    opaque=smooth(.80,.99,a)
    inner=v.copy()
    inner[...,0]=L-np.where(main_gate>.5,.075,.02)*smooth(.74,.94,L)
    rim_h=np.radians(215.)
    rim_C=C*.75
    inner[...,1]=rim_C*np.cos(rim_h); inner[...,2]=rim_C*np.sin(rim_h)
    outer=v.copy()
    # Empirical original halo L vs opacity from alpha strata (see report).
    outer[...,0]=np.clip(L+np.interp(a,[0,.2,.45,.75,.95,1],[.16,.16,.142,.057,-.10,-.10]),0,1)
    outer[...,1:]=v[...,1:]*np.interp(a,[0,.2,.45,.75,.95,1],[0,0,.15,.43,.8,.8])[...,None]
    target=outer*(1-opaque[...,None])+inner*opaque[...,None]
    w=light*halo_strength*valid
    adjusted+=(target-v)*w[...,None]
    linear,compressed=gamut_rgb(adjusted)
    changed=(np.abs(adjusted-v).max(axis=-1)>1e-12)&valid
    out=original.copy()
    out[...,:3]=np.clip(np.round(linear*255),0,255).astype('uint8')
    out[~changed]=original[~changed]
    assert np.array_equal(out[...,3],original[...,3])
    assert np.array_equal(out[original[...,3]==0],original[original[...,3]==0])
    return Image.fromarray(out),{'changed_pixels':int(changed.sum()),'gamut_compressed_pixels':compressed,'gamut_clipped_pixels':int((((linear<-.0001)|(linear>1.0001)).any(axis=-1)&changed).sum())}

FONT='/System/Library/Fonts/Hiragino Sans GB.ttc'
def font(size): return ImageFont.truetype(FONT,size)

def make_sheet(items,out,scale=2,white=False):
    # Render composites before resize, never interpolate unassociated alpha.
    cellw=480*scale; cellh=150*scale
    sheet=Image.new('RGB',(cellw,cellh*len(items)),(244,244,240)); d=ImageDraw.Draw(sheet)
    for i,(title,im) in enumerate(items):
        y=i*cellh; d.text((14,y+10),title,font=font(12*scale),fill=(30,38,42))
        if white: frame=Image.new('RGBA',(480,110),'white')
        else: frame=Image.open(IN/'menu_bg.png').convert('RGBA').crop((0,0,480,110))
        frame.alpha_composite(im,(38,10))
        sheet.paste(frame.convert('RGB').resize((cellw,110*scale),Image.Resampling.NEAREST),(0,y+35*scale))
    sheet.save(out)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=ROOT/'round2')
    ap.add_argument('--strength',type=float,help='Single custom candidate: ink/warm color transfer, 0..1')
    ap.add_argument('--halo-strength',type=float,default=.8)
    ap.add_argument('--gradient-strength',type=float,default=.55)
    ap.add_argument('--label',default='custom')
    args=ap.parse_args()
    if args.out.resolve().is_relative_to(REPO.resolve()):
        ap.error('Output must be outside the repository for this study.')
    if not args.label.replace('_','').replace('-','').isalnum():
        ap.error('label must contain letters, numbers, hyphens or underscores only')
    for n in ['strength','halo_strength','gradient_strength']:
        x=getattr(args,n)
        if x is not None and not 0<=x<=1: ap.error(f'{n} must be in 0..1')
    args.out.mkdir(parents=True,exist_ok=True)
    src=Image.open(IN/'chinese_source.png').convert('RGBA')
    jp=Image.open(IN/'japanese.png').convert('RGBA'); base=fit_logo(src)
    params=calibrate(jp,base)
    (args.out/'calibration.json').write_text(json.dumps(params,indent=2,ensure_ascii=False))
    configs={'A':('轻调',.55,.35,0),'B':('均衡',.85,.8,.55),'C':('更贴近原版',1,1,1)}
    if args.strength is not None:
        configs={args.label:('自定参数',args.strength,args.halo_strength,args.gradient_strength)}
    items=[('日文原版 · 配色参照',jp),('中文原素材 · 未调整（同样量化）',quantize_for_template(base,256).convert('RGBA'))]
    reports={}; zmask=masks(base);jmask=masks(jp,True)
    reports['reference']={k:summarize(lab(np.array(jp)[...,:3]/255),m) for k,m in jmask.items()}
    reports['original']={k:summarize(lab(np.array(base)[...,:3]/255),m) for k,m in zmask.items()}
    for key,(name,s,h,g) in configs.items():
        full,meta=process(src,params,s,h,g); native=fit_logo(full)
        assert np.array_equal(np.array(native)[...,3],np.array(base)[...,3])
        full.save(args.out/f'{key}_source.png'); native.save(args.out/f'{key}_405x89.png')
        q=quantize_for_template(native,256)
        q.save(args.out/f'{key}_256.png')
        # The pipeline palette approximation is present in every menu preview.
        menu=compose_title_mock(q.convert('RGBA')).convert('RGB')
        menu.save(args.out/f'{key}_menu_preview.png')
        menu.resize((960,544),Image.Resampling.NEAREST).save(args.out/f'{key}_menu_preview_2x.png')
        items.append((f'{key} · {name}（已模拟 256 色量化）',q.convert('RGBA')))
        v=lab(np.array(native)[...,:3]/255)
        reports[key]={'parameters':{'strength':s,'halo_strength':h,'gradient_strength':g},'checks':meta,'measurements_on_fixed_source_masks':{k:summarize(v,m) for k,m in zmask.items()}}
        print(key,json.dumps(reports[key],ensure_ascii=False))
    make_sheet(items,args.out/'compare_on_background.png')
    make_sheet(items,args.out/'compare_on_white.png',white=True)
    (args.out/'report.json').write_text(json.dumps(reports,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
