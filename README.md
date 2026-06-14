# AI 日报

每天 17:00 自动推送到飞书的 AI 日报。

## 使用方法

### 1. 注册 GitHub 账号
如果没有，去 https://github.com/signup 注册一个。

### 2. 创建仓库
1. 打开 https://github.com/new
2. 仓库名填 `ai-daily-report`
3. 选 **Public**（公开，免费）
4. 点 **Create repository**

### 3. 上传文件
创建好仓库后，点 **Add file → Upload files**，把以下文件拖进去：

- `.github/workflows/daily-report.yml`
- `daily_report.py`

然后点 **Commit changes**。

### 4. 设置密钥
1. 进仓库 Settings → **Secrets and variables → Actions**
2. 点 **New repository secret**，分别添加：
   - `FEISHU_APP_ID` → `cli_aa9fe7e3fa3a1cd7`
   - `FEISHU_APP_SECRET` → 在 Hermes 的 `~/.hermes/.env` 里找到 `FEISHU_APP_SECRET=...` 的值
   - `FEISHU_CHAT_ID` → `oc_2277f3a0958bcc1d546735c6e51014f5`

### 5. 测试运行
1. 进仓库 **Actions** 页面
2. 左边点 **AI 日报**
3. 右边点 **Run workflow → Run workflow**
4. 等一两分钟，看看飞书有没有收到卡片
