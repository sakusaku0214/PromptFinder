# PromptFinderPro

[日本語](README.md) · [English](README.en.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md)

## AI 생성 이미지의 생성 설정을 다시 찾기

로컬에 저장한 이미지를 프롬프트, 모델, LoRA로 검색할 수 있습니다. 일본어 키워드로 후보를 찾고 모델로 좁힌 다음, 마음에 드는 이미지의 포지티브 프롬프트를 복사해 다시 활용하세요.

## 다운로드 및 첫 스캔

[Windows x64 ZIP · v1.1.3](https://github.com/sakusaku0214/PromptFinder/releases/download/v1.1.3/PromptFinderPro_v1.1.3_Windows_x64.zip) · [SHA256SUMS.txt](https://github.com/sakusaku0214/PromptFinder/releases/download/v1.1.3/SHA256SUMS.txt) · [GitHub Releases](https://github.com/sakusaku0214/PromptFinder/releases/latest)

Windows 10/11 64비트용 포터블 버전입니다. ZIP을 쓰기 가능한 폴더에 풀고 `PromptFinderPro.exe`를 실행하세요. Python 설치는 필요 없습니다. **フォルダ選択**에서 이미지 폴더를 고른 다음 **スキャン / 更新**을 누르세요. 이후에는 변경된 파일을 기준으로 인덱스를 갱신합니다.

썸네일을 하나 이상 선택하고 오른쪽 클릭 메뉴에서 **画像ファイルをコピー**(파일 복사) 또는 **画像ファイルを切り取り**(파일 잘라내기)를 선택한 뒤 탐색기 폴더에 붙여넣으세요. 잘라낸 원본은 붙여넣을 때 이동합니다. 드래그는 기본적으로 복사하며 이동을 지원하는 대상에서는 Shift를 누른 채 이동할 수 있습니다.

## 이미지 관리 도구별 활용 방식

- digiKam은 날짜, 위치, 인물, 태그로 사진을 정리하고 시각적 유사도 범위를 지정해 이미지를 찾을 수 있습니다. [digiKam](https://www.digikam.org/about/features/) · [Manual](https://docs.digikam.org/en/maintenance_tools/maintenance_duplicates.html)
- Diffusion Toolkit은 프롬프트 검색, WebUI나 탐색기로 썸네일 드래그, ComfyUI 워크플로 데이터 검색을 지원합니다. [Diffusion Toolkit](https://github.com/RupertAvery/DiffusionToolkit/blob/master/Diffusion.Toolkit/Tips.md) · [Releases](https://github.com/RupertAvery/DiffusionToolkit/releases)
- **PromptFinderPro** — PromptFinderPro에서는 일본어 태그와 모델·LoRA로 후보를 좁힌 뒤, 한 이미지를 기준으로 프롬프트 어휘가 비슷한 결과와 구도가 비슷한 결과(dHash)를 각각 살펴볼 수 있습니다. 파일 복사본 정리에는 완전 일치 검색을 사용합니다.

## 검색과 재사용

AUTOMATIC1111 / Forge, ComfyUI, NovelAI의 생성 메타데이터와 지원되는 JPEG / WebP의 Exif UserComment를 읽습니다. 저장 방식에 따라 추출되는 항목이 달라집니다. 평점으로 필터링하거나 네거티브 프롬프트를 검색에 포함할 수 있습니다. `blue_eyes -monochrome`처럼 제외할 단어도 지정할 수 있습니다. 일본어 자동 번역 시 검색어가 Google로 전송될 수 있습니다.

썸네일을 선택하면 미리보기와 생성 설정을 확인하고 포지티브·네거티브 프롬프트 또는 전체 설정을 복사할 수 있습니다. 파일을 호환 앱으로 드래그할 수도 있습니다. 목록에서 `1`~`5`는 평점 지정, `0`은 평점 해제, `Delete`는 확인 후 휴지통으로 이동하는 키입니다.

## 완전히 일치하는 복사본 정리

**重複画像を検索（完全一致）**를 누르세요. 파일 크기로 후보를 찾는 동안 진행 막대가 움직이고, SHA-256 대조가 시작되면 처리한 파일 수와 진행률이 표시됩니다. 재압축한 이미지는 겉보기에 같아도 해시가 달라질 수 있습니다.

**古い重複を一括選択**을 누르면 그룹마다 최종 수정 시간이 가장 최근인 파일 하나를 보호하고 나머지를 선택합니다. **検索結果**는 현재 목록의 이미지 수, **選択中**은 선택한 이미지 수입니다. 대상을 검토하고 **選択した重複をゴミ箱へ**를 눌러 확인하세요. 이동하기 전에 보관할 파일과 이동할 파일의 내용을 다시 검사합니다.

## 무결성 확인 및 업데이트

아래 PowerShell 명령의 결과를 공개된 체크섬과 비교하세요. 업데이트할 때는 앱을 종료하고 기존 폴더를 보관한 뒤 새 버전을 별도 폴더에 푸세요. 평점, 인덱스, 설정을 이어 쓰려면 첫 실행 전에 `ai_images_index_v2.db`와 `config.json`을 새 폴더에 복사하세요.

```powershell
Get-FileHash .\PromptFinderPro_v1.1.3_Windows_x64.zip -Algorithm SHA256
```

## 소스에서 실행

Windows · Python 3.12

```powershell
python -m pip install PySide6 Pillow send2trash deep-translator pyinstaller
python prompt_finder_pro.py
```

EXE: `python -m PyInstaller --clean PromptFinderPro.spec`
