# My LiveContainer Source

这是一个独立的个人 AltStore 源，LiveContainer、AltStore、SideStore 和
Feather 都可以读取生成的 `all-apps.json`。

首次发布前，先编辑 `config/source.json`，至少替换源名称、`identifier`、
`website` 中的 `OWNER/REPO`；如果要使用自己的图标，再把 `iconURL` 指向你
仓库中的图标文件。

## 当前内容

- 默认同步 AltGallery 的全部应用，并保留其版本、图标、截图和更新消息。
- 通过 `config/source.json` 自定义源名称、图标、颜色和上游应用筛选。
- 通过 `apps/extra-apps.json` 添加不在 AltGallery 中的应用。
- GitHub Actions 每 6 小时更新一次上游数据，也支持手动运行工作流。

## 在 LiveContainer 中添加

把下面的地址替换为你的 GitHub 用户名和仓库名，然后在 LiveContainer 的
`Sources` 页面点击 `+` 添加：

```text
https://raw.githubusercontent.com/OWNER/REPO/refs/heads/main/all-apps.json
```

也可以使用深链接：

```text
livecontainer://source?url=https%3A%2F%2Fraw.githubusercontent.com%2FOWNER%2FREPO%2Frefs%2Fheads%2Fmain%2Fall-apps.json
```

如果你的默认分支是 `master`，把上面地址中的 `main` 换成 `master`。

## 添加额外应用

编辑 `apps/extra-apps.json`，在 `apps` 数组中加入一个完整的 AltStore 应用
对象。最小示例：

```json
{
  "name": "Example App",
  "bundleIdentifier": "com.example.app",
  "developerName": "Developer",
  "subtitle": "Short description",
  "localizedDescription": "Full description",
  "iconURL": "https://HOST/icon.png",
  "versions": [
    {
      "version": "1.0.0",
      "date": "2026-01-01",
      "downloadURL": "https://HOST/Example.ipa",
      "minOSVersion": "15.0"
    }
  ]
}
```

要求：

1. `downloadURL` 必须是可以直接下载 IPA 的 HTTPS 地址，不是 GitHub Release
   页面地址。
2. `bundleIdentifier` 必须与 IPA 内的 `CFBundleIdentifier` 一致。
3. 若与上游应用的 `bundleIdentifier` 相同，额外应用会替换上游条目；不同则
   追加到列表末尾。
4. 可选的更新消息放入 `news` 数组，`appID` 填对应的
   `bundleIdentifier`，并为每条消息提供唯一 `identifier`。

本地验证：

```bash
python3 scripts/build_source.py --check
python3 -m unittest discover -s tests -v
```

修改后生成正式文件：

```bash
python3 scripts/build_source.py
```

需要立即拉取 AltGallery 最新内容时：

```bash
python3 scripts/build_source.py --refresh-upstream
```

## 筛选 AltGallery 应用

默认 `includeAppNames` 和 `includeBundleIdentifiers` 为 `null`，表示全部保留。
如果只想保留部分应用，把 `config/source.json` 中的 `null` 改为数组，例如：

```json
"includeAppNames": ["Aidoku", "PiliPlus", "UTM"],
"includeBundleIdentifiers": null
```

也可以使用 `excludeAppNames` 或 `excludeBundleIdentifiers` 排除个别应用。

## Fork 还是独立仓库

个人使用建议采用当前这种**独立仓库**：

- 源名称、图标、筛选列表和额外应用完全由你控制；
- 上游只作为数据来源，不会把你的定制内容混入 AltGallery；
- 不需要处理 fork 与上游分支同步时的冲突。

只有在你准备向 AltGallery 提交应用、希望沿用其完整 `altgen` 配置体系，或
想直接跟随其目录结构维护时，才更适合 fork。无论哪种方式，LiveContainer
最终读取的都是一个公开可访问的 AltStore JSON URL。

## 归属说明

上游应用目录和部分资源来自
[bebound/AltGallery](https://github.com/bebound/AltGallery)，其生成源地址记录在
`config/source.json`；各应用的 IPA 下载地址仍由对应项目维护。
