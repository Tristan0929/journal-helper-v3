# PWA 部署教程（把网站装成手机 App）

目标：部署到 HTTPS 网址（如 Render）后，用手机浏览器「添加到主屏幕」，得到一个有独立图标、全屏打开、像原生 App 的入口。**全程免费、无需上架 App Store。**

---

## 一、先搞清楚 PWA 需要什么

一个网站能被「装」成 App，必须同时满足 4 个条件，缺一不可：

1. **HTTPS**（Render 自动就是 https，localhost 也算安全上下文，可本地测）
2. **manifest（清单文件）** —— 告诉手机 App 叫什么、什么图标、怎么打开
3. **service worker（SW）** —— 一段后台脚本，PWA 的“身份证”
4. **图标**（至少 192×192 和 512×512 的 PNG）

这 4 样代码里都已经写好了，你只要确认文件带上、部署到 https 即可。

---

## 二、确认项目里这些东西都在（重要）

在项目根目录 `journal-helper-v3/` 下应该有：

```
app.py
templates/index.html
static/
  ├── icon-192.png
  ├── icon-512.png
  └── apple-touch-icon.png
requirements.txt
```

对应的代码（都已写好，核对一下即可）：

- **`app.py`** 里有两个路由：
  - `GET /manifest.webmanifest` —— 返回清单
  - `GET /sw.js` —— 返回 service worker
  （注意 sw.js 必须从**根路径** `/sw.js` 提供，这样它才能管整个站点。已经是这样了。）

- **`templates/index.html`** 的 `<head>` 里有：
  ```html
  <link rel="manifest" href="/manifest.webmanifest">
  <meta name="theme-color" content="#b3541e">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="外刊助手">
  <link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
  <link rel="icon" href="/static/icon-192.png">
  <script>if("serviceWorker" in navigator){window.addEventListener("load",()=>navigator.serviceWorker.register("/sw.js").catch(()=>{}));}</script>
  ```

> ⚠️ 最常见的坑：`static/` 图标**没提交到 Git**，部署后图标 404，PWA 就装不了。下一步专门处理。

---

## 三、提交到 GitHub（关键：别漏了 static/）

在项目文件夹打开终端：

```bash
cd journal-helper-v3

# 1) 确认 static 里的图标会被 git 跟踪（有些 .gitignore 会忽略图片）
git add -f static/icon-192.png static/icon-512.png static/apple-touch-icon.png

# 2) 加上其余改动
git add app.py templates/index.html requirements.txt README.md

# 3) 提交
git commit -m "feat: PWA 支持（manifest + service worker + 图标）"

# 4) 推送
git push
```

推送后，去 GitHub 仓库页面**亲眼确认** `static/` 文件夹和 3 个 png 都在。如果不在，多半是被 `.gitignore` 挡了——用上面的 `git add -f`（强制添加）再提交一次。

---

## 四、在 Render 上部署 / 重新部署

如果你已经在 Render 部署过，`git push` 后它会**自动重新部署**，等几分钟即可。若是第一次：

1. Render → New → **Web Service** → 连接你的 GitHub 仓库。
2. 配置：
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：
     ```
     gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 300
     ```
   - Instance Type：Free 即可。
3. 部署完成后拿到网址，例如 `https://journal-helper-v3.onrender.com`。

Render 默认给的就是 **https**，PWA 的前提自动满足。

---

## 五、部署后先在电脑 Chrome 验证（30 秒）

用电脑 Chrome 打开你的线上网址，按 F12 打开开发者工具：

1. **Application（应用）标签 → Manifest**
   - 能看到名称「外刊阅读助手」、图标预览、theme color。没报红就对了。
2. **Application → Service Workers**
   - 能看到 `/sw.js` 状态是 **activated and running**。
3. 直接访问 `https://你的域名/manifest.webmanifest`，应返回一段 JSON；访问 `/sw.js` 应返回一段 JavaScript。
   - 若这两个 404，说明后端没部署新版 `app.py`，重新 push。
4. 直接访问 `https://你的域名/static/icon-512.png`，应能看到图标。
   - 若 404，就是第三步图标没提交，回去 `git add -f`。

Chrome 地址栏右侧若出现「安装」图标，点它就能把网站装成桌面应用。

---

## 六、手机上「添加到主屏幕」

### iPhone / iPad（Safari）
1. 用 **Safari**（不是微信/Chrome 内置浏览器）打开你的网址。
2. 点底部**分享**按钮（方框向上箭头）。
3. 选「**添加到主屏幕**」。
4. 确认名称「外刊助手」，点添加。
5. 桌面出现独立图标，点开就是**全屏、无地址栏**，像 App 一样。

> iOS 的 PWA 由 Safari 提供，用微信里打开是不行的，必须 Safari。

### 安卓（Chrome）
1. 用 Chrome 打开网址。
2. 通常会自动弹「添加到主屏幕 / 安装应用」的横幅；没弹就点右上角 ⋮ → 「**安装应用 / 添加到主屏幕**」。
3. 确认即可，桌面出现图标。

---

## 七、常见问题排查

| 现象 | 原因 & 解决 |
|------|------|
| 图标是灰的 / 默认截图 | `static/` 图标 404。确认已 `git add -f` 提交，且 `/static/icon-512.png` 能直接打开 |
| 没有「添加到主屏幕」选项 | 不是 https（用了 http），或不是 Safari/Chrome，或 manifest/sw 没加载。按第五步逐项查 |
| `/manifest.webmanifest` 或 `/sw.js` 打开是 404 | 线上还是旧版 app.py，重新 `git push` 让 Render 重部署 |
| 改了代码但手机 App 里没更新 | Service worker 有缓存。杀掉后台重开；或 DevTools → Application → Service Workers → Unregister 再刷新。本项目 sw 对首页用「网络优先」，一般刷新即更新 |
| iOS 打开还是有地址栏 | 检查 `<meta name="apple-mobile-web-app-capable" content="yes">` 在不在 head 里；且必须从主屏幕图标打开，不是 Safari 里打开 |

---

## 八、想换图标？

图标就是 `static/` 里的三个 png。你可以用任意 512×512 的 PNG 覆盖 `icon-512.png`，192×192 覆盖 `icon-192.png`，180×180 覆盖 `apple-touch-icon.png`（文件名别改），再 `git add -f static/*.png && git commit && git push` 即可。

---

## 九、关于真正上架 App Store / TestFlight（可选，非免费）

PWA 到此就够日常「像 App 一样用」了。若你一定要在 **App Store 搜到、用 TestFlight 分发**：

1. 需要 **Apple 开发者账号：99 美元/年**（TestFlight 免费，但依附这个付费账号）。
2. 需要一台 **Mac + Xcode**（软件免费）。
3. 用一个 **WKWebView 壳**把你的网址包成 iOS App（可用开源模板，或工具如 Capacitor）。
4. 通过 Xcode 上传到 App Store Connect → 走 TestFlight 内测 / 提交审核。

这条路能力上没问题，但**那 99 美元/年绕不开**。日常用 PWA 完全够，等确有上架需求再考虑。
