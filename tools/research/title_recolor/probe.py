import sys, json, shutil, subprocess, hashlib, os
from pathlib import Path
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent
# 归档进仓库后按脚本位置推导仓库根（tools/research/title_recolor/ → parents[3]）；
# 原版这里是作者本机绝对路径，换机器或换 checkout 就失效。SNDL_REPO 可覆盖。
REPO=Path(os.environ.get('SNDL_REPO') or Path(__file__).resolve().parents[3])
sys.path.insert(0,str(REPO))
from tools.bake_finale_title import fit_logo, content_box, compose_title_mock
IN=ROOT/'inputs'
# ⚠ chinese_source/baked 指的是**调色前**的那一版，现在工作区里的同名文件已经是调色
# 成品，直接照这张表快照会二次处理。用 snapshot_inputs.py 从 git 取（已钉 sha256）。
paths={'japanese.png':'png/sysgim/title_01_a.png','chinese_source.png':'docs/finale/assets/title_01_c.src.png','chinese_baked.png':'docs/finale/assets/title_01_c.png','menu_bg.png':'png/bg/bg_4_a_0.png','previous_e2e.png':'build/emu/drives/title_logo/10_title_reboot.png'}

def lab(rgb):
    rgb=np.asarray(rgb,dtype=np.float64)
    c=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    lms=c@np.array([[.4122214708,.5363325363,.0514459929],[.2119034982,.6806995451,.1073969566],[.0883024619,.2817188376,.6299787005]]).T
    return np.cbrt(lms)@np.array([[.2104542553,.7936177850,-.0040720468],[1.9779984951,-2.4285922050,.4505937099],[.0259040371,.7827717662,-.8086757660]]).T

def rgb(lab):
    lms=(lab@np.array([[1,.3963377774,.2158037573],[1,-.1055613458,-.0638541728],[1,-.0894841775,-1.2914855480]]).T)**3
    c=lms@np.array([[4.0767416621,-3.3077115913,.2309699292],[-1.2684380046,2.6097574011,-.3413193965],[-.0041960863,-.7034186147,1.7076147010]]).T
    return np.where(c<=.0031308,12.92*c,1.055*np.maximum(c,0)**(1/2.4)-.055)

def stats(im,title):
    a=np.asarray(im.convert('RGBA'))/255
    c=a[...,:3]; L=lab(c); H=np.mod(np.degrees(np.arctan2(L[...,2],L[...,1])),360)
    y=np.arange(a.shape[0])[:,None]
    zones={'main':y<a.shape[0]*.57,'subtitle':y>a.shape[0]*.65}
    print(title,im.size,content_box(im))
    for k,zone in zones.items():
        mask=zone&(a[...,3]>.95)&(c[...,2]-c[...,0]>.075)&(L[...,0]<.65)
        p=c[mask]; lp=L[mask]; h=H[mask]
        print(k,'n=',len(p),'rgb med',np.round(np.median(p,axis=0)*255,1),'L10/50/90',np.round(np.quantile(lp[:,0],[.1,.5,.9]),3),'C median',round(float(np.median(np.linalg.norm(lp[:,1:],axis=1))),4),'h median',round(float(np.median(h)),2))
        colors,count=np.unique((p*255).round().astype('uint8'),axis=0,return_counts=True)
        ids=np.argsort(count)[-10:][::-1]
        print('top colors',list(zip(colors[ids].tolist(),count[ids].tolist())))
    return a

if __name__=='__main__':
    jp=Image.open(IN/'japanese.png').convert('RGBA'); src=Image.open(IN/'chinese_source.png').convert('RGBA'); zh=fit_logo(src)
    assert np.array_equal(np.asarray(zh), np.asarray(Image.open(IN/'chinese_baked.png').convert('RGBA')))
    stats(jp,'JP'); stats(src,'ZH source'); stats(zh,'ZH native')
    sheet=Image.new('RGB',(1215,750),(245,245,245)); draw=ImageDraw.Draw(sheet); font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',22)
    for i,(name,im) in enumerate([('Japanese reference',jp),('Chinese latest (unchanged)',zh)]):
        draw.text((12,375*i+8),name,font=font,fill=(20,20,20))
        white=Image.new('RGBA',im.size,'white');white.alpha_composite(im)
        sheet.paste(white.convert('RGB').resize((1215,267),Image.Resampling.NEAREST),(0,375*i+42))
        bg=Image.open(IN/'menu_bg.png').convert('RGBA').crop((38,10,443,99)); bg.alpha_composite(im)
        # separate large background proof
        bg.convert('RGB').resize((1215,267),Image.Resampling.NEAREST).save(ROOT/f'{i}_on_bg_3x.png')
    sheet.save(ROOT/'diagnostic_white_3x.png')
