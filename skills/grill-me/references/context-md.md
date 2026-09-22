# 参考：CONTEXT.md 格式

在第一个术语敲定、需要真正写入 `CONTEXT.md` 时读这份文档。

## 结构

```md
# {上下文名称}

{一两句话描述这个上下文是什么、为什么存在。}

## 语言

**订单（Order）**:
{一两句话定义该术语}
_避免使用_: Purchase, transaction

**发票（Invoice）**:
向客户发送的交付后付款请求。
_避免使用_: Bill, payment request

**客户（Customer）**:
下订单的个人或组织。
_避免使用_: Client, buyer, account
```

> 注：示例语言应跟随项目主语言。中文项目用中文术语，英文项目用英文术语。

## 规则

- **有主张。** 当多个词指代同一概念时，选最好的那个，其余列入 `_避免使用_`。
- **定义简洁。** 最多两句话。定义它**是**什么，而非它做什么。
- **只收录项目上下文专属术语。** 通用编程概念不属于这里。
- **出现自然聚类时分组。** 若所有术语属于同一领域，平铺即可。
- **完全不含实现细节。** 它只是术语表，不是规格文档、草稿本或实现决策仓库。

## 单上下文 vs 多上下文

大多数仓库只有单一上下文：根目录一个 `CONTEXT.md`，决策记录在 `docs/adr/`。

多上下文时，根目录用 `CONTEXT-MAP.md` 列出所有上下文及其关系，各上下文有自己的 `CONTEXT.md` 和 `docs/adr/`，系统级决策留在根 `docs/adr/`：

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← 系统级决策
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← 上下文专属决策
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

`CONTEXT-MAP.md` 的形态：

```md
# 上下文地图

## 上下文

- [Ordering](./src/ordering/CONTEXT.md) — 接收和追踪客户订单
- [Billing](./src/billing/CONTEXT.md) — 生成发票和处理付款
- [Fulfillment](./src/fulfillment/CONTEXT.md) — 管理仓库拣货和发运

## 关系

- **Ordering → Fulfillment**: Ordering 发出 `OrderPlaced` 事件；Fulfillment 消费它以启动拣货
- **Fulfillment → Billing**: Fulfillment 发出 `ShipmentDispatched` 事件；Billing 消费它以生成发票
- **Ordering ↔ Billing**: 共享 `CustomerId` 和 `Money` 类型
```

推断当前结构：`CONTEXT-MAP.md` 存在就读它来定位上下文；只有根 `CONTEXT.md` 则为单上下文；都不存在就在第一个术语敲定时懒创建根 `CONTEXT.md`。多上下文时推断当前话题属于哪个上下文，不确定就问。
