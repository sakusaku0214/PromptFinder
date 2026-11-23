# PromptFinderPro

[日本語](README.md) · [English](README.en.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md)

## 找回 AI 生成图片背后的参数

按提示词、模型或 LoRA 搜索本地图片。可以先用日语关键词寻找候选图片，再按模型筛选，最后复制喜欢的图片的正面提示词，用于下一次生成。

## 下载与首次扫描

[Windows x64 ZIP · v1.3.0](https://github.com/sakusaku0214/PromptFinder/releases/download/v1.3.0/PromptFinderPro_v1.3.0_Windows_x64.zip) · [SHA256SUMS.txt](https://github.com/sakusaku0214/PromptFinder/releases/download/v1.3.0/SHA256SUMS.txt) · [GitHub Releases](https://github.com/sakusaku0214/PromptFinder/releases/latest)

适用于 64 位 Windows 10/11。将便携版 ZIP 解压到可写文件夹，运行 `PromptFinderPro.exe`，无需安装 Python。点击 **フォルダ選択** 选择图片文件夹，再点击 **スキャン / 更新** 建立索引。后续扫描会增量更新。

选中一张或多张缩略图，右键选择 **画像ファイルをコピー**（复制文件）或 **画像ファイルを切り取り**（剪切文件），然后在资源管理器的目标文件夹中粘贴。剪切的文件会在粘贴时移动。拖动默认复制，按住 Shift 可移至支持移动的目标。

## 如何选择图片管理工具

- digiKam 支持按日期、地点、人物和标签整理照片，还可以指定视觉相似度范围来查找图片。 [digiKam](https://www.digikam.org/about/features/) · [Manual](https://docs.digikam.org/en/maintenance_tools/maintenance_duplicates.html)
- Diffusion Toolkit 支持按提示词搜索、将缩略图拖到 WebUI 或资源管理器，以及搜索 ComfyUI 工作流数据。 [Diffusion Toolkit](https://github.com/RupertAvery/DiffusionToolkit/blob/master/Diffusion.Toolkit/Tips.md) · [Releases](https://github.com/RupertAvery/DiffusionToolkit/releases)
- **PromptFinderPro** — PromptFinderPro 把日语标签、模型和 LoRA 筛选与两种相似搜索结合起来。选中一张图，既可以找提示词用词接近的作品，也可以通过 dHash 找构图接近的图片。整理文件副本时，可以单独使用完全匹配搜索。

## 搜索、筛选与复用

可读取 AUTOMATIC1111 / Forge、ComfyUI、NovelAI 的生成元数据，以及部分 JPEG / WebP 的 Exif UserComment。能提取哪些字段取决于图片的保存方式。可按评分筛选、将负面提示词纳入搜索，或用 `blue_eyes -monochrome` 排除关键词。自动翻译日语时，搜索词可能会发送到 Google。

选择缩略图即可预览图片，复制正面提示词、负面提示词或全部生成参数，也可将文件拖到兼容的应用中。在列表中按 `1` 至 `5` 设置评分，按 `0` 清除评分，按 `Delete` 并确认后将文件移入回收站。

## 整理完全相同的副本

点击 **重複画像を検索（完全一致）**。按文件大小查找候选时，进度条会滚动；开始核对 SHA-256 后，会显示已处理数量和百分比。图片重新压缩后，即使看起来一样，哈希值也可能不同。

点击 **古い重複を一括選択**，每组保留最后修改时间最新的一份，并选中其余副本。**検索結果** 表示当前列表中的图片数，**選択中** 表示已选数量。检查后点击 **選択した重複をゴミ箱へ** 并确认。移动前，程序会重新核对所选文件和保留文件的内容。

## 校验与升级

将下方 PowerShell 命令输出的哈希值与发布的校验值进行比较。升级时请先退出应用，保留旧文件夹，并将新版本解压到另一文件夹。要沿用评分、索引和设置，请在首次启动前将 `ai_images_index_v2.db` 和 `config.json` 复制到新文件夹。

```powershell
Get-FileHash .\PromptFinderPro_v1.3.0_Windows_x64.zip -Algorithm SHA256
```

## 从源码运行

Windows · Python 3.12

```powershell
python -m pip install PySide6 Pillow send2trash deep-translator pyinstaller
python prompt_finder_pro.py
```

EXE: `python -m PyInstaller --clean PromptFinderPro.spec`

## v1.2.0 更新内容

外部翻译默认关闭。启用 Google 选项后，可在搜索时翻译词典以外的日语词语。重复选择文件夹即可添加多个目录。缩略图会缓存在本地磁盘。欢迎非商业用途的修改和免费分享，详见[许可证](LICENSE)。

## v1.3.0

运行期间约每 60 秒扫描已注册的文件夹。支持普通图片、同名 .txt、NovelAI 隐写 PNG 和包含 ComfyUI 图数据的 JPEG。重复搜索会复用已保存的 SHA-256。

## main 更新（尚未包含在发布 ZIP 中）

自动扫描后保留滚动位置和选择。如果顶部图片被删除，会使用附近图片恢复位置。自动扫描期间保留相似及重复搜索视图。删除确认期间固定原文件路径，确认后再次核对重复文件。关闭应用时等待后台任务完成。

已在 Windows 验证实际 60 秒监视、滚动位置和两张图片的选择保持、顶部图片删除、确认期间列表重排和文件变化，以及后台处理期间关闭应用。

监视在应用运行期间约每 60 秒进行一次。缩小解码的效果取决于图片格式。缓存目前没有总容量限制。相似提示词搜索使用最多 3,000 个候选项。元数据支持取决于嵌入格式。
