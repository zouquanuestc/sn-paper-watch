# Springer Nature 论文状态监控（GitHub Actions 版）

每天北京时间 **09:00 / 21:00** 自动登录 Springer Nature，抓取全部投稿状态并与上次快照对比，
**有变化或检查失败时**发邮件到 `32400920@qq.com`。运行在 GitHub 的服务器上，本机关机不影响。

## 一次性配置（约 3 分钟）

1. 打开 https://github.com/new 新建一个仓库（建议 **Private**，名字随意，如 `sn-paper-watch`），
   不要勾选 README / .gitignore。
2. 把本目录（`sn-gha` 里的全部内容，包括隐藏的 `.github` 文件夹）上传到该仓库。
   - 网页方式：仓库首页 → "uploading an existing file" → 把 `.github`、`check.py`、`requirements.txt`、`state` 一起拖进去 → Commit。
3. 仓库 → **Settings → Secrets and variables → Actions → New repository secret**，依次添加 4 个：

   | Name | Value |
   |---|---|
   | `SN_EMAIL` | `zouquan@nclab.net` |
   | `SN_PASSWORD` | Springer Nature 账号密码 |
   | `SMTP_AUTH` | QQ 邮箱 SMTP 授权码 |
   | `MAIL_TO` | `32400920@qq.com` |

4. 打开 **Actions** 标签页 → 左侧 "Springer Nature paper status check" →
   右侧 **Run workflow** 手动跑一次，确认日志出现 `FIRST_RUN` 且收到「部署成功」邮件。

## 日常

- 快照文件 `state/snapshot.txt` 由工作流自动提交回仓库（bot commit），无需手工维护；
- 需要临时查一次：Actions → Run workflow；
- 修改检查时间：编辑 `.github/workflows/check.yml` 里的 cron（UTC 时间，北京时间减 8 小时）。

## 说明

- GitHub 的定时任务在高峰期可能延迟几分钟到几十分钟，属正常现象；
- 仓库若 60 天无任何活动，GitHub 会自动暂停定时工作流，届时点一下 Actions 页面的
  "Enable workflow" 即可（每次状态变化产生的提交也算活动，一般不会触发）。
