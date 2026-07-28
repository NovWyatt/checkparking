# Check Vehicle OCR

Tool desktop Python de import hang loat anh xe, nhan dien bien so bang OCR va xuat Excel.

## Chuc nang

- Import tung file anh hoac ca folder anh.
- Ho tro nhieu dinh dang anh thong qua Pillow: JPG, PNG, WEBP, BMP, TIFF, GIF, HEIC/HEIF/AVIF neu `pillow-heif` cai duoc.
- Co 5 engine:
  - `PaddleOCR Local`: engine mac dinh, chay local bang OpenCV + PaddleOCR, khong can API key va khong bi rate limit.
  - `Gemini Vision`: gui anh len Google Gemini de doc bien so bang model nhin anh tong quat.
  - `Plate Recognizer`: API chuyen doc bien so xe, mac dinh region `vn`, nen uu tien cho bai toan bai xe/nhieu xe.
  - `GPT Vision`: gui anh da resize/nen len OpenAI de doc bien so.
  - `Local OCR`: xu ly local bang OpenCV + Tesseract, dung khi khong co API key.
- `PaddleOCR Local` dung PP-OCRv5 mobile detection/recognition, phu hop chay mien phi tren may local; lan dau co the mat them thoi gian de Paddle tai/cache model.
- `PaddleOCR Local` co them ONNX license-plate detector `yolo-v9-t-384-license-plate-end2end` de tim dung box bien so truoc khi OCR; model nhe, chay CPU local, giup anh nhieu xe it sot bien hon ma khong phu thuoc API.
- Khi dung PaddleOCR, app tach cac dong OCR gan nhau thanh tung bien so rieng de mot anh co the tra ve nhieu bien so, dong thoi loc time mark/timestamp nhu `26 Thang 5, 2026`, ngay gio, watermark camera.
- Pipeline PaddleOCR uu tien toc do: `Nhanh` va `Can bang` uu tien luong Paddle nhe, chi dung ONNX khi can cuu anh fail; `Quet ky` moi bat ONNX ngay tu dau de bat nhieu xe hon.
- Anh fail nhung van net se tu chay rescue pass: doc lai khong che timestamp va quet them cac o focus de bat bien so nam lech goc, bi time mark che mot phan, hoac co nhieu xe trong anh.
- `GPT Vision` dung OpenAI Responses API voi model mac dinh `gpt-4.1` de nhanh va on dinh hon; app co retry/fallback model neu model chinh khong kha dung.
- `Gemini Vision` dung model mac dinh `gemini-2.5-flash`, ep JSON schema, gui anh goc kem crop nghi bien so, va fallback sang cac model Gemini khac neu model chinh khong kha dung.
- Khi dung Gemini, app tu gioi han toc do goi API de tranh rate-limit va se thu Local OCR fallback neu Gemini loi hoac khong doc duoc bien.
- Gemini loc ket qua theo cau truc bien so Viet Nam va danh dau can review khi anh mo, bien so bi che, nho, hoac ky tu con nghi ngo.
- GPT Vision gui anh goc kem it crop nghi bien so hon de giam thoi gian cho moi anh.
- OpenAI, Gemini va Plate Recognizer API key/token co the luu tren may bang Windows DPAPI, lan sau mo app khong can nhap lai.
- Tu dong tim vung nghi bien so bang OpenCV khi dung `Local OCR`.
- Quet song song nhieu anh de tang toc; co tuy chinh so luong thread trong giao dien.
- Co 2 luot detect va mot luot outline de bat them truong hop anh co nhieu xe/bien so.
- Bo qua cac vung giong timestamp o goc/tren/duoi anh va loc text giong ngay gio.
- OCR bang Tesseract, co tien xu ly anh nhieu kieu de tang kha nang doc bien so.
- Giao dien chinh gom danh sach tung anh, preview anh dang chon, va danh sach tat ca bien so cua anh do de tick/sua truc tiep.
- Sau khi quet xong co popup chon `Review bang anh`, `Xuat luon`, hoac `Cancel`.
- Review bang anh hien preview anh lon, cac bien so doc duoc, o sua va checkbox OK cho tung bien so.
- Giu dinh dang bien so co dau gach, khoang trang, dau cham neu OCR doc duoc, vi du `70-K1 247.11`.
- Do do mo cua anh va tach rieng anh/xe can kiem tra thu cong.
- Xuat Excel gom:
  - `Tong_quan`
  - `Theo_tung_anh`
  - `Bien_so_doc_duoc`
  - `Can_kiem_tra`
  - `Tat_ca_anh`
- Khi xuat tu app sau review, Excel co them `Review_tat_ca` va chi dua dong da Tick OK vao sheet `Bien_so_doc_duoc`.
- Excel nhung thumbnail anh truc tiep vao sheet, kem crop bien so neu Local OCR tao duoc crop.
- Luu crop bien so vao folder rieng de doi chieu nhanh.

## Cai dat de chay source

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## OCR engine

Mac dinh nen dung `PaddleOCR Local` neu muon quet mien phi va khong phu thuoc quota. Engine nay chay local nen khong can API key; lan dau co the tai model PaddleOCR vao cache cua Windows user.

Neu dung engine API, co the nhap truc tiep trong giao dien, tick `Luu key cho lan sau`, hoac set bien moi truong:

```powershell
$env:PLATE_RECOGNIZER_TOKEN="..."
$env:GEMINI_API_KEY="..."
$env:OPENAI_API_KEY="sk-..."
```

Khuyen nghi neu muon dung Gemini de doi chieu: chon `Gemini Vision`, dung model `gemini-2.5-flash`, nhap `GEMINI_API_KEY`, roi bam `Luu API keys`. Neu tai khoan da co quota/billing cho Pro, co the doi sang `gemini-2.5-pro`.

Neu can doi chieu them, co the thu `Plate Recognizer` cho bai toan bai xe/nhieu xe, `GPT Vision` neu ban da co OpenAI key, hoac `Local OCR`/Tesseract khi PaddleOCR gap anh kho.

Neu dung `Local OCR`, app can Tesseract OCR. App se tu tim theo thu tu:

1. Duong dan ban chon trong giao dien.
2. Bien moi truong `CHECK_VEHICLE_TESSERACT`.
3. Folder bundle canh file exe: `tesseract\tesseract.exe`.
4. Cac duong dan cai dat pho bien cua Tesseract tren Windows.
5. `tesseract.exe` trong PATH.

Ban nen dung ban Tesseract Windows cua UB Mannheim:

https://github.com/UB-Mannheim/tesseract/wiki

Neu muon installer Inno Setup bundle san Tesseract, cai Tesseract truoc roi chay:

```powershell
.\tools\prepare_tesseract_vendor.ps1
```

Script nay se copy folder Tesseract dang cai tren may vao `vendor\tesseract`.

## Build exe

```powershell
.\build_exe.ps1
```

File chạy mới chỉ nằm ở một chỗ:

```text
release\CheckVehicleOCR\CheckVehicleOCR.exe
```

Script build sẽ dọn các output cũ `dist`, `dist_release`, `build_release` để tránh nhầm bản exe cũ với bản mới.

## Build installer bang Inno Setup

Can cai Inno Setup 6 truoc. Neu lenh `iscc` chua co trong PATH, script se tu tim o `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`.

```powershell
.\build_installer.ps1
```

Installer se nam o:

```text
installer\Output\CheckVehicleOCR_Setup.exe
```

## Luu y do chinh xac

Day la OCR tu dong nen ket qua phu thuoc nhieu vao anh: goc chup, anh rung, bien so bi che, anh qua toi/sang, bien so nho trong khung hinh. Sheet `Can_kiem_tra` duoc tao rieng de gom anh mo, OCR thap tin cay, hoac khong tim thay bien so.
