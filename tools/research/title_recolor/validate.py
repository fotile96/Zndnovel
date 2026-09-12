import sys,json,hashlib
sys.dont_write_bytecode=True
from pathlib import Path
import numpy as np
from PIL import Image
from probe import ROOT,REPO,IN,lab,rgb
import recolor_title as rc
from tools.gimcodec import Gim
p=ROOT/'round2'; template=Gim((REPO/'build/databin/sysgim/title_01_a.gim').read_bytes())
src=np.array(Image.open(IN/'chinese_source.png').convert('RGBA')); base=np.array(Image.open(IN/'chinese_baked.png').convert('RGBA'))
report={}
for key in 'ABC':
 full=np.array(Image.open(p/f'{key}_source.png').convert('RGBA')); native=np.array(Image.open(p/f'{key}_405x89.png').convert('RGBA'))
 indexed=rc.quantize_for_template(Image.open(p/f'{key}_405x89.png').convert('RGBA'),256)
 assert np.array_equal(np.array(indexed.convert('RGBA')),np.array(Image.open(p/f'{key}_256.png').convert('RGBA')))
 raw=template.encode_from_pil(indexed); (p/f'{key}_title_01_c.gim').write_bytes(raw)
 decoded=Gim(raw).to_pil().convert('RGBA'); decoded.save(p/f'{key}_gim_decoded.png')
 q=np.array(decoded)
 assert np.array_equal(q,np.array(indexed.convert('RGBA')))
 assert np.array_equal(full[...,3],src[...,3])
 assert np.array_equal(native[...,3],base[...,3])
 # Existing 256-colour quantizer may modify alpha. Report that separately.
 report[key]={'source_alpha_identical':bool(np.array_equal(full[...,3],src[...,3])),'native_alpha_identical':bool(np.array_equal(native[...,3],base[...,3])),'transparent_source_rgba_identical':bool(np.array_equal(full[src[...,3]==0],src[src[...,3]==0])),'gim_rgba_matches_indexed_png':True,'gim_bytes':len(raw),'native_size':[native.shape[1],native.shape[0]],'quantizer_alpha_mae':float(np.abs(q[...,3].astype(float)-native[...,3]).mean()),'sha256_rgba_png':hashlib.sha256((p/f'{key}_405x89.png').read_bytes()).hexdigest()}
# Nontrivial numerical invariant for the color-space implementation.
x=np.random.default_rng(34).uniform(0,1,(20000,3)); maxerr=float(np.abs(rgb(lab(x))-x).max()); assert maxerr<2e-6
report['Oklab_RGB_roundtrip_max_error']=maxerr
fullim=Image.open(IN/'chinese_source.png').convert('RGBA')
params=rc.calibrate(Image.open(IN/'japanese.png').convert('RGBA'),rc.fit_logo(fullim))
identity,meta=rc.process(fullim,params,0,0,0)
assert np.array_equal(np.array(identity),src)
report['zero_strength_identity']=True
out, meta=rc.process(fullim,params,1,1,1)
report['C_gamut']=meta
assert meta['gamut_clipped_pixels']==0
# Matrices are approximate: output clipping tolerance stays far below an 8-bit step.
report['round1_to_round2_C_mean_abs_rgb_difference']=float(np.abs(np.array(Image.open(ROOT/'round1/C_405x89.png')).astype(float)[...,:3]-np.array(out.resize((405,89))).astype(float)[...,:3]).mean()) if False else 'see source comparison separately'
(p/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
