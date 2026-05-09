# 🍪 WeChat Analyzer Pro

> 微信聊天记录人格分析工具 — 支持 Windows & macOS，支持群聊分析，自动生成好友备注推荐标签

## ✨ 功能特性

| 功能 | 描述 |
|------|------|
| 🖥️ 跨平台支持 | 支持 Windows 和 macOS 微信数据库 |
| 💬 私聊分析 | 分析与好友的聊天记录，生成双人对比报告 |
| 👥 群聊分析 | 分析群聊数据，统计成员发言情况 |
| 🔀 成员对比 | 从群聊中提取任意两个成员进行对比分析 |
| 🏷️ 备注推荐 | 自动生成好友备注标签，一键复制到微信 |
| 📊 可视化报告 | 生成精美的 HTML 分析报告 |

## 📋 使用要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 或 macOS 12+ |
| Python | 3.10 及以上 |
| 微信版本 | Windows 微信 4.x / Mac 微信 4.x |

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/wechat-analyzer-pro.git
cd wechat-analyzer-pro
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 准备数据库

本工具需要**已解密的微信数据库**。请使用以下工具之一解密：

#### Windows 用户

推荐使用 [ylytdeng/wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt)：

```bash
git clone https://github.com/ylytdeng/wechat-decrypt.git
cd wechat-decrypt
pip install -r requirements.txt
python find_all_keys_windows.py
python decrypt_db.py --db-dir "微信数据库路径" --keys-file all_keys.json
```

#### macOS 用户

推荐使用 [Java-Chris/wechat-db-decrypt-macos](https://github.com/Java-Chris/wechat-db-decrypt-macos)

### 4. 配置路径

编辑 `config.json`，设置解密后的数据库目录：

```json
{
  "decrypted_db_dir": "/path/to/decrypted/db_storage"
}
```

### 5. 运行分析

```bash
cd src

# 列出所有联系人
python main.py --list-contacts

# 列出所有群聊
python main.py --list-groups

# 分析私聊
python main.py --contact "好友名称"

# 分析群聊
python main.py --group "群名"

# 群成员两两对比
python main.py --group "群名" --pair "成员A" "成员B"
```

## 📖 使用示例

### 私聊分析

```bash
python main.py --contact "小明" --output ./analysis
```

输出：
- `analysis/report.html` - 完整分析报告
- `analysis/analysis_result.json` - 分析结果数据

### 群聊分析

```bash
python main.py --group "工作群" --output ./analysis
```

输出：
- `analysis/group_report.html` - 群聊概览报告
- `analysis/group_analysis.json` - 分析结果数据

### 群成员对比

```bash
python main.py --group "工作群" --pair "张三" "李四" --output ./analysis
```

输出：
- `analysis/张三_vs_李四_report.html` - 对比报告
- `analysis/张三_vs_李四_analysis.json` - 分析数据

## 🏷️ 好友备注推荐

分析完成后，工具会自动生成适合微信好友备注的一句话标签：

```
张三: 冷静的战略规划者，用系统思维解决问题
李四: 热情的团队协调者，用沟通推动协作
王五: 敏捷的辩论家，用创新推动讨论
```

你可以直接复制这些标签到微信联系人备注中。

## 📊 分析内容

### Big Five 人格维度

- **开放性 (Openness)** - 对新事物的接受程度
- **尽责性 (Conscientiousness)** - 做事的认真程度
- **外向性 (Extraversion)** - 社交活跃程度
- **宜人性 (Agreeableness)** - 与人相处的态度
- **神经质 (Neuroticism)** - 情绪稳定性

### MBTI 人格类型

基于 Big Five 和沟通风格推断 MBTI 类型：
- 分析师：INTJ, INTP, ENTJ, ENTP
- 外交家：INFJ, INFP, ENFJ, ENFP
- 守护者：ISTJ, ISFJ, ESTJ, ESFJ
- 探险家：ISTP, ISFP, ESTP, ESFP

## 🔒 隐私说明

- 所有数据处理在**本地**完成
- 不会向任何外部服务器发送数据
- 分析结果仅保存在本地
- 请勿用于分析他人设备上的数据

## 🙏 致谢与引用

本项目基于以下开源项目构建：

| 项目 | 用途 | 链接 |
|------|------|------|
| [Jiang59991/wechat-analyzer](https://github.com/Jiang59991/wechat-analyzer) | 原始分析框架、报告模板 | 感谢原作者的人格分析思路和精美报告设计 |
| [ylytdeng/wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt) | Windows 微信数据库解密 | Windows 用户的核心依赖 |
| [Java-Chris/wechat-db-decrypt-macos](https://github.com/Java-Chris/wechat-db-decrypt-macos) | macOS 微信数据库解密 | macOS 用户的核心依赖 |

特别感谢以上项目的开发者们！

## 📝 更新日志

### v2.0.0 (2024-05)

- ✨ 新增 Windows 平台支持
- ✨ 新增群聊分析功能
- ✨ 新增群成员两两对比
- ✨ 新增好友备注推荐标签
- 🔧 重构代码结构，提升可维护性

## 📄 许可证

MIT License

## ⚠️ 免责声明

本工具仅供个人学习研究使用，请勿用于任何违法用途。使用本工具分析他人聊天记录可能涉及隐私问题，请确保获得当事人同意。

---

<p align="center">Made with ❤️ by Claude & Human</p>
