# Godmiracle LiveContainer 源

这是由 **godmiracle** 维护的个人 AltStore 源，面向 LiveContainer、AltStore、
SideStore 和 Feather。源内容以 [AltGallery](https://github.com/bebound/AltGallery)
为上游，并保留了添加自定义 IPA 的入口。

## 源地址

在 LiveContainer 的 `Sources` 页面点击 `+`，添加下面的地址：

```text
https://raw.githubusercontent.com/godmiracle/my-ipa-source/refs/heads/main/all-apps.json
```

LiveContainer 深链接：

```text
livecontainer://source?url=https%3A%2F%2Fraw.githubusercontent.com%2Fgodmiracle%2Fmy-ipa-source%2Frefs%2Fheads%2Fmain%2Fall-apps.json
```

仓库地址：[godmiracle/my-ipa-source](https://github.com/godmiracle/my-ipa-source)

## 当前支持的应用

以下列表由 `all-apps.json` 自动生成；应用版本和
列表会随着 AltGallery 上游同步而变化。

<!-- BEGIN GENERATED APP LIST -->
当前源收录 **31** 个应用；版本信息来自 AltGallery 当前生成源。

| 应用 | 简介 | 当前版本 | 最低系统 |
| --- | --- | --- | --- |
| Aidoku | Free and open source manga reader for iOS and iPadOS | `0.9` | iOS 15.0 |
| AniBaka | 跨平台番剧聚合、媒体播放与弹幕客户端 | `5.1.0` | iOS 13.0 |
| AnimeFlow | 跨平台动漫视频播放器，支持多数据源、实时 4K 超分辨率与弹幕 | `2.5.0` | iOS 13.0 |
| Animeko | 一站式弹幕追番平台 | `6.1.0` | iOS 14.0 |
| Apollo for Reddit - GLASS | Apollo-Reborn build with Liquid Glass patch | `3.6.0` | iOS 未声明 |
| ARMSX2 | PlayStation 2 emulator for ARM64 | `nightly-20260909` | iOS 17.0 |
| Doer | A native iOS client for Linux.do | `1.8.5` | iOS 15.0 |
| DolphiniOS | GameCube and Wii emulator for iOS/iPadOS | `5.0.0b6` | iOS 14.0 |
| DukeX | Original Xbox emulation for iOS | `1.0.2` | iOS 16.0 |
| EhPanda | An unofficial E-Hentai App for iOS built with SwiftUI & TCA | `2.8.1` | iOS 26.0 |
| iTorrent | Torrent client for iOS | `2.2.0-1` | iOS 16.0 |
| Kazumi | 基于自定义规则的番剧采集APP，支持流媒体在线观看，支持弹幕，支持实时超分辨率。 | `2.3.1` | iOS 13.0 |
| KMusic | 基于 SwiftUI 的多源音乐聚合播放器 | `2.3.0` | iOS 14.0 |
| Kumone | 原生 NetEase Cloud Music iOS 客户端（雲の音） | `0.3.16` | iOS 16.0 |
| LiveContainer+SideStore | Run iOS apps without actually installing them! | `3.8.0` | iOS 15.0 |
| Mangayomi | Read manga, novels, and watch anime | `0.9.2` | iOS 未声明 |
| ManicEMU | All-in-one retro game emulator for iOS | `2.0.0` | iOS 15.0 |
| MoviePilotLite | MoviePilot 移动端，基于 Flutter 实现 | `1.2.5` | iOS 15.0 |
| Musly | Free Navidrome client & Subsonic music player | `2.0.2` | iOS 15.0 |
| Novella | 轻书架第三方客户端 | `2.4.0` | iOS 16.4 |
| PiliPlus | 使用Flutter开发的BiliBili第三方客户端 | `2.1.3` | iOS 14.0 |
| Pixiv-SwiftUI | 基于 SwiftUI 的 Pixiv 第三方客户端 | `0.15.0` | iOS 17.0 |
| PSX3IOS | PlayStation 3 emulator for iPhone and iPad | `0.2.7-beta` | iOS 15.0 |
| PureLive | 基于 Flutter 的开源多平台直播聚合播放器 | `3.1.2` | iOS 15.6 |
| SceneBox | Torrent streaming client | `1.0.2` | iOS 18.0 |
| TiebaPure | 基于 SwiftUI 的第三方百度贴吧客户端 | `1.4.14` | iOS 16.4 |
| Tsumiru | Native manga & manhwa reader for Suwayomi-Server | `1.2.1` | iOS 14.0 |
| UTM | Virtual machines for iOS | `4.7.5` | iOS 14.0 |
| VeneraNext | 跨平台漫画阅读器 | `1.15.0` | iOS 14.0 |
| YouProEXTRA | YouTube mod with customizable tweaks | `21.24.3` | iOS 16.0 |
| ZhihuMinusMinus | 轻量、纯净的第三方知乎客户端 | `0.5.0` | iOS 15.1 |
<!-- END GENERATED APP LIST -->

## 添加其他应用

编辑 `apps/extra-apps.json`，将应用对象加入 `apps` 数组。至少需要提供：

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

规则：

1. `downloadURL` 必须是可以直接下载 IPA 的 HTTPS 地址，不是 GitHub Release 页面。
2. `bundleIdentifier` 必须与 IPA 内的 `CFBundleIdentifier` 一致。
3. 如果 `bundleIdentifier` 与 AltGallery 中的应用相同，自定义条目会覆盖上游条目；
   不同则追加到列表末尾。
4. 添加后执行：

```bash
python3 scripts/build_source.py
python3 scripts/update_readme_apps.py
python3 -m unittest discover -s tests -v
```

然后提交并推送：

```bash
git add README.md all-apps.json apps/extra-apps.json config/source.json data/upstream-all-apps.json scripts/
git commit -m "feat: add custom app"
git push origin main
```

## 同步 AltGallery

手动同步最新上游内容：

```bash
python3 scripts/build_source.py --refresh-upstream
python3 scripts/update_readme_apps.py
```

GitHub Actions 会每 6 小时自动同步一次，也可以在仓库的 **Actions** 页面手动运行。

## 筛选应用

默认会保留 AltGallery 全部应用。若只保留指定应用，编辑 `config/source.json`：

```json
"includeAppNames": ["Aidoku", "PiliPlus", "UTM"],
"includeBundleIdentifiers": null
```

也可以通过 `excludeAppNames` 或 `excludeBundleIdentifiers` 排除应用。

## 归属说明

应用目录和部分资源来自 [bebound/AltGallery](https://github.com/bebound/AltGallery)，
上游源地址记录在 `config/source.json`。各应用的 IPA、图标、截图和版本说明由对应项目维护。
