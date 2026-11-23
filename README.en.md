# PromptFinderPro

[日本語](README.md) · [English](README.en.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md)

## Find the settings behind an AI-generated image

Search your local collection by prompt, checkpoint or LoRA. Start with a Japanese keyword, narrow the results by model, then copy the positive prompt from a promising image to try the idea again.

## Download and first scan

[Windows x64 ZIP · v1.1.2](https://github.com/sakusaku0214/PromptFinder/releases/download/v1.1.2/PromptFinderPro_v1.1.2_Windows_x64.zip) · [SHA256SUMS.txt](https://github.com/sakusaku0214/PromptFinder/releases/download/v1.1.2/SHA256SUMS.txt) · [GitHub Releases](https://github.com/sakusaku0214/PromptFinder/releases/latest)

Windows 10/11 (64-bit). Extract the portable ZIP into a writable folder and run `PromptFinderPro.exe`. Python is optional. Choose your image folder with **フォルダ選択**, then click **スキャン / 更新** to index it. Subsequent scans pick up changes.

## Compare search workflows

- digiKam organizes photos by date, location, people and tags, and can search within a visual similarity range. [digiKam](https://www.digikam.org/about/features/) · [Manual](https://docs.digikam.org/en/maintenance_tools/maintenance_duplicates.html)
- Diffusion Toolkit searches generated images by prompt, supports dragging thumbnails to WebUI or Explorer, and can search ComfyUI workflow data. [Diffusion Toolkit](https://github.com/RupertAvery/DiffusionToolkit/blob/master/Diffusion.Toolkit/Tips.md) · [Releases](https://github.com/RupertAvery/DiffusionToolkit/releases)
- **PromptFinderPro** — PromptFinderPro combines Japanese tag lookup, model and LoRA filters, and two ways to follow a promising image: compare prompt vocabulary or compare visual structure using dHash. Use exact duplicate search when cleaning up file copies.

## Search, review and reuse

Reads supported metadata from AUTOMATIC1111 / Forge, ComfyUI and NovelAI, including supported JPEG / WebP Exif UserComment data. Available fields depend on how the image was saved. Filter by rating, include negative prompts, or exclude terms with `blue_eyes -monochrome`. Japanese automatic translation may send search terms to Google.

Select a thumbnail to preview the image and copy its positive prompt, negative prompt or full generation parameters. Drag files to compatible apps. In the thumbnail list, keys `1`–`5` set a rating, `0` clears it and `Delete` prompts before moving files to the Recycle Bin.

## Clean up exact duplicates

Click **重複画像を検索（完全一致）**. The bar animates while candidates are gathered by file size, then shows files processed and percentage during SHA-256 verification. Re-encoded images can look identical and have different hashes.

Click **古い重複を一括選択** to select older copies while protecting one file per group using the latest modification time. **検索結果** counts images in the current list and **選択中** counts selected images. Review the selection, then use **選択した重複をゴミ箱へ** and confirm. The app rechecks the selected and retained files before the move.

## Verify and upgrade

Compare the PowerShell hash below with the published checksum. For an upgrade, close the app, keep the old folder and extract the new version separately. To keep ratings, the index and preferences, copy `ai_images_index_v2.db` and `config.json` into the new folder before launch.

```powershell
Get-FileHash .\PromptFinderPro_v1.1.2_Windows_x64.zip -Algorithm SHA256
```

## Run from source

Windows · Python 3.12

```powershell
python -m pip install PySide6 Pillow send2trash deep-translator pyinstaller
python prompt_finder_pro.py
```

EXE: `python -m PyInstaller --clean PromptFinderPro.spec`
