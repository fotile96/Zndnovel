# TTF→PGF 字体转换调研（2026-08-31）

结论：**走 tpunix/pgftool 的 `ttf_pgf`（小补丁参数化）+ 自研 Python PGF 解析器做 QA**，
全链路已在本机试产验证通过。本文记录原字体档案、工具评估、试产证据与遗留风险。

## 原字体档案（assets/DATA.BIN → pgf/，本次实测）

| | tsukuminpro_e_17.pgf | tsukuminpro_e_09.pgf |
|---|---|---|
| 用途 | 正文（fontLoad 槽 0 原配） | ruby 注音/小字（槽 1） |
| 字面 | FOT-TsukuMin Pro E（筑紫明朝）Regular | 同左 |
| 规格 | PGF rev2/ver6、4bpp、17px em @72dpi | 同左、9px em |
| 字形数 | 7480（charmap U+0020..U+FFE5，bpe13，缺字=8191） | 同左 |
| ascender/descender | 14.95 / −2.05 px | 7.91 / −1.09 px |
| 阴影表 | 无（shadowMapLength=0） | 同左 |

关键探针：假名/JIS 汉字/全角拉丁/`≪■【→` 均有；**简体（记/忆）与全部拼音声调
元音（āáǎà…ǖǘǚǜ）缺字**——拼音 ruby 必须靠新字体自带，原字体无从谈起。

## 工具评估

- **tpunix/pgftool**（C，tpu/掉线作，中文 PSP 汉化圈实战出身）：`ttf_pgf` 用
  FreeType 渲染 TTF→PGF rev2/ver6/4bpp/无阴影——**与本作原字体规格完全同型**；
  `dump_pgf` 可反查。`save_pgf.c` 处理全部难点（charmap/charptr 位打包、
  dim/bearing/advance 表、4bpp RLE、列主序）。缺点：尺寸 18px、128dpi、
  ascender 写死——已做 3 处小补丁参数化（见文末 diff）。macOS 上
  `cc -I/opt/homebrew/opt/freetype/include/freetype2 -I. -O2 -o ttf_pgf
  save_pgf.c libpgf.c ttfont_znd.c -L/opt/homebrew/opt/freetype/lib -lfreetype -lz`
  一次通过。
- PSP-Archive/ttf2pgf（skylark，2005，GPL2）：alpha 品质、约 17px advance 上限、
  Windows 向；仅作参考不采用。
- GimConv 类比方案（官方工具）不存在于字体侧；PGF 权威结构参照 PPSSPP
  `Core/Font/PGF.h`（本文头部字段偏移均按其核对：表长度字段在 +258，
  charmap 前还有 dim/xadj/yadj/adv 四表各 len×8 字节）。

## 试产证据（build/_font_trial/，gitignored）

用 `third_party/LXGWWenKai-Regular.ttf` 生成 17px/9px 两份（各 <1s）：

- 结构：rev2/ver6/4bpp/72dpi/尺寸字段与原字体同型；43478 字形（全字库，
  17px 5.3MB / 9px 2.4MB；正式版按语料裁剪 ucs 清单，预期 ~2MB/17px）。
- 探针：记/忆/ā/ǎ/é/ü/ǜ/漢/あ/Ｔ/。/≪/■/【/→ 全部命中（两个尺寸皆然）。
- 位图级：自研 Python 解码器（charptr→字形记录 14/7/7/7/7/6bit + 表索引
  + 4bpp RLE + 转置）同时解原字体与生成字体渲染并排目检——原 17px 明朝
  清晰（证解码器正确），LXGW 17px 简体工整，**9px 全套声调元音成形可辨**。
- 量度：「永」17px adv=17.0、9px adv=9.0，与原字体一致；top/left 偏差 ≤1px。

## 生产管线（待工具化）

1. ucs 清单：翻译语料全字集 ∪ ASCII ∪ 全角形 ∪ CJK 标点 ∪ 假名 ∪ 拼音声调
   元音 ∪ 游戏控制符（≪≧【】○■←→ 等），每行一个十六进制码位。
2. `ttf_pgf LXGWWenKai-Regular.ttf out.pgf ucs.txt 17`（及 9）。
3. QA：Python 解析器核对头部/探针/样字渲染。
4. `databin.py pack` 注入（manifest 追加 `pgf/LXGWWenKai-Regular.pgf`；
   槽 1 小字体名称与 lua `fontLoad(1, …)` 的改法一并定）。
5. PPSSPP 实机目检（另项调研已铺路）。

## 遗留风险

- 头部 ascender/descender 与原字体不同（16/−5 vs 14.95/−2.05）：引擎 stub 若用
  它排版，基线可能偏移——PPSSPP 实测定夺，必要时后补丁头部对齐原值。
- 9px 声调符号在实机 1:1 像素下的辨识度需目检（预览 6× 下可辨）。
- LXGW WenKai 笔画偏细（vs 原明朝 E=Extra bold 级）；若观感淡，可换
  LXGW WenKai Bold/GB 或其他开源字体再产（管线不变）。
- charmap bpe 由 13→16（字形数 43478 所致）：PGF 格式合法（bpe 是头部自描述
  字段），裁剪字库后自然回落。

## ttfont.c 补丁（/tmp/pgftool/ttfont_znd.c，共 3 处）

```diff
- if(argc<3){ printf("Usage: ttf_pgf {xxx.ttf} {out.pgf} [unicode list]\n");
+ if(argc<3){ printf("Usage: ttf_pgf {xxx.ttf} {out.pgf} [unicode list] [pixel_size]\n");

- /* 18x18 TrueType */
- face = TTF_Init(argv[1], 18, 18);
+ int px = (argc>4) ? atoi(argv[4]) : 17;
+ face = TTF_Init(argv[1], px, px);

- h_res = 128;
- pgft->ph->h_res = h_res<<6; pgft->ph->v_res = h_res<<6;
- pgft->ph->h_size = (h_size<<6)*72/h_res; pgft->ph->v_size = (h_size<<6)*72/h_res;
- pgft->ph->ascender = 0x000003f5; pgft->ph->descender = 0xffffff75;
+ h_res = 72;
+ pgft->ph->h_res = h_res<<6; pgft->ph->v_res = h_res<<6;
+ pgft->ph->h_size = h_size<<6; pgft->ph->v_size = h_size<<6;
+ pgft->ph->ascender = mt->ascender; pgft->ph->descender = mt->descender;
```
