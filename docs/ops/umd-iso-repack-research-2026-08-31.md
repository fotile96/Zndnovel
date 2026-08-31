# PSP UMD ISO 重打包注意事项调研（2026-08-31）

结论：**不做全量重建，走「就地替换 DATA.BIN」路线**（CUE UMD-replace 算法，
Python 重写进 tools/），实在要重建才用 mkisofs 配方 + 严格核验。本文记录
"UltraISO 产物实机不可用"的机理、两条路线的做法与验证矩阵。

## 为什么 PPSSPP 不挑、实机挑

- **PPSSPP**（本机 `~/ppsspp/Core/FileSystems/ISOFileSystem.cpp` 实读）：挂载时从
  PVD 取根目录记录，**递归走目录记录树，完全不读 path table**；对文件名匹配
  也宽容。所以结构半坏的 ISO 在模拟器里一切正常。
- **实机 CFW**：Inferno/M33 驱动只负责把 ISO/CSO 当块设备**喂原始扇区**
  （ARK-4 `core/inferno/isoread.c` 实读：只认 CSO/ZSO/DAX/JSO 魔数，不碰
  ISO9660），**真正解析文件系统的是 Sony 固件的 isofs**——它按规范读
  PVD + path table 定位目录，对主卷里的名字、表结构一致性远比 PPSSPP 敏感。
- 所以判据是"固件视角的 ISO9660 合法性"，PPSSPP 通过≠实机通过。

## UltraISO 类通用工具的典型破坏点

1. **改名进 Joliet**：真实文件名放进 Joliet 补充卷，主卷（PVD）里的名字被
   8.3 大写化/加 `~` 改名。固件只读主卷 → 小写/长名文件（本作 ISO 层可能有
   `movie/op.mp4` 这类小写路径，待 ISO 到手核验）直接找不到 → 黑屏。
2. **path table 与目录记录不一致**（或重排后没同步）：PPSSPP 不用它所以无感，
   固件用它所以致命。
3. **重排 LBA / 去 padding**：索引（卷描述符、path table、目录表）按 LBA 指位，
   工具重排后对"按绝对 LBA 直读"的游戏致命；UMDGen 的 filelist.txt 强制 LBA
   的功能就是为这类游戏留的。
4. 附加 UDF/引导等多余描述符、丢 `;1` 版本号、动系统区（LBA 0–15）。

## 首选：就地替换（UMD-replace 算法）

只有 `PSP_GAME/USRDIR/DATA.BIN`（路径待核）需要更新，最小侵入 = 最大稳妥。
算法（已通读 UMDReplaceK 源码确认，源自 CUE UMD-replace 20150303）：

1. 从 PVD（LBA16；根目录记录在 +0x9C，总扇区数在 +0x50）沿目录树找到目标
   文件的目录记录（LBA@+2 / 大小@+10，双端序各存一份）；
2. 新内容按 2048 对齐就地写入；**尺寸变化时把 ISO 尾部整体平移**，然后
   更新三处引用：PVD 总扇区数、至多 4 份 path table（L/M 及备份）中
   LBA > 插入点的目录项、全目录树中 LBA > 插入点的记录；
3. ISO9660 里只有这三类结构引用扇区号，平移是闭合安全的。

优点：其余每个字节保持不变（可 diff 验证"只改了该改的"）；文件名大小写、
path table、系统区、UMD_DATA.BIN 全部原样。残余风险仅"游戏对 DATA.BIN
**之后**的文件按绝对 LBA 直读"——本作资源几乎全在 DATA.BIN 内，ISO 层
剩 EBOOT/movie 等寥寥数个，风险极低；若想归零，可把 DATA.BIN 挪到 ISO
末尾（UMDGen 同款策略）或吃原盘 dummy padding 的空间。

计划工具化为 `tools/umdiso.py`：`replace`（就地替换，支持变大）+
`verify`（PVD/path table/目录树三方一致性 + 与原盘的差异区间报告）+
`list`。纯 stdlib，约 200 行；对照物有 UMDReplaceK（GPL，不抄码，按格式
知识清写）。

## 备选：全量重建（mkisofs）

真实 PSP 英化项目（R11）实战配方：

```sh
mkisofs -iso-level 4 -xa -A "PSP GAME" -V "<卷标从原盘抄>" -sysid "PSP GAME" \
  -volset "" -p "" -publisher "" -o out.iso extracted/
```

注意：`-iso-level 4` 保留小写与长名于主卷；**不加 `-J`（Joliet）不加 `-R`
（RockRidge）**；`;1` 版本号 mkisofs 默认保留；卷标/系统 ID 按原盘 PVD 抄写；
重建后必须核验（见下）。GUI 兜底是 UMDGen 4.00（Windows/wine，汉化圈标准，
filelist.txt 可锁 LBA）。macOS 可用 `brew install cdrtools`（mkisofs）或
`xorriso -as mkisofs`。

## 验证矩阵（从宽到严）

1. 自研 verify：解析 PVD/path table/目录树三方互证 + 与原盘逐字节 diff 的
   区间清单（期望只有 DATA.BIN 数据区 + 三类索引结构变动）；
2. PPSSPP 冒烟（宽容裁判）：能开机进主菜单、读到改后资源；
3. 实机 CFW（严格裁判）：ARK-4/Inferno 挂载实测——这一步才算过。

## 待办与依赖

- **需要原版 ISO**（本机现只有 assets/DATA.BIN）：做 PVD/文件表基线、
  确认 DATA.BIN 的 ISO 内路径与其后文件布局、就地替换的底盘。
- ISO < 4GB（本作 ~1.x GB）无 FAT32 拆分问题；CSO 压缩（Inferno 支持）
  与本地化无关，先不做。
