# Worklog

## 2026-11-03 08:31 Asia/Bangkok — PLAN S2 hoàn tất nội dung

- Chủ repo nhắc hoàn tất nhanh PLAN chi tiết FE/BE chung Markdown, phân quyền ba role, demo đúng hai bàn và account/demo TXT; chỉ PLAN trong lượt này.
- Đọc agent.md, PROJECT/HANDOFF/WORKLOG, plans README/template/feature template, index và playbook PLAN/system/feature/frontend/backend/flow/testing/CI/chart; skills git-workflow, security-review, verification-loop, agent-self-evaluation. Repo sạch ban đầu, nhánh codex/taporder-plan, origin giữ nguyên; chưa manifests/tests/CI app.
- Bổ sung PLAN-2 mục9–17: F01–F12/algorithms/errors/locks, API inventory/examples/schema policy, FE routes/cache/mock/a11y, BE modules/transactions, sequence, task graph/ownership/worktrees, T01–T16/CI gates, demo và yêu cầu bất ngờ. Thống nhất routes, can_cancel, expected visit race; seed đúng bàn1/3 thay 5 bàn.
- Đọc source QR RestaurantSettings tại pin59216d7: có QRCodeSVG/export PNG nhưng QR chung quán; plan port thành từng bàn. Bổ sung encrypted token để cashier xuất lại QR với hash lookup. GitHub connector xác nhận source; web open lỗi cache, không coi là source runtime đã chạy.
- Sửa nhận định cũ: SHA nguồn thật có package-lock.json (git ls-tree xác minh); chưa npm ci/build, không khẳng định nguồn thiếu lock. Không install/run code/SQL nguồn.
- DEMO.txt có usernames dự kiến và script; password/QR thật chỉ xuất TXT ignored ở DEMO01, chưa tạo account giả hoặc commit secrets. Chưa app/mock/live/canonical OpenAPI/deploy.
- Local docs checks thực chạy: Python kiểm4 tài liệu/15 link nội bộ/17 sections/F01–F12/T01–T16/fences đều pass; git diff --check pass; diff review consistency/quyền/secrets. Mermaid source đã review, chưa render. Build/types/lint/unit/integration/security dependency audit N/A chưa app; hosted CI và deployed checks chưa chạy.
- Fetch origin thành công sau dùng quyền phù hợp vì mặc định bị chặn ghi FETCH_HEAD; HEAD và origin branch chưa diverge (0/0) trước commit. Commit/push/remote SHA xác minh ở thao tác cuối; tra history/ls-remote, không nhúng SHA tự tham chiếu.
- Self-evaluation: accuracy4/5 (static/source facts đã đối chiếu, runtime chưa có); completeness4/5 (đủ PLAN nhưng canonical schema/accounts thật thuộc mốc sau); clarity4/5 (17 mục và bảng, vẫn dài để đủ giao việc); actionability4/5 (C01/tasks/tests rõ, commands còn phải tạo ở scaffold); conciseness4/5 (có lặp acceptance để trace test). Trung bình4.0/5. Cải thiện ưu tiên: kiểm canonical examples/DTO ở C01, render diagrams khi detailed design; không mở rộng scope thành app trong PLAN.
- Next coordinator C01 CONTRACT-1, S01 scaffold rồi hai agent FE/BE design khi được giao; chưa khởi chạy agent sản phẩm.

## 2026-11-03 — PLAN: khảo sát source và deploy webapp

- S1 commit `9ccdca2a9abb5bd8c031df75c82e73b2397f505c` đã push, local/remote SHA trùng.
- Chủ repo bổ sung: deploy nhanh và thủ tục rõ trong PLAN; tìm/clone repo cùng đề, ưu tiên repo roshanx0 gửi. Đọc skills deployment-patterns/github-ops, dùng GitHub connector và web docs chính thức.
- Clone 3 repo vào `.local-tools/references/`, kiểm clones sạch và đều ignored, chưa install/run source/SQL. SHA/lựa chọn trong PLAN mục 7: UI roshan MIT; ứng viên 2 thiếu root LICENSE; ứng viên 3 AGPL không copy code.
- Static review roshan: SQL thật setup.sql, README chỉ schema.sql không có; checkout tự nhập bàn/tên/phone, tổng/thuế client; JSONB orders thiếu bill nhiều lượt/per-item status; auth/RLS/role phải thay. Không claim runtime/security pass.
- PLAN mục 8: Railway Docker web FE+FastAPI cùng origin + Postgres, Render dự phòng; account/budget/GitHub/env/Docker/PORT/migrate/seed/HTTPS/QR/SSE/smoke/update/rollback, links nguồn đọc 2026-11-03. Chưa cloud resource/chi phí/deploy.
- Checks checkpoint: Markdown structure/link và diff trước commit; app tests/build/types/lint N/A, hosted CI/deployed checks chưa chạy. Next coordinator: S2 contract/features/FE/BE/tasks/tests cùng file.

## 2026-11-03 07:58 Asia/Bangkok — PLAN S1: hệ thống và quyền TapOrder

- Yêu cầu: PLAN chi tiết FE/BE chung một file; ba role có API/actions/UI khác nhau; commit/push sau mỗi bước. Chỉ PLAN, chưa triển khai app.
- Nguồn đọc: AGENTS.md, agent.md, PROJECT/HANDOFF/WORKLOG, plans/README + template, feature template, README; đủ 10 Markdown playbook; skills git-workflow, verification-loop, security-review, agent-self-evaluation.
- Repo baseline `88e19d3`, sạch, chưa manifests/locks/tests/CI. Tạo nhánh `codex/taporder-plan`; fetch origin thành công với quyền phù hợp sau lần read remote mặc định lỗi mạng. Giữ remote cũ.
- S1: tạo PLAN sections 1–6, scope/decisions/system trước feature; role/action/resource/UI matrix, guest capability + staff RBAC, schema/state/locks/idempotency, môi trường/seed/rollback. P0 nghiệp vụ, P1 SSE, P2 gợi ý/thống kê.
- Chốt ba câu hỏi đề: hủy dòng của mình khi waiting; paid không reopen, QR cho lượt mới khi submit; hết hàng reject cả lượt và giữ giỏ. Không có câu hỏi nghiệp vụ chặn PLAN.
- Mock/live: chưa có app. Checks S1: kiểm cấu trúc/link và diff trước commit; application tests/build/types/lint N/A do chỉ Markdown. Hosted CI/deploy chưa có/chưa chạy. Push/SHA xác minh sau commit, không suy ra từ local.
- Next owner coordinator: S2 hoàn thiện cùng file, chưa chạy hai agent sản phẩm.

## 2026-11-03 — SETUP: quy trình và vault

- Yêu cầu: chuẩn bị môi trường/hướng dẫn trước khi nhận đề, giữ stack FE cũ và dùng Python/FastAPI/PostgreSQL Docker.
- Đã đọc: 10 Markdown trong playbook; skills skill-installer/ecc-guide/git-workflow/verification-loop; repo/Git và nguồn ECC/Obsidian chính thức.
- Phát hiện: repo chưa có commit/source/CI; remote origin đã đặt; ECC skills đã có nhiều trên máy, cần kiểm tra installation thay vì overwrite hàng loạt. Winget nhận diện Obsidian đã có bản cũ và đang cập nhật.
- Artifacts: agent guides, templates PLAN/feature, context, README, ignore local tools/settings/secrets.
- Quyết định: repo root là Obsidian vault; contract trước hai agent; worktree + ownership riêng; setup không tự đặt nghiệp vụ hoặc tạo pipeline app khi chưa có stack manifest.
- Kiểm tra docs/cài đặt và Git sync: sẽ ghi kết quả thực tế ở checkpoint tiếp theo trước bàn giao.

## 2026-11-03 — SETUP: công cụ local đã xác minh

- Obsidian: winget update/install thành công, package 1.15.0; executable `D:\Obsidian\Obsidian.exe` metadata 1.15.0.0. Đã thêm vault repo ID `34e11dbe483ba4bf` vào cấu hình local, giữ bốn vault khác; bản sao cấu hình cũ tại `.local-tools/obsidian-config-before.json` (ignored). Chưa mở UI nghiệm thu.
- ECC: clone chính thức vào `.local-tools/ecc`, revision `b38be6a7f6350964d59328b52f0624e1d1d552d1`; đối chiếu đủ 314 skills và 620 files giống upstream, thiếu 0/khác 0. Installation sẵn có được giữ nguyên, không ghi đè hay nhân đôi.
- Quyền: clone/cài app/đăng ký vault chạy với quyền phù hợp; thao tác Git mutation mặc định bị chặn ghi `.git`, dùng cùng thao tác với quyền được cấp. Không bỏ qua hoặc đổi đích remote.
- Gate ứng dụng build/type/lint/unit/integration: N/A, repo chưa có source/manifests. Docker CLI hiện diện; engine chưa kiểm tra vì chưa tới bước app.
- Bước tiếp: kiểm tra docs/diff, commit/push setup và xác minh SHA remote; sau đó chờ chủ repo giao đề.

## 2026-11-03 — SETUP: verification trước commit

- Cấu trúc Markdown: 11 file mới được kiểm tra, 13 link nội bộ hợp lệ, 0 fence chưa đóng/0 link lỗi. Playbook gốc có 14 tham chiếu ra source dự án cũ bị thiếu; ghi rõ trong HANDOFF, giữ nguyên nội dung do chủ repo cung cấp.
- Ignore check: `.local-tools/ecc`, `.obsidian/workspace.json`, `.env` đều bị ignore. Không đưa ECC source/settings/installer/credentials vào commit.
- Diff review: scope chỉ tài liệu workflow/templates/context, ignore và playbook có sẵn; không có app hoặc dependency thay đổi. Build/types/lint/application tests N/A; hosted CI/deploy chưa chạy, không claim pass.
- Tự đánh giá theo skill `agent-self-evaluation`: accuracy 4/5 (cài/version/config đã xác minh, UI chưa mở); completeness 5/5 (hướng dẫn, công cụ, context và templates đủ scope setup); clarity 4/5 (hướng dẫn dài do nhiều gates, có bảng routing); actionability 5/5 (entrypoint và next step cụ thể); conciseness 4/5 (AGENTS tóm tắt có lặp vài quy tắc bắt buộc với agent guide). Trung bình 4.4/5; không có lỗi nghiêm trọng. Cải thiện ưu tiên: UI Obsidian có thể kiểm tra khi cần sử dụng; rút gọn phần lặp nếu workflow lớn thêm. Self-check: đáp ứng setup và không sáng tác đề bài.

## 2026-11-03 — SETUP: checkpoint GitHub đã xác minh

- Commit `d2dd422bfae4c2976de46a78d1d387019a949cd7`: `chore(setup): prepare agent workflow and Obsidian context`, 22 files (bao gồm playbook gốc, không sửa nội dung).
- Fetch và push thành công tới remote có sẵn, nhánh `codex/setup-agent-workflow`, upstream tracking đã đặt. `git ls-remote` cho nhánh này trùng SHA local; working tree sạch và `git diff --check` không lỗi tại checkpoint.
- Kết quả: SETUP sẵn sàng nhận đề. Bản cập nhật context này được commit/push riêng; HEAD cuối cùng tra Git history, tránh vòng ghi SHA tự tham chiếu.
- Next action: chủ repo gửi đề → PLAN chi tiết theo templates/playbook. Chưa chạy agent frontend/backend sản phẩm hoặc app tests/hosted CI/deploy.
