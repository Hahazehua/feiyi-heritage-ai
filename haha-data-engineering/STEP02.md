# 第二课：把商品编号变成可理解的信息

第一步已经把 54 件商品整理成 Parquet。第二步接着读取这份结果，
根据商家编号和非遗项目编号，补充商家名称、地区和非遗名称。

```text
第一步的商品 Parquet + merchants.csv + heritage_items.csv
                       ↓ Spark Join
         信息更完整的商品维度表 + 检查报告
```

## 运行

在 PowerShell 中执行：

```powershell
Set-Location 'F:\HC\hackathon'
.\.venv\Scripts\python.exe .\haha-data-engineering\step02_product_dimension.py --snapshot-date 2026-09-07
```

默认读取第一课已经验证通过的 `output/20260906_203925_876380/dim_product`。
输入固定，避免程序自动选择了一个意外的结果目录。也可以用 `--products` 指定
另一份第一课成功输出的绝对路径。商家与非遗资料读取原项目当前 CSV。

日期参数表示这次采集快照的标签，不代表恢复了那一天的历史源数据。
每次运行新建一个输出文件夹，尚未实现按日覆盖、自动调度或历史补数。

## 关键概念

- **Join（关联）**：商品里的 merchant_id 对应商家表的 merchant_id，由此查出商家名称。
- **主键**：一张表里唯一识别一行的字段。例如商品表的 product_id。
- **外键关联**：商品的 merchant_id 引用了另一张表的商家编号。
- **粒度**：每行代表什么。本课始终保持每行一件商品。
- **左连接 left join**：保留商品，再添加对应的参考资料。

程序先检查商家、非遗编号是否重复，然后检查每件商品能否找到对应资料。
因此既防止重复编号让一件商品变成多行，也防止找不到资料导致商品悄悄消失。
任何检查失败都会停止，不会自动伪造或填补资料。

原有价格、商品状态、演示标记都会保留；新增商家与非遗资料的版本、
核验说明和演示标记，避免把演示分类当成正式认证。
保留 merchant_id 不意味着原商品 CSV 已经包含商家全名，名称来自本次关联。

## 输出与验收

在 `output/step02_运行时间/` 中查看：

- `dim_product_snapshot/`：商品维度 Parquet 表。
- `validation.json`：输入数量、输出数量、关联缺失数量、回读检查与源 CSV 校验值。

当前数据预期：54 件商品、2 个商家、11 个非遗项目；关联后仍为 54 行。
程序还验证输出里的所有原商品字段均未变化。

## 阅读代码

打开 `step02_product_dimension.py`，重点看：

```python
products.join(merchants, "merchant_id", "left").join(
    heritage, "heritage_id", "left"
)
```

这就是本课的核心：以商品为主体，连续关联两张参考表。
`alias` 用来给新增字段取名，避免不同表都有 `status` 或 `data_version` 时混淆。

## 验证边界情况

```powershell
Set-Location 'F:\HC\hackathon'
.\.venv\Scripts\python.exe .\haha-data-engineering\test_step02.py
```

测试覆盖正常关联、商家编号重复、商家找不到、非遗项目找不到四种情况。

下一步是生成明确标注的模拟推荐与选择日志，供后续事实表和指标分析使用。
