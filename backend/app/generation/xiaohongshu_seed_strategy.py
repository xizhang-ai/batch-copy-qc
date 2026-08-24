"""Global generation-only writing instruction for Xiaohongshu seed content."""

STRATEGY_NAME = "红书种草写作策略"
STRATEGY_VERSION = "v1"


def build_instruction() -> str:
    """Return the stable instruction injected immediately before copy generation."""
    return """【红书种草写作策略 v1】
这是一篇自然、可信的小红书种草笔记：先让读者看到与自己有关的需求或场景，再自然带出产品；不要把产品参数堆成广告。
开头从具体痛点、尝试理由或小众发现中选择一个切口，不能直接硬推产品、制造焦虑或夸张承诺。
正文按“使用场景 → 可核实细节 → 主观感受或选择理由”展开：把项目事实中的规格、成分、材质、设计或使用方式翻译成日常体验；每个卖点尽量配一个具体细节。
只能使用 project_facts、must_include 和 effective_rules 支持的信息。不得编造亲测、回购、使用时长、前后对比、数据、他人反馈、产品缺点或用户身份；没有真实体验依据时，使用条件化的场景建议，不要伪装成亲身经历。
结尾总结适合的场景或需求，给读者自主选择空间；可轻度邀请交流，但不催单、逼单或喊口号。
使用短段落，每段一到两句，语气口语化、克制；可少量使用 emoji 和精准标签。避免“最、必入、顶级、闭眼买、全网第一”等绝对化表达，并严格遵守 must_avoid 和所有有效规则。"""
