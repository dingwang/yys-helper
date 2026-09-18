# 御魂匠图标 · 2026-09-18

制作：内置 imagegen 生成，随后用同一工具清理外沿；PNG 保留生成的透明通道。`scripts/package_icon.py` 只做 Windows ICO 多分辨率格式打包（16/24/32/48/64/128/256），没有重新绘制设计。

设计：Apple/macOS 风格的柔白圆角底座、冰蓝与白色玻璃阴阳符号。原创应用图标，不使用 Apple 标识或游戏官方素材。

最终资产：`app-icon.png`、`app-icon.ico`。桌面快捷方式以本地内容哈希命名的 ICO 缓存避免旧图标缓存；可运行 `scripts/update_shortcut.ps1` 更新，保留已有启动参数。

## 初始生成提示词

Use case: logo-brand. Asset type: production desktop app icon for a Chinese Onmyoji inventory and daily task assistant, 1024x1024 square PNG. Primary request: redesign in a refined modern Apple macOS app icon aesthetic, original identity, NOT an Apple logo. A single strong, balanced yin-yang symbol, two flowing interlocking comma shapes in saturated azure blue and frosted icy-white translucent glass, readable at 32 pixels. The symbol sits centered on a warm porcelain white rounded-square squircle tile with a very subtle pale-blue center glow and restrained soft bevel, gentle diffuse studio highlight from upper left. Straight-on orthographic view, precise symmetry, generous negative space, large central mark taking around 60% of tile width. A quiet high-end utility icon, not a game badge. Tile fills approximately 90% of canvas; genuinely transparent outer corners and background outside tile. Avoid text, letters, Apple logos, gold filigree, ornate frames, stars, sparkles, extra circles, clutter, metallic fantasy decoration, dark background, strong drop shadow, perspective tilt, mockup sheets. One finished icon only.

## 定向修订提示词

Precise-object-edit of the most recent generated blue and white yin-yang desktop icon. Keep its exact interior design, tile size, colors and glass shading unchanged. Clean only the alpha outer boundary: remove ragged stray white flecks around the tile and all outside glow. The entire rounded square silhouette should have a perfectly smooth antialiased edge. Every pixel outside that single rounded-square icon must be genuinely transparent. No changes to the interior yin-yang mark, no extra decorations. Return the single production-ready icon.
