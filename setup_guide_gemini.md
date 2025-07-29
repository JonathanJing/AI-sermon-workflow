# Gemini 2.5-pro 配置指南

本指南将帮助你配置Google Gemini 2.5-pro API，用于AI视频自动切片系统。

## 🔑 获取Google Cloud Service Account

### 1. 创建Google Cloud项目

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 点击"Select a project" > "New Project"
3. 输入项目名称，例如："ai-video-clipper"
4. 点击"Create"

### 2. 启用Gemini API

1. 在Google Cloud Console中，导航到"APIs & Services" > "Library"
2. 搜索"Generative Language API"
3. 点击启用该API
4. 如果需要，也可以启用"AI Platform API"

### 3. 创建Service Account

1. 导航到"IAM & Admin" > "Service Accounts"
2. 点击"Create Service Account"
3. 输入Service Account详情：
   - **Name**: `gemini-video-clipper`
   - **Description**: `Service account for AI video clipping system`
4. 点击"Create and Continue"

### 4. 分配权限

在"Grant this service account access to project"步骤中，添加以下角色：
- `AI Platform User`
- `Generative AI User` (如果可用)
- `Service Account User`

点击"Continue"，然后"Done"

### 5. 创建密钥文件

1. 在Service Accounts列表中，点击你刚创建的Service Account
2. 转到"Keys"标签页
3. 点击"Add Key" > "Create new key"
4. 选择"JSON"格式
5. 点击"Create"
6. 密钥文件将自动下载到你的计算机

### 6. 配置密钥文件

1. 将下载的JSON文件重命名为`service-account.json`
2. 将该文件移动到项目根目录：
   ```bash
   mv ~/Downloads/your-project-xxxxx-xxxxxxxx.json ./service-account.json
   ```

## 🛠️ 配置项目

### 1. 环境变量配置

创建`.env`文件：
```bash
cp .env.example .env
```

编辑`.env`文件：
```env
# Google AI配置
GOOGLE_SERVICE_ACCOUNT_PATH=service-account.json
GEMINI_MODEL=gemini-2.5-pro

# Gemini配置参数
GEMINI_TEMPERATURE=0.7
GEMINI_TOP_P=0.8
GEMINI_TOP_K=40
GEMINI_MAX_OUTPUT_TOKENS=2048

# 服务配置
HOST=0.0.0.0
PORT=8000
DEBUG=True

# 文件路径配置
OUTPUT_DIR=data/clips
UPLOAD_DIR=data/uploads
LOG_DIR=logs
```

### 2. 验证配置

启动服务并测试：
```bash
cd app
python main.py
```

访问API测试页面：
```bash
curl -X POST "http://localhost:8000/video-clipping/config" \
  -H "Content-Type: application/json" \
  -d '{
    "service_account_path": "service-account.json",
    "model": "gemini-2.5-pro",
    "output_dir": "data/clips"
  }'
```

## 🔍 故障排除

### 1. 认证错误

**错误**: `DefaultCredentialsError` 或 `403 Forbidden`

**解决方案**:
- 检查`service-account.json`文件是否存在且路径正确
- 确认Service Account具有正确的权限
- 验证Google Cloud项目是否启用了相关API

### 2. API配额限制

**错误**: `429 Too Many Requests` 或配额超限

**解决方案**:
- 检查Google Cloud Console中的配额使用情况
- 考虑申请增加配额或升级到付费账户
- 实现请求限速机制

### 3. 模型不可用

**错误**: `Model not found` 或 `gemini-2.5-pro not available`

**解决方案**:
- 确认你的地区支持Gemini 2.5-pro
- 检查API版本是否最新
- 尝试使用其他可用的Gemini模型（如`gemini-1.5-pro`）

### 4. 网络连接问题

**错误**: `Connection timeout` 或网络错误

**解决方案**:
- 检查防火墙设置
- 确认可以访问Google API端点
- 考虑配置代理（如果在企业网络中）

## 🔧 高级配置

### 1. 自定义生成参数

在代码中调整Gemini参数：
```python
generation_config = {
    "temperature": 0.5,      # 降低随机性
    "top_p": 0.9,           # 核采样参数
    "top_k": 50,            # Top-K采样
    "max_output_tokens": 4096,  # 最大输出长度
}
```

### 2. 安全设置

配置内容安全过滤：
```python
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH", 
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    }
]
```

### 3. 批量处理优化

对于大量请求，考虑：
- 实现请求池和限速
- 使用异步处理
- 缓存常见的AI响应

### 4. 监控和日志

启用详细日志：
```python
import logging
logging.getLogger('google.generativeai').setLevel(logging.DEBUG)
```

监控API使用情况：
- Google Cloud Console > Monitoring
- 设置配额告警
- 跟踪成本和使用趋势

## 📋 配置检查清单

- [ ] Google Cloud项目已创建
- [ ] Generative Language API已启用
- [ ] Service Account已创建并配置权限
- [ ] Service Account密钥已下载并放置在正确位置
- [ ] 环境变量已正确配置
- [ ] API连接测试成功
- [ ] 权限和配额检查通过
- [ ] 安全设置已配置
- [ ] 日志和监控已设置

## 🌐 有用的链接

- [Google Cloud Console](https://console.cloud.google.com/)
- [Gemini API文档](https://ai.google.dev/docs)
- [Service Account指南](https://cloud.google.com/iam/docs/service-accounts)
- [API配额管理](https://cloud.google.com/docs/quota)
- [Gemini定价](https://ai.google.dev/pricing)

## 💡 提示和最佳实践

1. **安全性**：
   - 不要将Service Account密钥提交到版本控制
   - 定期轮换密钥
   - 使用最小权限原则

2. **性能**：
   - 调整`temperature`参数以平衡创意性和一致性
   - 使用适当的`max_output_tokens`限制
   - 实现结果缓存机制

3. **成本控制**：
   - 监控API使用情况
   - 设置预算告警
   - 优化提示词以减少token消耗

4. **可靠性**：
   - 实现重试机制
   - 处理API限制和错误
   - 使用健康检查监控服务状态