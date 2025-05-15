#青龙面板签到脚本
脚本都是网上收集 AI生成适配个人自用脚本

命令解析：
ql repo https://github.com/Ray2023m/script.git "白名单" "黑名单" "依赖文件" "分支" "文件后缀"

白名单：指要拉取的脚本（多个用 | 隔开）

黑名单：指要忽略的脚本（多个用 | 隔开）

依赖文件：utils 项目运行所必需的框架依赖

分支：拉取仓库的指定分支

文件后缀：要拉取的文件后缀，如 js|py|sh|ts 等

青龙拉取命令：'''ql repo https://github.com/Ray2023m/script.git "" "" "" "main" '''
