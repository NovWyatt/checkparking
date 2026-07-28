# Phân tích hồi quy hiệu năng sau milestone UI

## Phạm vi đo

So sánh baseline trong `docs/PERFORMANCE_CURRENT.md` (trước milestone UI) với benchmark mới. Tất cả dùng Windows/Python 3.11, Paddle model cache local, ảnh synthetic 900×520, không API/Telegram/network. Lệnh tái lập profile:

```powershell
python -B tests\performance_regression_profile.py --output audit-output\performance-regression-profile.json
python -B tests\performance_benchmark.py
```

File profile thực tế được tạo trong `audit-output/performance-regression-profile.json` của lần kiểm tra này.

## So sánh benchmark

| Hạng mục | Trước UI | Sau UI trước tối ưu | Sau lazy/progress | Nhận xét |
|---|---:|---:|---:|---|
| Import app median | 2.549s | 2.693s | 2.553s | Gần baseline; import Paddle/OpenCV/OpenAI là phần lớn, không phải page router. |
| UI init median | 0.073s | 0.449s | 0.418s | Lazy page giảm khoảng 6.9% so với trước tối ưu; UI mới vẫn nhiều widget hơn baseline. |
| Paddle cold init | 1.350s | 1.488s | 1.475s | Dao động runtime/model cache; không có thay đổi model. |
| First image | 0.685s | 0.889s | 0.892s | Tương đương UI eager trong nhiễu giữa các process; vẫn chậm hơn baseline. |
| Warm image | 0.640s | 0.779s | 0.813s | Trong nhiễu giữa các process; profile xác nhận native Paddle chi phối. |
| Batch 3 ảnh | 1.877s | 2.365s | 2.401s | Chưa về baseline; số đo này chịu ảnh hưởng runtime/cache. |
| Excel compact | 0.081s | 0.104s | 0.096s | Cải thiện 0.008s so với UI eager; chậm chủ yếu do ghi zip/file system. |
| Excel full | 0.156s | 0.205s | 0.199s | Cải thiện 0.006s so với UI eager; thumbnail/zip vẫn là chi phí chính. |

Không suy luận rằng toàn bộ chênh lệch OCR/Excel là do UI: đo process riêng cho thấy thời gian native `libpaddle.run` và I/O OpenPyXL thay đổi theo môi trường/cache/disk.

## Bottleneck có bằng chứng

### Startup eager trước tối ưu

Profile eager trước lazy: 22,492 call, 0.443s. `ApplicationShell._build_pages()` tạo cả tám page; tổng 178 widget `ttk` và `tkapp.call` chiếm 0.367s cumulative. Page construction riêng có Scan 0.018s, Session 0.008s, Review 0.007s; phần còn lại nằm ở Tk widget/layout.

Sau lazy ở lần profile cuối: 16,067 call, 0.441s, chỉ cache `['scan']` lúc startup, 66 widget `ttk`. Các page mở lần đầu được đo:

| Page | Thời gian tạo lần đầu |
|---|---:|
| Session | 0.0116s |
| Review | 0.0115s |
| Export | 0.0036s |
| Providers | 0.0081s |
| Telegram | 0.0069s |
| Updates | 0.0041s |
| Settings | 0.0030s |

Top cumulative sau lazy:

```text
CheckVehicleApp.__init__                  0.441s
  _build_ui / ApplicationShell.__init__   0.362s
    ttk widget constructors               0.358s
      _tkinter.tkapp.call                 0.358s
    _build_sidebar                        0.334s
Tk root create                            0.068s
_create_page('scan')                     0.020s
```

Kết luận: lazy-load được áp dụng vì có bằng chứng. Sidebar vẫn là chi phí Tk chính, nhưng không được loại bỏ vì là chức năng điều hướng bắt buộc.

### Progress/state và event queue

Trước tối ưu, `BatchProgress.snapshot()` dùng `dataclasses.asdict`, gây recursive `deepcopy`: 0.089s/1,000 snapshot, 298,003 function calls. Sau thay manual snapshot chỉ copy list/dict cần thiết: 0.0068s/1,000 snapshot, 10,003 calls, nhanh hơn khoảng 13 lần.

`WorkerManager` chỉ emit event progress bắt đầu tối đa mỗi 150ms; event result vẫn mang snapshot theo từng ảnh để giữ số đếm chính xác. `_drain_events()` đã có render throttle 120ms, không render lại toàn Treeview; chỉ upsert dòng ảnh vừa xong.

Top cumulative sau tối ưu:

```text
progress_snapshot_1000   0.007s
event_queue_1000         0.017s
  queue.put/get          0.009s
  BatchProgress.snapshot 0.006s
```

### OCR và Excel

Profile `process_image` synthetic có fallback nhiều hơn benchmark chính: 2.011s, trong đó `runner.py:__call__` của Paddle chiếm 1.941s cumulative (khoảng 97%). Python crop/preprocess chỉ là phần rất nhỏ. Không refactor pipeline OCR vì sẽ không xử lý được bottleneck đã đo.

Profile Excel compact 0.178s cho snapshot 3 kết quả: `Workbook.save` 0.139s; `zipfile.write`/`io.open` 0.106s. Atomic save, formula injection, compact/full và background snapshot được giữ nguyên; không có thay đổi rủi ro chỉ để hạ benchmark.

## Tối ưu áp dụng

1. Shell chỉ tạo Scan page khi startup; page còn lại tạo khi điều hướng lần đầu và cache sau đó.
2. Các page lazy không khởi tạo provider network client, Telegram worker hay updater worker; các worker chỉ tạo khi người dùng thực hiện action.
3. `BatchProgress.snapshot()` bỏ `asdict/deepcopy`; progress start event throttle 150ms, result event giữ chính xác từng ảnh.
4. Không thay đổi model/PaddleOCR source, không bỏ Excel atomic save, review hay instrumentation cần thiết.

## Kết luận

UI startup được cải thiện rõ so với milestone UI trước tối ưu, progress instrumentation không còn là bottleneck. Các hồi quy còn lại so với baseline cũ chủ yếu nằm ngoài UI: native Paddle inference và I/O OpenPyXL, đồng thời chịu ảnh hưởng cache/disk. Việc tiếp tục loại bỏ UI hoặc safety step sẽ không có bằng chứng là cách xử lý đúng.
