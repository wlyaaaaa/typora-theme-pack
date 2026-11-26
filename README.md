# Typora 薄荷主题与 PDF 样式

- **这是什么：** 给 Typora 加一套薄荷色的编辑主题，并提供原版、个人、公司三种 PDF 样式。
- **我怎么用：** 让 AI 安装主题，重启 Typora 后在“主题”菜单选“Verdant Mint”。
- **怎么知道正常：** Typora 的主题菜单里有“Verdant Mint”，选上后显示正常。
- **坏了怎么提醒我：** 没有自动提醒，出问题直接跟 AI 说。
- **让 AI 做什么：** 安装和检查主题、配置 PDF 转换器，按需要导出原版、个人版或公司版 PDF。

导出 PDF 要另外配置转换器，只装主题不需要。许可见 [NOTICE](NOTICE.md)。

Pillow 只用于生成预览图，导出工具不依赖它。预览工具仍保留；外部 PDF 转换器需要哪些依赖（例如 Markdown），以转换器自身的要求为准。

三种 PDF 导出在仓库的 `tools/export_pdf.py`，用 `--mode original`、`personal`、`company` 分别得到“原版”“个人”“公司”后缀。要刷新 Typora 的三个自定义导出菜单，在配置转换器后运行 `python tools/configure_typora_menu.py`；它只更新这三个菜单槽，先备份 `profile.data`。菜单通过 `typora_export_launcher.ps1` 每次读取 PCConfig 登记的 Python，仓库移动后重新运行菜单配置即可。

实况接入在 `docs/live.contract.json`；沿原验证入口按需刷新：`python tools/install_theme.py verify --live-output docs/live.snapshot.json --profile-data <本机配置文件> --host-python-registry <本机Python登记>`，隔离工作树检查正式安装时再传 `--installation-root <正式检出>`。它只检查现有配置和文件，不试导出。机器路径由本机调用方提供。换主题、菜单或样张后按需核验，页面保留上次核验的时刻。PCConfig 的项目夜检只复算源码和文档规模，不重新检查安装、菜单或 PDF 导出。
