# 可视化伴侣使用指南

可视化伴侣是一套运行在浏览器中的辅助工具，用来展示界面草图、架构图和可点击的方案选项。

**脚本位置：** 下文中的 `scripts/` 都相对于当前 Skill 目录。执行前先解析 Skill 的绝对路径，例如 `~/.codex/skills/brainstorming/scripts/`。命令里的 `<skill-dir>` 表示该 Skill 的绝对路径。

## 什么时候使用

不要在会话开始时一次性决定是否全程使用浏览器。每遇到一个问题，都先判断：**让用户直接看到，会不会比用文字描述更容易理解？**

以下内容适合放到浏览器中展示：

- **界面草图**：线框图、页面布局、导航结构、组件设计。
- **架构图**：系统组件、数据流、依赖关系。
- **并排比较**：对比不同布局、配色或设计方向。
- **视觉细节**：间距、层级、风格和整体观感。
- **空间关系**：状态机、流程图、实体关系图。

以下内容留在终端中讨论更合适：

- **需求和范围**：某个概念是什么意思、哪些功能在范围内。
- **文字方案选择**：用文字就能说清楚的 A/B/C 方案。
- **取舍分析**：优缺点、约束和比较表。
- **技术决策**：API 设计、数据模型、架构选型。
- **澄清问题**：答案主要是文字，而不是视觉偏好。

讨论的是 UI，并不代表一定要打开浏览器。例如，“你需要哪种向导流程？”是概念问题，应该在终端中问；“这两种向导布局哪一种更舒服？”才适合用浏览器展示。

## 工作原理

服务器会监视一个目录，并把最新的 HTML 文件展示到浏览器。Codex 将页面内容写入 `screen_dir`，用户可以在浏览器中查看和点击选项；点击结果会记录到 `state_dir/events`，供下一轮对话读取。

HTML 可以有两种形式：

- 如果文件以 `<!DOCTYPE` 或 `<html` 开头，服务器会按完整页面处理，只注入交互脚本。
- 其他内容会被当作页面片段，自动套用内置模板，包括标题栏、主题样式、连接状态和交互逻辑。

默认写页面片段。只有确实需要完全控制页面结构时，才编写完整 HTML 文档。

## 启动会话

只有在用户同意使用可视化伴侣后，才能启动服务器：

```bash
# --open 会在第一张页面准备好后打开浏览器。
# --project-dir 会把会话保存在项目的 .brainstorm/ 目录中，重启后仍可复用。
<skill-dir>/scripts/start-server.sh \
  --project-dir /path/to/project \
  --open \
  --foreground

# 返回示例：
# {"type":"server-started","port":52341,
#  "url":"http://localhost:52341/?key=ab12…",
#  "screen_dir":"/path/to/project/.brainstorm/12345-1706000000/content",
#  "state_dir":"/path/to/project/.brainstorm/12345-1706000000/state"}
```

保存返回结果中的 `screen_dir` 和 `state_dir`。使用 `--open` 时，第一张页面写入后浏览器会自动打开；仍应把完整 URL 告诉用户，方便远程或无界面环境手动访问。

### 不要丢失 URL 中的密钥

URL 带有会话密钥 `?key=…`。服务器会拒绝没有密钥的 HTTP 和 WebSocket 请求，因此：

- 必须使用返回结果中 `url` 字段的完整值。
- 不要删除查询参数。
- 不要只发送 `http://host:port`。

浏览器第一次访问后会通过 Cookie 记住密钥，之后刷新页面或访问 `/files/*` 资源时不需要再次填写。

### 找回连接信息

服务器会把启动信息写入 `$STATE_DIR/server-info`。如果没有保存标准输出，可以读取这个文件找回 URL 和端口。使用 `--project-dir` 时，会话目录位于 `<project>/.brainstorm/`。

建议始终传入项目根目录作为 `--project-dir`，这样页面可以在服务器重启后保留，并复用原来的端口。如果不传，临时文件会写入系统临时目录，并在停止服务器时清理。

如果项目尚未忽略 `.brainstorm/`，提醒用户把它加入 `.gitignore`。

### 在 Codex CLI 中保持进程运行

服务器必须跨越多个对话轮次持续运行，因此要使用 Codex 的长运行命令会话，并保留返回的会话句柄：

```bash
<skill-dir>/scripts/start-server.sh \
  --project-dir /path/to/project \
  --open \
  --foreground
```

不要依赖脱离终端的后台子进程。后续需要查看状态或停止服务器时，继续使用同一个命令会话。

`--open` 会启动浏览器；如果当前权限策略要求确认，先向用户申请批准。

在 Windows 或远程环境中，使用该平台支持的长运行命令机制，确保服务器不会在当前轮次结束后退出。

如果浏览器无法访问返回的地址，可以监听非回环网卡：

```bash
<skill-dir>/scripts/start-server.sh \
  --project-dir /path/to/project \
  --host 0.0.0.0 \
  --url-host localhost \
  --foreground
```

`--url-host` 只控制返回 URL 中显示的主机名。

## 一轮完整交互

1. **确认服务器仍在运行，再写入页面。**
   - 检查 `$STATE_DIR/server-info` 存在，并确认 `$STATE_DIR/server-stopped` 不存在。
   - 如果服务器已经停止，使用相同的 `--project-dir` 重启。脚本会复用原端口，用户已经打开的标签页会自动重连。
   - 服务器默认在空闲 4 小时后退出，可通过 `--idle-timeout-minutes` 调整。

2. **在 `screen_dir` 中创建新的 HTML 文件。**
   - 文件名要表达内容，例如 `platform.html`、`visual-style.html`、`layout.html`。
   - 不要重复使用旧文件名，每张页面都创建新文件。
   - 使用 `apply_patch` 或当前环境支持的文件编辑工具，不要用冗长的终端 heredoc 写 HTML。
   - 服务器会自动展示修改时间最新的文件。

3. **告诉用户页面里有什么，然后结束当前轮次。**
   - 每一轮都附上完整 URL，不要只在第一次发送。
   - 用一句话说明页面内容，例如：“页面中展示了三种首页布局方案。”
   - 请用户在终端回复，也可以直接点击浏览器中的选项。

4. **下一轮读取反馈。**
   - 如果 `$STATE_DIR/events` 存在，读取其中的 JSONL 事件。
   - 把浏览器事件和用户在终端中的回复合并判断。
   - 终端回复是主要反馈，浏览器事件用于补充结构化信息。

5. **根据反馈迭代或进入下一题。**
   - 如果当前方案需要修改，创建新文件，例如 `layout-v2.html`。
   - 当前问题确认后，再进入下一个问题。

6. **回到纯终端讨论时，清空旧页面。**

   ```html
   <!-- 文件名：waiting.html；后续版本可用 waiting-2.html -->
   <div style="display:flex;align-items:center;justify-content:center;min-height:60vh">
     <p class="subtitle">请回到终端继续讨论……</p>
   </div>
   ```

   这样可以避免用户继续盯着已经完成的选择题。下次出现真正需要可视化的问题时，再推送新页面。

重复以上步骤，直到设计讨论结束。

## 编写页面片段

页面片段只需要包含正文内容。服务器会自动补齐页面结构、主题样式、连接状态和交互脚本。

最小示例：

```html
<h2>哪种布局更合适？</h2>
<p class="subtitle">请重点比较阅读体验和视觉层级</p>

<div class="options">
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content">
      <h3>单栏布局</h3>
      <p>结构简洁，阅读路径集中。</p>
    </div>
  </div>
  <div class="option" data-choice="b" onclick="toggleSelect(this)">
    <div class="letter">B</div>
    <div class="content">
      <h3>双栏布局</h3>
      <p>左侧导航，右侧展示主要内容。</p>
    </div>
  </div>
</div>
```

不需要额外添加 `<html>`、CSS 或 `<script>`，服务器会自动提供。

## 可用的 CSS 类

### 选项列表

```html
<div class="options">
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content">
      <h3>方案名称</h3>
      <p>方案说明</p>
    </div>
  </div>
</div>
```

如需多选，在容器上添加 `data-multiselect`：

```html
<div class="options" data-multiselect>
  <!-- 用户可以选择或取消多个选项 -->
</div>
```

### 设计卡片

```html
<div class="cards">
  <div class="card" data-choice="design1" onclick="toggleSelect(this)">
    <div class="card-image"><!-- 界面草图 --></div>
    <div class="card-body">
      <h3>设计名称</h3>
      <p>设计说明</p>
    </div>
  </div>
</div>
```

### 草图容器

```html
<div class="mockup">
  <div class="mockup-header">预览：仪表盘布局</div>
  <div class="mockup-body"><!-- 草图内容 --></div>
</div>
```

### 左右并排

```html
<div class="split">
  <div class="mockup"><!-- 左侧方案 --></div>
  <div class="mockup"><!-- 右侧方案 --></div>
</div>
```

### 优缺点

```html
<div class="pros-cons">
  <div class="pros"><h4>优点</h4><ul><li>主要收益</li></ul></div>
  <div class="cons"><h4>不足</h4><ul><li>主要代价</li></ul></div>
</div>
```

### 线框图组件

```html
<div class="mock-nav">Logo｜首页｜产品｜联系我们</div>
<div style="display: flex;">
  <div class="mock-sidebar">侧边导航</div>
  <div class="mock-content">主要内容区域</div>
</div>
<button class="mock-button">操作按钮</button>
<input class="mock-input" placeholder="请输入内容">
<div class="placeholder">占位区域</div>
```

### 文字和区块

- `h2`：页面标题。
- `h3`：区块标题。
- `.subtitle`：标题下方的辅助说明。
- `.section`：带底部间距的内容区块。
- `.label`：小号标签文字。

## 浏览器事件格式

用户点击选项后，事件会按 JSONL 格式写入 `$STATE_DIR/events`。每次推送新页面时，旧事件会自动清空。

```jsonl
{"type":"click","choice":"a","text":"方案 A：简洁布局","timestamp":1706000101}
{"type":"click","choice":"c","text":"方案 C：复杂网格","timestamp":1706000108}
{"type":"click","choice":"b","text":"方案 B：混合布局","timestamp":1706000115}
```

完整事件流能反映用户的探索过程。最后一次 `choice` 通常是最终选择，但连续切换也可能说明用户仍在犹豫，值得进一步追问。

如果 `$STATE_DIR/events` 不存在，说明用户没有在浏览器中操作，只使用终端回复即可。

## 设计建议

- **展示精度要匹配问题。** 讨论布局时使用线框图，讨论视觉风格时再增加细节。
- **每张页面都说明正在决定什么。** 使用“哪种布局更显专业？”，不要只写“请选择”。
- **先迭代当前问题，再进入下一题。**
- **每页控制在 2～4 个选项。**
- **必要时使用真实内容。** 例如设计摄影作品集时，真实图片比占位块更容易暴露布局问题。
- **草图保持克制。** 聚焦当前需要判断的结构和视觉关系，不追求无关的像素级完整度。

## 文件命名

- 使用能表达内容的名称，例如 `platform.html`、`visual-style.html`、`layout.html`。
- 不要覆盖旧文件，每张页面都创建新文件。
- 迭代版本使用 `layout-v2.html`、`layout-v3.html` 这样的后缀。
- 服务器始终展示修改时间最新的文件。

## 结束和清理

```bash
<skill-dir>/scripts/stop-server.sh "$SESSION_DIR"
```

使用 `--project-dir` 时，页面会保留在 `.brainstorm/` 中，方便后续查看。只有写入系统临时目录的会话会在停止时自动删除。

## 相关文件

- 页面模板和 CSS：`scripts/frame-template.html`
- 浏览器端辅助脚本：`scripts/helper.js`
